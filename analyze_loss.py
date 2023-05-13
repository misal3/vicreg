import pandas as pd
import re
import matplotlib.pyplot as plt
import os
import argparse
from pathlib import Path


def get_arguments():
    parser = argparse.ArgumentParser(description="Analyze loss by converting a stats.txt file to a plot", add_help=False)
    parser.add_argument('--input_file', type=Path, required=True, help='The stats.txt file to analyze')
    parser.add_argument('--output_file', type=Path, required=True, help='The plot output file of the loss')
    return parser


def extract_values(key_value_pairs: list[str]) -> list[float]:
    return_list = []
    for key_value in key_value_pairs:
        return_list.append(float(key_value.split(" ")[1]))
    return return_list


def extract_keys(key_value_pairs: list[str]) -> list[float]:
    return_list = []
    for key_value in key_value_pairs:
        return_list.append(key_value.split(":")[0])
    return return_list


def plot(df: pd.DataFrame, plot_file: Path):
    # select the columns of interest
    cols = ['step', 'loss', 'invariance_loss', 'variance_loss', 'covariance_loss']
    data = df[cols]

    # set the step column as the x-axis
    x = data['step']

    # plot the y-axis variables against the x-axis
    plt.plot(x, data['loss'], label='loss')
    plt.plot(x, data['invariance_loss'], label='invariance_loss')
    plt.plot(x, data['variance_loss'], label='variance_loss')
    plt.plot(x, data['covariance_loss'], label='covariance_loss')

    # add labels and title
    plt.xlabel('Step')
    plt.ylabel('Loss')
    plt.title('Loss over time')

    # add a legend
    plt.legend()
    plt.savefig(plot_file)
    plt.close()

    # show the plot
    plt.show()
    print(os.getcwd())


def main():
    parser = argparse.ArgumentParser('Loss Analysis Script', parents=[get_arguments()])
    args = parser.parse_args()

    pattern = r'(\"[\w\s]+\": \d+\.?\d*)'
    # create an empty list to store the matches
    matches_list = []

    # open the input file
    with open(args.input_file, 'r') as file:
        # read the first line to get the keys
        # file.readline()  # ignore the first line (empty)
        keys = re.findall(r'(\"\w*\")', file.readline())
        keys = [w.replace('"', '') for w in keys]
        keys.remove("loss_details")

        # loop through each line in the input file
        for line in file:
            # find all matches in the line
            matches = re.findall(pattern, line)
            # add the matches to the list
            if len(matches) > 0:
                matches_list.append(extract_values(matches))

    # create a dataframe from the list of matches
    df = pd.DataFrame(matches_list)
    df.columns = keys

    # print the resulting dataframe
    # print(df)
    plot(df, args.output_file)


main()
