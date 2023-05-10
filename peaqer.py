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

def metric_plot(input, settings):
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
                    "kbps": kbps,
                    "score": score
                }
                results[encoder][metric].append(score_data)
            print()

    formats = ["o-", "v-", "^-", "<-", ">-", "p-", "h-", "H-", "8-", "o--", "v--", "^--", "<--", ">--", "p--", "h--", "H--", "8--"]

    for metric in metrics_settings.keys():
        plt.subplots(figsize=(16, 9))
        fmt = 0
        for encoder in encoder_settings.keys():
            rates = []
            scores = []
            for score_data in results[encoder][metric]:
                rates.append(score_data["kbps"])
                scores.append(score_data["score"])
            plt.plot(rates, scores, formats[fmt],label=encoder_settings[encoder]["label"])
            fmt += 1
            if fmt >= len(formats):
                fmt = 0

        plt.title(input)
        plt.xlabel("Bitrate (kbps)")
        plt.xticks(bitrates)
        plt.ylabel(metrics_settings[metric]["label"])
        plt.legend(loc="lower right")
        plt.grid()
        plt.savefig(input + "." + metric + ".svg")
        plt.clf()


def main():
    settings = {}
    with open("./settings.json") as f:
        settings = json.load(f)

    files = os.listdir(".")
    for file in files:
        if file.endswith(".wav"):
            metric_plot(file, settings)


if __name__ == "__main__":
    main()
