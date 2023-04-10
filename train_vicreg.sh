#!/bin/bash
echo $MASTER_ADDR
echo $MASTER_PORT
#SBATCH -p performance
#SBATCH -w node15
#SBATCH --exclude=node22
#SBATCH --gpus=4
#SBATCH -t 1-02:03:04
#SBATCH --job-name=vicreg
#SBATCH --out=out.log
#SBATCH --err=err.log
python3 /home2/michael.s/vicreg/main_vicreg.py --data-dir /home2/michael.s/imagenet/ILSVRC/Data/CLS-LOC --exp-dir /home2/michael.s/vicreg_experiment --dist-url 'tcp://10.35.146.96:9988' --num-workers 8 --world-size 4
