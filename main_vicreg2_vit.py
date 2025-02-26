# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.


import random
from pathlib import Path
import argparse
import json
import math
import os
import sys
import time
import logging
import torchvision
from torchvision.models.vision_transformer import vit_b_16
from helpers import save_heatmap, downsample_cov
import torch
import torch.nn.functional as F
from torch import nn, optim
import torch.distributed as dist
import torch.utils.data.sampler
import torchvision.datasets as datasets
import augmentations as aug
from distributed import init_distributed_mode
import resnet
from torch.utils.tensorboard import SummaryWriter

logging.basicConfig(level=logging.DEBUG, filename='vicreg.log', filemode='w', format='%(asctime)s - %(levelname)s - %(message)s')


def get_arguments():
    parser = argparse.ArgumentParser(description="Pretrain a resnet model with VICReg", add_help=False)

    # Data
    parser.add_argument("--data-dir", type=Path, default="/path/to/imagenet", required=True,
                        help='Path to the image net dataset')

    # Checkpoints
    parser.add_argument("--exp-dir", type=Path, default="./exp",
                        help='Path to the experiment folder, where all logs/checkpoints will be stored')
    parser.add_argument("--log-freq-time", type=int, default=60,
                        help='Print logs to the stats.txt file every [log-freq-time] seconds')

    # Model
    parser.add_argument("--arch", type=str, default="resnet50",
                        help='Architecture of the backbone encoder network')
    parser.add_argument("--mlp", default="8192-8192-8192",
                        help='Size and number of layers of the MLP expander head')

    # Optim
    parser.add_argument("--epochs", type=int, default=100,
                        help='Number of epochs')
    parser.add_argument("--batch-size", type=int, default=2048,
                        help='Effective batch size (per worker batch size is [batch-size] / world-size)')
    parser.add_argument("--data-subset-size", type=int, default=-1,
                        help="Number of pictures to use for training. -1 = all pictures of training set")
    parser.add_argument("--base-lr", type=float, default=0.2,
                        help='Base learning rate, effective learning after warmup is [base-lr] * [batch-size] / 256')
    parser.add_argument("--wd", type=float, default=1e-6,
                        help='Weight decay')

    # Loss
    parser.add_argument("--sim-coeff", type=float, default=25.0,
                        help='Invariance regularization loss coefficient')
    parser.add_argument("--std-coeff", type=float, default=25.0,
                        help='Variance regularization loss coefficient')
    parser.add_argument("--cov-coeff", type=float, default=1.0,
                        help='Covariance regularization loss coefficient')

    # Running
    parser.add_argument("--num-workers", type=int, default=10)
    parser.add_argument('--device', default='cuda',
                        help='device to use for training / testing')

    # Distributed
    parser.add_argument('--world-size', default=1, type=int,
                        help='number of distributed processes')
    parser.add_argument('--local_rank', default=-1, type=int)
    parser.add_argument('--dist-url', default='env://',
                        help='url used to set up distributed training')

    return parser


def main(args):
    """print(f"cuda availble: {torch.cuda.is_available()}")
    print("args in main", args, "\n\n")
    torch.backends.cudnn.benchmark = True
    init_distributed_mode(args)
    print("initialized")"""
    gpu = torch.device(args.device)
    logging.info(f"gpu: {gpu}")

    stats_file = open(args.exp_dir / "stats.txt", "a", buffering=1)
    """if args.rank == 0:
        args.exp_dir.mkdir(parents=True, exist_ok=True)
        stats_file = open(args.exp_dir / "stats.txt", "a", buffering=1)
        print(" ".join(sys.argv))
        print(" ".join(sys.argv), file=stats_file)"""

    transforms = aug.TrainTransform()

    dataset = datasets.ImageFolder(args.data_dir / "train", transforms)
    if args.data_subset_size > 0:
        random_indices = random.sample(range(0, len(dataset)), args.data_subset_size)
        dataset = torch.utils.data.Subset(dataset, random_indices)
        #dataset = torch.utils.data.Subset(dataset, range(0, args.data_subset_size))
    # sampler = torch.utils.data.distributed.DistributedSampler(dataset, shuffle=True)
    sampler = torch.utils.data.RandomSampler(data_source=dataset, )
    assert args.batch_size % args.world_size == 0
    # per_device_batch_size = args.batch_size // args.world_size
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=args.batch_size,  # per_device_batch_size,
        # num_workers=args.num_workers,
        pin_memory=True,
        sampler=sampler,
    )
    # max_split_size_mb = 512

    model = VICRegViT(args).cuda(gpu)
    logging.info(f"model: \n{model}")
    loader_ = torch.utils.data.DataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    example_images, _ = next(iter(loader_))
    example_images = torch.cat(example_images, dim=0)
    image_grid = torchvision.utils.make_grid(example_images)
    writer.add_image("sample images", image_grid)

    model = nn.SyncBatchNorm.convert_sync_batchnorm(model)
    optimizer = LARS(
        model.parameters(),
        lr=0,
        weight_decay=args.wd,
        weight_decay_filter=exclude_bias_and_norm,
        lars_adaptation_filter=exclude_bias_and_norm,
    )
    # optimizer = optim.Adam(
    #     params=model.parameters(),
    #     lr=0,
    #     weight_decay=args.wd,
    # )

    if (args.exp_dir / "model.pth").is_file():
        if True:  # args.rank == 0:
            print("resuming from checkpoint")
        ckpt = torch.load(args.exp_dir / "model.pth", map_location="cpu")
        start_epoch = ckpt["epoch"]
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
    else:
        start_epoch = 0

    start_time = last_logging = time.time()
    scaler = torch.cuda.amp.GradScaler()
    for epoch in range(start_epoch, args.epochs):
        print(f"epoch: {epoch}")
        print(f"steps per epoch: {len(loader)}")
        # sampler.set_epoch(epoch)
        for step, ((x, y), _) in enumerate(loader, start=epoch * len(loader)):
            print(f"step {step}")
            x = x.cuda(gpu, non_blocking=True)
            y = y.cuda(gpu, non_blocking=True)

            lr = adjust_learning_rate(args, optimizer, loader, step)
            # print("lr", lr)

            optimizer.zero_grad()
            with torch.cuda.amp.autocast():
                loss = model.forward(x, y, step=step, epoch=epoch)

            writer.add_scalar('loss', loss["loss_total"], step)
            writer.add_scalar('invariance_loss', loss["loss_details"]["invariance_loss"], step)
            writer.add_scalar('variance_loss', loss["loss_details"]["variance_loss"], step)
            writer.add_scalar('covariance_loss', loss["loss_details"]["covariance_loss"], step)

            scaler.scale(loss["loss_total"]).backward()
            scaler.step(optimizer)
            scaler.update()

            current_time = time.time()
            if current_time - last_logging > args.log_freq_time:
                stats = dict(
                    epoch=epoch,
                    step=step,
                    loss=loss["loss_total"].item(),
                    loss_details=loss["loss_details"],#.item(),
                    time=int(current_time - start_time),
                    lr=lr,
                )
                print(json.dumps(stats))
                print(json.dumps(stats), file=stats_file)
                last_logging = current_time
        if True:  # args.rank == 0:
            state = dict(
                epoch=epoch + 1,
                model=model.state_dict(),
                optimizer=optimizer.state_dict(),
            )
            torch.save(state, args.exp_dir / "model.pth")
    # if args.rank == 0:
    torch.save(model.backbone.state_dict(), args.exp_dir / "vit.pth")


def adjust_learning_rate(args, optimizer, loader, step):
    max_steps = args.epochs * len(loader)
    warmup_steps = 10 * len(loader)
    base_lr = args.base_lr * args.batch_size / 256
    if step < warmup_steps:
        lr = base_lr * step / warmup_steps
    else:
        step -= warmup_steps
        max_steps -= warmup_steps
        q = 0.5 * (1 + math.cos(math.pi * step / max_steps))
        end_lr = base_lr * 0.001
        lr = base_lr * q + end_lr * (1 - q)
    for param_group in optimizer.param_groups:
        param_group["lr"] = lr
    return lr


class VICRegViT(nn.Module):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.num_features = int(args.mlp.split("-")[-1])
        # self.backbone, self.embedding = resnet.__dict__[args.arch](
        #    zero_init_residual=True
        # )
        self.backbone = vit_b_16()
        self.backbone.heads = nn.Identity()
        self.embedding = 768
        self.projector = Projector(args, self.embedding)
        self.last_epoch = -1

    def forward(self, x, y, step: int = 0, epoch: int = 0):
        x = self.projector(self.backbone(x))
        y = self.projector(self.backbone(y))

        if step % 1000 == 0:
            writer.add_embedding(mat=x, global_step=step, tag='x')
            writer.add_embedding(mat=x, global_step=step, tag='y')

        logging.info("########## FORWARD ##############")
        logging.info(f'shape: x: {x.shape}, y: {y.shape}')

        repr_loss = F.mse_loss(x, y)

        logging.info(f'repr_loss: {repr_loss}')

        # x = torch.cat(FullGatherLayer.apply(x), dim=0)
        # y = torch.cat(FullGatherLayer.apply(y), dim=0)
        x = x - x.mean(dim=0)
        y = y - y.mean(dim=0)
        logging.info(f'x: {x}')
        logging.info(f'y: {y}')

        std_x = torch.sqrt(x.var(dim=0) + 0.0001)
        std_y = torch.sqrt(y.var(dim=0) + 0.0001)
        logging.info(f'std_x: {std_x.shape}\n{std_x}')
        logging.info(f'std_y: {std_y.shape}\n{std_y}')
        std_loss = torch.mean(F.relu(1 - std_x)) / 2 + torch.mean(F.relu(1 - std_y)) / 2
        logging.info(f'std_loss: {std_loss}')

        cov_x = (x.T @ x) / (self.args.batch_size - 1)
        cov_y = (y.T @ y) / (self.args.batch_size - 1)

        if step % 1000 == 0:
            writer.add_embedding(mat=downsample_cov(tensor=cov_x, downsampling=16), global_step=step, tag='cov_x')
            writer.add_embedding(mat=downsample_cov(tensor=cov_y, downsampling=16), global_step=step, tag='cov_y')

        logging.info(f'cov_x: {cov_x.shape}\n{cov_x}')
        logging.info(f'cov_y: {cov_y.shape}\n{cov_y}')
        cov_loss = off_diagonal(cov_x).pow_(2).sum().div(
            self.num_features
        ) + off_diagonal(cov_y).pow_(2).sum().div(self.num_features)
        logging.info(f'cov_loss: {cov_loss}')

        if epoch != self.last_epoch:
            self.last_epoch = epoch
            save_heatmap(tensor=cov_x, downsampling=16, plot_title=f'cov_x, step {step}, epoch {epoch}',
                         filepath=Path(f'{args.exp_dir}/covPlots/cov_x_step{step}_epoch{epoch}.png'))
            save_heatmap(tensor=cov_y, downsampling=16, plot_title=f'cov_y, step {step}, epoch {epoch}',
                         filepath=Path(f'{args.exp_dir}/covPlots/cov_y_step{step}_epoch{epoch}.png'))

        loss = {
            "loss_total": self.args.sim_coeff * repr_loss + self.args.std_coeff * std_loss + self.args.cov_coeff * cov_loss,
            "loss_details": {
                "invariance_loss": self.args.sim_coeff * repr_loss.item(),
                "variance_loss": self.args.std_coeff * std_loss.item(),
                "covariance_loss": self.args.cov_coeff * cov_loss.item()
            }
        }
        # loss = (
        #         self.args.sim_coeff * repr_loss
        #         + self.args.std_coeff * std_loss
        #         + self.args.cov_coeff * cov_loss
        # )
        return loss


class VICReg(nn.Module):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.num_features = int(args.mlp.split("-")[-1])
        self.backbone, self.embedding = resnet.__dict__[args.arch](
            zero_init_residual=True
        )
        self.projector = Projector(args, self.embedding)
        self.last_epoch = -1

    def forward(self, x, y, step: int = 0, epoch: int = 0):
        x = self.projector(self.backbone(x))
        y = self.projector(self.backbone(y))

        if step % 1000 == 0:
            writer.add_embedding(mat=x, global_step=step, tag='x')
            writer.add_embedding(mat=x, global_step=step, tag='y')

        logging.info("########## FORWARD ##############")
        logging.info(f'shape: x: {x.shape}, y: {y.shape}')

        repr_loss = F.mse_loss(x, y)

        logging.info(f'repr_loss: {repr_loss}')

        # x = torch.cat(FullGatherLayer.apply(x), dim=0)
        # y = torch.cat(FullGatherLayer.apply(y), dim=0)
        x = x - x.mean(dim=0)
        y = y - y.mean(dim=0)
        logging.info(f'x: {x}')
        logging.info(f'y: {y}')

        std_x = torch.sqrt(x.var(dim=0) + 0.0001)
        std_y = torch.sqrt(y.var(dim=0) + 0.0001)
        logging.info(f'std_x: {std_x.shape}\n{std_x}')
        logging.info(f'std_y: {std_y.shape}\n{std_y}')
        std_loss = torch.mean(F.relu(1 - std_x)) / 2 + torch.mean(F.relu(1 - std_y)) / 2
        logging.info(f'std_loss: {std_loss}')

        cov_x = (x.T @ x) / (self.args.batch_size - 1)
        cov_y = (y.T @ y) / (self.args.batch_size - 1)

        if step % 1000 == 0:
            writer.add_embedding(mat=downsample_cov(tensor=cov_x, downsampling=16), global_step=step, tag='cov_x')
            writer.add_embedding(mat=downsample_cov(tensor=cov_y, downsampling=16), global_step=step, tag='cov_y')

        logging.info(f'cov_x: {cov_x.shape}\n{cov_x}')
        logging.info(f'cov_y: {cov_y.shape}\n{cov_y}')
        cov_loss = off_diagonal(cov_x).pow_(2).sum().div(
            self.num_features
        ) + off_diagonal(cov_y).pow_(2).sum().div(self.num_features)
        logging.info(f'cov_loss: {cov_loss}')

        if epoch != self.last_epoch:
            self.last_epoch = epoch
            save_heatmap(tensor=cov_x, downsampling=16, plot_title=f'cov_x, step {step}, epoch {epoch}',
                         filepath=Path(f'{args.exp_dir}/covPlots/cov_x_step{step}_epoch{epoch}.png'))
            save_heatmap(tensor=cov_y, downsampling=16, plot_title=f'cov_y, step {step}, epoch {epoch}',
                         filepath=Path(f'{args.exp_dir}/covPlots/cov_y_step{step}_epoch{epoch}.png'))

        loss = {
            "loss_total": self.args.sim_coeff * repr_loss + self.args.std_coeff * std_loss + self.args.cov_coeff * cov_loss,
            "loss_details": {
                "invariance_loss": self.args.sim_coeff * repr_loss.item(),
                "variance_loss": self.args.std_coeff * std_loss.item(),
                "covariance_loss": self.args.cov_coeff * cov_loss.item()
            }
        }
        # loss = (
        #         self.args.sim_coeff * repr_loss
        #         + self.args.std_coeff * std_loss
        #         + self.args.cov_coeff * cov_loss
        # )
        return loss


def Projector(args, embedding):
    """
    Sequential(
        (0): Linear(in_features=2048, out_features=8192, bias=True)
        (1): BatchNorm1d(8192, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True)
        (2): ReLU(inplace=True)
        (3): Linear(in_features=8192, out_features=8192, bias=True)
        (4): BatchNorm1d(8192, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True)
        (5): ReLU(inplace=True)
        (6): Linear(in_features=8192, out_features=8192, bias=False)
    )
    """
    mlp_spec = f"{embedding}-{args.mlp}"  # 2048-8192-8192-8192
    layers = []
    f = list(map(int, mlp_spec.split("-")))  # [2048 8192 8192 8192]
    for i in range(len(f) - 2):
        layers.append(nn.Linear(f[i], f[i + 1]))
        layers.append(nn.BatchNorm1d(f[i + 1]))
        layers.append(nn.ReLU(True))
    layers.append(nn.Linear(f[-2], f[-1], bias=False))
    logging.info(f'projector: {layers}')
    return nn.Sequential(*layers)


def exclude_bias_and_norm(p):
    return p.ndim == 1


def off_diagonal(x):
    n, m = x.shape
    assert n == m
    return x.flatten()[:-1].view(n - 1, n + 1)[:, 1:].flatten()


class LARS(optim.Optimizer):
    def __init__(
            self,
            params,
            lr,
            weight_decay=0,
            momentum=0.9,
            eta=0.001,
            weight_decay_filter=None,
            lars_adaptation_filter=None,
    ):
        defaults = dict(
            lr=lr,
            weight_decay=weight_decay,
            momentum=momentum,
            eta=eta,
            weight_decay_filter=weight_decay_filter,
            lars_adaptation_filter=lars_adaptation_filter,
        )
        super().__init__(params, defaults)

    @torch.no_grad()
    def step(self):
        for g in self.param_groups:
            for p in g["params"]:
                dp = p.grad

                if dp is None:
                    continue

                if g["weight_decay_filter"] is None or not g["weight_decay_filter"](p):
                    dp = dp.add(p, alpha=g["weight_decay"])

                if g["lars_adaptation_filter"] is None or not g[
                    "lars_adaptation_filter"
                ](p):
                    param_norm = torch.norm(p)
                    update_norm = torch.norm(dp)
                    one = torch.ones_like(param_norm)
                    q = torch.where(
                        param_norm > 0.0,
                        torch.where(
                            update_norm > 0, (g["eta"] * param_norm / update_norm), one
                        ),
                        one,
                    )
                    dp = dp.mul(q)

                param_state = self.state[p]
                if "mu" not in param_state:
                    param_state["mu"] = torch.zeros_like(p)
                mu = param_state["mu"]
                mu.mul_(g["momentum"]).add_(dp)

                p.add_(mu, alpha=-g["lr"])


def batch_all_gather(x):
    x_list = FullGatherLayer.apply(x)
    return torch.cat(x_list, dim=0)


class FullGatherLayer(torch.autograd.Function):
    """
    Gather tensors from all process and support backward propagation
    for the gradients across processes.
    """

    @staticmethod
    def forward(ctx, x):
        output = [torch.zeros_like(x) for _ in range(dist.get_world_size())]
        dist.all_gather(output, x)
        return tuple(output)

    @staticmethod
    def backward(ctx, *grads):
        all_gradients = torch.stack(grads)
        dist.all_reduce(all_gradients)
        return all_gradients[dist.get_rank()]


def handle_sigusr1(signum, frame):
    os.system(f'scontrol requeue {os.environ["SLURM_JOB_ID"]}')
    exit()


def handle_sigterm(signum, frame):
    pass


if __name__ == "__main__":
    print("MAIN\n\n")
    logging.info("MAIN")
    parser = argparse.ArgumentParser('VICReg training script', parents=[get_arguments()])
    args = parser.parse_args()
    global writer
    writer = SummaryWriter(str(args.exp_dir) + "/tensorboard")
    with open(Path(f'{args.exp_dir}/args.txt'), "w") as args_file:
        args_file.write(str(args))
    main(args)
