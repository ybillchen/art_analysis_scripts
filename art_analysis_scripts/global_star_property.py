"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import os
import sys

import numpy as np
import yt

from age_spreads import time_units, duration, ave_time, age_spread

def load_ds(basepath, a_target):
    filename = os.path.join(basepath, "run/out/snap_a%.4f.art"%a_target)
    filename = filename if os.path.isfile(filename) else os.path.join(basepath, "out/snap_a%.4f.art"%a_target)
    return yt.load(filename)

def logmi(region):
    return np.log10(region[("STAR", "INITIAL_MASS")].to_value("Msun"))

def save_logmi(basepath, a_target):
    ds = load_ds(basepath, a_target)
    snap = ds.all_data()

    logmi = logmi(snap)
    np.savetxt(os.path.join(basepath, "run/analysis/logmi.txt"), logmi)

def save_tave(basepath, a_target):
    ds = load_ds(basepath, a_target)
    snap = ds.all_data()

    tave = ave_time(snap)
    np.savetxt(os.path.join(basepath, "run/analysis/tave.txt"), tave)

def save_tdur(basepath, a_target):
    ds = load_ds(basepath, a_target)
    snap = ds.all_data()

    tave = duration(snap)
    np.savetxt(os.path.join(basepath, "run/analysis/tdur.txt"), tdur)

def save_tspread(basepath, a_target):
    ds = load_ds(basepath, a_target)
    snap = ds.all_data()

    tspread = age_spread(snap)
    np.savetxt(os.path.join(basepath, "run/analysis/tspread.txt"), tspread)

def save_all(basepath, a_target):
    ds = load_ds(basepath, a_target)
    snap = ds.all_data()

    logmi = logmi(snap)
    np.savetxt(os.path.join(basepath, "run/analysis/logmi.txt"), logmi)
    tave = ave_time(snap)
    np.savetxt(os.path.join(basepath, "run/analysis/tave.txt"), tave)
    tave = duration(snap)
    np.savetxt(os.path.join(basepath, "run/analysis/tdur.txt"), tdur)
    tspread = age_spread(snap)
    np.savetxt(os.path.join(basepath, "run/analysis/tspread.txt"), tspread)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        basepath = ""
        a_target = None
    elif len(sys.argv) == 2:
        basepath = sys.argv[1]
        a_target = None
    elif len(sys.argv) == 3:
        basepath = sys.argv[1]
        a_target = float(sys.argv[2])

    assert not a_target is None

    save_all(basepath, a_target)