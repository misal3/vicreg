import os
import argparse
from pathlib import Path


def get_arguments():
    parser = argparse.ArgumentParser(description="Analyze imagenet data", add_help=False)
    parser.add_argument('--root_folder', type=Path, required=True, help='Folder where train, test, val located')
    return parser


def count_jpg_files(directory):
    count = 0

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".JPEG"):
                count += 1

    return count


def main():
    parser = argparse.ArgumentParser('Imagenet Analysis Script', parents=[get_arguments()])
    args = parser.parse_args()
    root_directory = args.root_folder
    main_subfolders = ["train", "test", "val"]

    for subfolder in main_subfolders:
        print(f'analyzing {subfolder}')
        subfolder_path = os.path.join(root_directory, subfolder)
        jpg_file_count = count_jpg_files(subfolder_path)
        print(f"Number of .jpg files in {subfolder}: {jpg_file_count}")


if __name__ == '__main__':
    main()
