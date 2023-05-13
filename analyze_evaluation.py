import pandas as pd
import re
import matplotlib.pyplot as plt
import os
import argparse
from pathlib import Path


def get_arguments():
    parser = argparse.ArgumentParser(description="Analyze Evaluation by converting a stats.txt file to plots", add_help=False)
    parser.add_argument('--input_file', type=Path, required=True, help='The stats.txt file to analyze')
    parser.add_argument('--output_file', type=Path, required=True, help='The plot output file of the loss')
    return parser


def extract_values(key_value_pairs: list[str]) -> list[float]:
    return_list = []
    for key_value in key_value_pairs:
        return_list.append(float(key_value.split(" ")[1]))
    return return_list


def extract_keys(line: str) -> list[str]:
    keys = re.findall(r'(\"\w*\")', line)
    return [w.replace('"', '') for w in keys]


def plot(df: pd.DataFrame, plot_file: Path, cols: list, x_axis: str, title: str, ylabel: str):
    # select the columns of interest
    # cols = ['step', 'loss', 'invariance_loss', 'variance_loss', 'covariance_loss']
    data = df[cols]

    # set the step column as the x-axis
    #x = data['step']
    x = data[x_axis]

    # plot the y-axis variables against the x-axis
    # plt.plot(x, data['loss'], label='loss')
    # plt.plot(x, data['invariance_loss'], label='invariance_loss')
    # plt.plot(x, data['variance_loss'], label='variance_loss')
    # plt.plot(x, data['covariance_loss'], label='covariance_loss')
    cols_to_plot = cols.copy()
    cols_to_plot.remove(x_axis)
    for column in cols_to_plot:
        plt.plot(x, data[column], label=column)

    # add labels and title
    plt.xlabel(x_axis)
    plt.ylabel(ylabel)
    plt.title(title)

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
    matches_lost = []
    matches_acc = []

    # open the input file
    with open(args.input_file, 'r') as file:
        file.readline()  # ignore the first line (args)
        keys_lost = extract_keys(file.readline())
        keys_acc = []

        for line in file:
            matches = re.findall(pattern, line)
            if "step" in line:
                matches_lost.append(extract_values(matches))
            elif "acc1" in line:
                keys_acc = extract_keys(line)
                matches_acc.append(extract_values(matches))

    # create a dataframe from the list of matches
    df_lost = pd.DataFrame(matches_lost)
    df_lost.columns = keys_lost
    df_acc = pd.DataFrame(matches_acc)
    df_acc.columns = keys_acc

    # print the resulting dataframe
    plot(df=df_lost, plot_file=args.output_file, cols=["step", "loss"], x_axis="step", title="Loss during evaluation", ylabel='loss')
    plot(df=df_acc, plot_file=Path("evaluation_plot_acc.png"), cols=["epoch", "acc1", "acc5", "best_acc1", "best_acc5"], x_axis="epoch", title="Accuracy during evaluation", ylabel='accuracy [%]')


main()
