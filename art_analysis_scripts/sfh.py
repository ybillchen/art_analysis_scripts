"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import sys

import numpy as np

def print_sfh(basepath, simple=False):
    d = np.loadtxt(basepath+"run/log/sf.log")
    steps = d[:,0].astype(int)
    ts = d[:,4]
    ms_star = d[:,7]

    print("steps = ", repr(steps))
    print("ts = ", repr(ts))
    print("ts = ", repr(ms_star))

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

    print_sfh(basepath, simple)