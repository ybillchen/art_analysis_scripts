"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import sys
import datetime

import numpy as np

def check_timing(path):
    f = open(path)
    data = f.read().split("")
    f.close()

    step = []
    t = []
    a = []
    total_run_time = []
    for line in data:
        x = line.split(" ")
        if x[0] == "#" or x[0] == "":
            continue

        step.append(int(x[0]))
        t.append(float(x[1]))
        a.append(float(x[2]))
        total_run_time.append(float(x[3]))

    step = np.array(step)
    t = np.array(t)
    a = np.array(a)
    total_run_time = np.array(total_run_time)

    t_per_runtime = t / total_run_time # yr per s

    print(t_per_runtime)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        path = "log/timing.000.log"
    elif len(sys.argv) == 2:
        path = sys.argv[1]

    check_timing(path)