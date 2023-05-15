import logging

import torch
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path
import seaborn as sns
import os


def save_heatmap(tensor: torch, downsampling: int, plot_title: str, filepath: Path) -> None:
    tensor_cpu = tensor.detach().clone().cpu()
    downsampled_tensor = tensor_cpu[::downsampling, ::downsampling]
    logging.info(f'downsampled_tensor: {downsampled_tensor}')
    sns.heatmap(downsampled_tensor, cmap='viridis')
    plt.title(plot_title)
    directory = os.path.dirname(filepath)
    os.makedirs(directory, exist_ok=True)
    plt.savefig(filepath)
    plt.close()


def downsample_cov(tensor: torch, downsampling: int) ->torch:
    tensor_cpu = tensor.detach().clone().cpu()
    return tensor_cpu[::downsampling, ::downsampling]
