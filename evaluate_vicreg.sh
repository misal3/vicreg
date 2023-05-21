#!/bin/bash
#SBATCH -p performance
##SBATCH -w node14
#SBATCH --gpus=1
#SBATCH -t 2-02:03:04
#SBATCH --job-name=vicreg_eval
#SBATCH --out=out-eval.log
#SBATCH --err=err-eval.log
python3 /home2/michael.s/vicreg/evaluate2.py --data-dir /home2/michael.s/imagenet/ILSVRC/Data/CLS-LOC/ --exp-dir /home2/michael.s/vicreg/vicreg_experiment/randomsubset_30000_bs64/evaluation/ --pretrained /home2/michael.s/vicreg/vicreg_experiment/randomsubset_30000_bs64/resnet50.pth --batch-size 64 --workers 1
