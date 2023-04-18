#!/bin/bash
echo "vicrec"
#SBATCH -p performance
#SBATCH -t 1-02:03:04
#SBATCH --job-name=vicreg
#SBATCH --out=out.log
#SBATCH --err=err.log
echo $MASTER_ADDR
echo $MASTER_PORT
python3 /home2/michael.s/vicreg/main_vicreg2.py --data-dir /home2/michael.s/imagenet/ILSVRC/Data/CLS-LOC --exp-dir /home2/michael.s/vicreg_experiment --dist-url 'tcp://10.35.146.45:32000' --num-workers 8 --world-size 4 --batch-size 32