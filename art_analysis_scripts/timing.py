"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import sys
import datetime

import numpy as np

def check_timing(path_to_log):
    f = open(path_to_log+"timing.000.log")
    data = f.read().split("\n")
    f.close()
    step = []
    total_run_time = []
    for line in data:
        x = line.split(" ")
        if x[0] == "#" or x[0] == "":
            continue

        step.append(int(x[0]))
        total_run_time.append(float(x[3]))
    step = np.array(step)
    total_run_time = np.array(total_run_time)

    f = open(path_to_log+"times.log")
    data = f.read().split("\n")
    f.close()
    step = []
    dt = []
    for line in data:
        x = line.split(" ")
        if x[0] == "#" or x[0] == "":
            continue

        step.append(int(x[0]))
        dt.append(float(x[2]))

    step = np.array(step)
    dt = np.array(dt)

    t_per_runtime = dt / total_run_time # yr per s

    print(t_per_runtime)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        path_to_log = "log/"
    elif len(sys.argv) == 2:
        path_to_log = sys.argv[1]

    check_timing(path)