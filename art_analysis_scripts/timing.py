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
    total_run_time = [0]
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
    t = []
    dt = []
    for line in data:
        x = line.split(" ")
        if x[0] == "#" or x[0] == "":
            continue

        step.append(int(x[0]))
        t.append(float(x[1]))
        dt.append(float(x[2]))

    step = np.array(step)
    t = np.array(t)
    dt = np.array(dt)

    d_run_time = total_run_time[1:] - total_run_time[:-1]

    t_per_runtime = (3600/1e6) * dt / d_run_time # Myr per hr

    for i in range(len(step)):
        print("step %d, time %.1f Myr, time/runtime %.1f Myr/hr"%(
            step[i], t[i], t_per_runtime[i]))

if __name__ == '__main__':
    if len(sys.argv) == 1:
        path_to_log = "log/"
    elif len(sys.argv) == 2:
        path_to_log = sys.argv[1]

    check_timing(path_to_log)