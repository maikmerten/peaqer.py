#!/usr/bin/env python3

# peaqer.py by Maik Merten
#
# To the extent possible under law, the person who associated CC0 with
# peaqer.py has waived all copyright and related or neighboring rights
# to peaqer.py.
#
# You should have received a copy of the CC0 legalcode along with this
# work.  If not, see <http://creativecommons.org/publicdomain/zero/1.0/>.

import os
import subprocess
import matplotlib.pyplot as plt
import json

def probe_bitrate(input):
    cmd = "ffprobe -v quiet -print_format json -show_format " + input
    p = subprocess.run(cmd.split(" "), capture_output=True, text=True)
    json_data = json.loads(p.stdout)
    filesize = float(json_data["format"]["size"])
    duration = float(json_data["format"]["duration"])
    bitrate = (filesize * 8) / duration
    return bitrate / 1000

def decode(cmd, input, output):
    cmd = cmd.replace("$INPUT", input)
    cmd = cmd.replace("$OUTPUT", output)
    print("executing " + cmd)
    subprocess.run(cmd.split(" "))

def encode(cmd, input, output, bitrate):
    cmd = cmd.replace("$BPS", str(bitrate * 1000))
    cmd = cmd.replace("$KBPS", str(bitrate))
    cmd = cmd.replace("$INPUT", input)
    cmd = cmd.replace("$OUTPUT", output)
    print("executing " + cmd)
    subprocess.run(cmd.split(" "))

def run_metric(reference, testfile, metric_settings):
    cmd = metric_settings["cmd"]
    prefix = metric_settings["prefix"]
    suffix = None
    if "suffix" in metric_settings.keys():
        suffix = metric_settings["suffix"]

    cmd = cmd.replace("$REFERENCE", reference)
    cmd = cmd.replace("$TESTFILE", testfile)
    print("executing " + cmd)
    p = subprocess.run(cmd.split(" "), capture_output=True, text=True)

    out = p.stdout
    if "out" in metric_settings.keys() and metric_settings["out"] == "stderr":
        out = p.stderr

    score = 0.0
    for line in out.split("\n"):
        if prefix in line:
            start = line.index(prefix) + len(prefix)
            if suffix != None:
                score = float(line[start:line.index(suffix)])
            else:
                score = float(line[start::1])
    return score

def get_plot_format(fmt=0):
    formats = ["o-", "v-", "^-", "<-", ">-", "p-", "h-", "H-", "8-", "o--", "v--", "^--", "<--", ">--", "p--", "h--", "H--", "8--"]
    return formats[fmt % len(formats)]

def save_plot(file, title, xticks, xlabel, ylabel):
    plt.title(title)
    plt.xlabel(xlabel)
    plt.xticks(xticks)
    plt.ylabel(ylabel)
    plt.legend(loc="lower right")
    plt.grid()
    plt.savefig(file)
    plt.clf()
    return file


# plot graphs for a given file
def plot_file(input, plotfiles, settings):
    metrics_settings = settings["metrics"]
    encoder_settings = settings["encoders"]
    decoder_settings = settings["decoders"]
    bitrates = settings["bitrates"]
    decfile = "/tmp/decode.wav"

    results = {}

    for encoder in encoder_settings.keys():
        extension = encoder_settings[encoder]["extension"]
        encode_cmd = encoder_settings[encoder]["cmd"]
        decoder = encoder_settings[encoder]["decoder"]
        decode_cmd = decoder_settings[decoder]["cmd"]

        results[encoder] = {}

        for metric in metrics_settings.keys():
            results[encoder][metric] = []

        for rate in bitrates:
            encfile = "/tmp/test." + extension
            encode(encode_cmd, input, encfile, rate)
            kbps = probe_bitrate(encfile)
            print("Actual bitrate: %f" % (kbps))

            decode(decode_cmd, encfile, decfile)

            for metric in metrics_settings.keys():
                score = run_metric(input, decfile, metrics_settings[metric])
                print("%s: %s for bitrate %d: %f" %(encoder, metrics_settings[metric]["label"], rate, score))
                score_data = {
                    "bitrate": rate, # requested bitrate
                    "kbps": kbps,    # actual bitrate
                    "score": score   # achieved metric score
                }
                results[encoder][metric].append(score_data)

            print()

    for metric in metrics_settings.keys():
        plt.subplots(figsize=(16, 9))
        fmt = 0
        for encoder in encoder_settings.keys():
            rates = []
            scores = []
            for score_data in results[encoder][metric]:
                rates.append(score_data["kbps"])
                scores.append(score_data["score"])
            plt.plot(rates, scores, get_plot_format(fmt), label=encoder_settings[encoder]["label"], gid="encoder_"+ encoder)
            fmt += 1

        plotfile = save_plot(file=input + "." + metric + ".svg", title=input, xticks=bitrates,
                             xlabel="Bitrate (kbps)", ylabel=metrics_settings[metric]["label"])
        plotfiles.append(plotfile)

    return results

# plot average scores over all files
def plot_average(all_scores, plotfiles, settings):

    files = all_scores.keys()
    metrics_settings = settings["metrics"]     
    bitrates = settings["bitrates"]
    encoder_settings = settings["encoders"]

    for metric in metrics_settings.keys():
        score_averages = {}
        rate_averages = {}
        for encoder in encoder_settings.keys():
            avg_scores = []
            avg_rates = []
            for rate in bitrates:
                score_sum = 0.0
                rate_sum = 0.0
                for file in files:
                    for score_data in all_scores[file][encoder][metric]:
                        if score_data["bitrate"] == rate:
                            score_sum += score_data["score"]
                            rate_sum += score_data["kbps"]
                avg_scores.append(score_sum / len(files))
                avg_rates.append(rate_sum / len(files))
            score_averages[encoder] = avg_scores
            rate_averages[encoder] = avg_rates
        

        plt.subplots(figsize=(16, 9))
        fmt = 0
        for encoder in encoder_settings.keys():
            rates = rate_averages[encoder]
            scores = score_averages[encoder]
            plt.plot(rates, scores, get_plot_format(fmt), label=encoder_settings[encoder]["label"], gid="encoder_"+ encoder)
            fmt += 1

        plotfile = save_plot(file="all_files_average." + metric + ".svg", title="Average for %d files" % (len(files)),
                             xticks=bitrates, xlabel="Average bitrate (kbps)", ylabel=metrics_settings[metric]["label"])
        plotfiles.append(plotfile)


def main():
    settings = {}
    with open("./settings.json") as f:
        settings = json.load(f)

    all_scores = {}
    plotfiles_files = []
    plotfiles_avg = []

    files = os.listdir(".")
    files.sort()
    for file in files:
        if file.endswith(".wav"):
            all_scores[file] = plot_file(file, plotfiles_files, settings)
    
    plot_average(all_scores, plotfiles_avg, settings)


    all_results = {}
    all_results["plotfiles"] = plotfiles_avg + plotfiles_files
    all_results["settings"] = settings
    all_results["results"] = all_scores

    with open("all_results.json", "w") as outfile:
        outfile.write(json.dumps(all_results))



if __name__ == "__main__":
    main()
