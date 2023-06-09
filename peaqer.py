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
from threading import Thread

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
    subprocess.run(cmd.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def encode(cmd, input, output, bitrate):
    cmd = cmd.replace("$BPS", str(bitrate * 1000))
    cmd = cmd.replace("$KBPS", str(bitrate))
    cmd = cmd.replace("$INPUT", input)
    cmd = cmd.replace("$OUTPUT", output)
    print("executing " + cmd)
    subprocess.run(cmd.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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


def create_file_plot(file, results, settings):
    metrics_settings = settings["metrics"]
    encoder_settings = settings["encoders"]
    bitrates = settings["bitrates"]

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

        save_plot(file=file + "." + metric + ".svg", title=file, xticks=bitrates, xlabel="Bitrate (kbps)", ylabel=metrics_settings[metric]["label"])


# create metric data for provided file
def measure_file(input, threadid, settings):
    metrics_settings = settings["metrics"]
    encoder_settings = settings["encoders"]
    decoder_settings = settings["decoders"]
    bitrates = settings["bitrates"]
    decfile = "/tmp/decode-" + str(threadid) + ".wav"

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
            encfile = "/tmp/encode-" + str(threadid) + "." + extension
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

            os.remove(encfile)
            os.remove(decfile)

            print()

    return results


# plot average scores over all files
def plot_average(all_scores, settings):

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

        file = "all_files_average." + metric + ".svg"
        title = "Average for %d files" % (len(files))
        save_plot(file=file, title=title, xticks=bitrates, xlabel="Average bitrate (kbps)", ylabel=metrics_settings[metric]["label"])

class PlotThread(Thread):
    def __init__(self, id, files, settings):
        Thread.__init__(self)
        self.id = id
        self.files = files
        self.settings = settings
        self.results = {}
    
    def run(self):
        for file in self.files:
            self.results[file] = measure_file(file, self.id, self.settings)
            

def main():
    settings = {}
    with open("./settings.json") as f:
        settings = json.load(f)

    files = list(filter(lambda file: file.endswith(".wav"), os.listdir(".")))
    files.sort()

    # use half of the hardware threads available
    threads = os.cpu_count() >> 1
    if threads < 1: threads = 1
    threadlist = []
    threadfiles = []
    for i in range(0, threads):
        threadfiles.append([])

    # distribute files to threads
    idx = 0
    for file in files:
        threadfiles[idx % threads].append(file)
        idx += 1
    
    # create and start threads
    for i in range(0, threads):
        thread = PlotThread(i, threadfiles[i], settings)
        thread.start()
        threadlist.append(thread)

    # assemble results
    threadscores = {}
    for thread in threadlist:
        thread.join()
        for file in thread.results.keys():
            threadscores[file] = thread.results[file]

    # put results into file order
    all_scores = {}
    for file in files:
        all_scores[file] = threadscores[file]
   

    # create plots for all files
    for file in all_scores.keys():
        create_file_plot(file, all_scores[file], settings)

    # plot average    
    plot_average(all_scores, settings)


    # write all results to JSON file
    all_results = {}
    all_results["settings"] = settings
    all_results["results"] = all_scores

    with open("all_results.json", "w") as outfile:
        outfile.write(json.dumps(all_results))



if __name__ == "__main__":
    main()
