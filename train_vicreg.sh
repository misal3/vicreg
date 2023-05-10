#!/bin/bash
#SBATCH -p performance
#SBATCH -w node14
#SBATCH --gpus 3
#SBATCH -t 1-02:03:04
#SBATCH --job-name=vicreg
#SBATCH --out=out.log
#SBATCH --err=err.log
python3 /home2/michael.s/vicreg/main_vicreg2.py --data-dir /home2/michael.s/imagenet/ILSVRC/Data/CLS-LOC --exp-dir /home2/michael.s/vicreg/vicreg_experiment --num-workers 1 --world-size 1 --batch-size 64 --data-subset-size 10000
