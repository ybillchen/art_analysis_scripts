"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import sys
import datetime

import numpy as np

def check_timing(basepath, simple=False):
    f = open(basepath+"run/log/timing.000.log")
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

    f = open(basepath+"run/log/times.log")
    data = f.read().split("\n")
    f.close()
    step = []
    t = []
    dt = []
    a = []
    for line in data:
        x = line.split(" ")
        if x[0] == "#" or x[0] == "":
            continue

        step.append(int(x[0]))
        t.append(float(x[1]))
        dt.append(float(x[2]))
        a.append(float(x[3]))

    step = np.array(step)
    t = np.array(t)
    dt = np.array(dt)
    a = np.array(a)

    d_run_time = total_run_time[1:] - total_run_time[:-1]

    mask = d_run_time <= 0 # this happens in restarts
    d_run_time[mask] = total_run_time[1:][mask]

    runtime_per_t = (1e6/3600) * d_run_time / dt # hr per Myr

    if simple:
        s0 = "step = ["
        s1 = "t = ["
        s2 = "a = ["
        s3 = "runtime_per_t = ["
        s4 = "runtime = ["

        for i in range(len(step)):
            s0 += "%d,"%step[i]
            s1 += "%.1f,"%(t[i]/1e6)
            s2 += "%.4f,"%a[i]
            s3 += "%.3f,"%runtime_per_t[i]
            s4 += "%.3f,"%total_run_time[i+1]/3600

        s0 += "]"
        s1 += "]"
        s2 += "]"
        s3 += "]"
        s4 += "]"

        print(s0)
        print(s1)
        print(s2)
        print(s3)
        print(s4)
        return

    for i in range(len(step)):
        print("step %d, t = %.1f Myr, a = %.4f, runtime = %.3f hr, druntime/dt = %.3f hr/Myr"%(
            step[i], t[i]/1e6, a[i], total_run_time[i+1]/3600, runtime_per_t[i]))

if __name__ == '__main__':
    if len(sys.argv) == 1:
        basepath = ""
        simple = False
    elif len(sys.argv) == 2:
        basepath = sys.argv[1]
        simple = False
    elif len(sys.argv) == 3:
        basepath = sys.argv[1]
        simple = bool(int(sys.argv[2]))

    check_timing(basepath, simple)