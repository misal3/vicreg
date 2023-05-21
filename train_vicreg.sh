#!/bin/bash
#SBATCH -p performance
##SBATCH -w node14
#SBATCH --gpus=1
#SBATCH -t 4-02:03:04
#SBATCH --job-name=vicregall
#SBATCH --out=outall.log
#SBATCH --err=errall.log
python3 /home2/michael.s/vicreg/main_vicreg2.py --data-dir /home2/michael.s/cifar10/ --exp-dir /home2/michael.s/vicreg/vicreg_experiment_cifar10/all_bs64/ --num-workers 1 --world-size 1 --batch-size 64 --data-subset-size -1
