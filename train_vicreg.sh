#!/bin/bash
#SBATCH -p performance
#SBATCH -w node14
#SBATCH --gpus=1
#SBATCH -t 2-02:03:04
#SBATCH --job-name=vicreg_1
#SBATCH --out=out-1.log
#SBATCH --err=err-1.log
python3 /home2/michael.s/vicreg/main_vicreg2.py --data-dir /home2/michael.s/imagenet/ILSVRC/Data/CLS-LOC --exp-dir /home2/michael.s/vicreg/vicreg_experiment/randomsubset_10000_bs32/ --num-workers 1 --world-size 1 --batch-size 32 --data-subset-size 10000
