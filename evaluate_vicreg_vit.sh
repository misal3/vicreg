#!/bin/bash
#SBATCH -p performance
#SBATCH -w node14
#SBATCH --gpus=1
#SBATCH -t 2-02:03:04
#SBATCH --job-name=vicreg_eval_vit
#SBATCH --dependency=afterok:12383
#SBATCH --out=out-eval_vit.log
#SBATCH --err=err-eval_vit.log
python3 /home2/michael.s/vicreg/evaluate2_vit.py --data-dir /home2/michael.s/imagenet/ILSVRC/Data/CLS-LOC/ --exp-dir /home2/michael.s/vicreg/vicreg_experiment_vit/randumsubset_10000_bs64/evaluation/ --pretrained /home2/michael.s/vicreg/vicreg_experiment_vit/vit.pth --batch-size 64 --workers 1
