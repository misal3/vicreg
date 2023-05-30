#!/bin/bash
#SBATCH -p performance
#SBATCH -w node14
#SBATCH --gpus=1
#SBATCH -t 4-02:03:04
#SBATCH --job-name=vicregvita
#SBATCH --out=out_vita.log
#SBATCH --err=err_vita.log
python3 /home2/michael.s/vicreg/main_vicreg2_vit.py --data-dir /home2/michael.s/cifar10/ --exp-dir /home2/michael.s/vicreg/vicreg_experiment_cifar10_vit/all_bs64/ --num-workers 1 --world-size 1 --batch-size 64 --data-subset-size -1
