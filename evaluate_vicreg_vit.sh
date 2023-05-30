#!/bin/bash
#SBATCH -p performance
##SBATCH -w node14
#SBATCH --gpus=1
#SBATCH -t 2-02:03:04
#SBATCH --job-name=vicreg_eval_vita
#SBATCH --dependency=afterok:12774
#SBATCH --out=out-eval_vita.log
#SBATCH --err=err-eval_vita.log
python3 /home2/michael.s/vicreg/evaluate2_vit.py --data-dir /home2/michael.s/cifar10/ --exp-dir /home2/michael.s/vicreg/vicreg_experiment_cifar10_vit/all_bs64/evaluation/ --pretrained /home2/michael.s/vicreg/vicreg_experiment_cifar10_vit/all_bs64/vit.pth --batch-size 64 --workers 1
