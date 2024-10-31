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
    is_under_run = os.path.isfile(filename)
    filename = filename if is_under_run else os.path.join(basepath, "out/snap_a%.4f.art"%a_target)
    return yt.load(filename), is_under_run

def log_init_mass(region):
    return np.log10(region[("STAR", "INITIAL_MASS")].to_value("Msun"))

def save_logmi(basepath, a_target):
    ds, is_under_run = load_ds(basepath, a_target)
    snap = ds.all_data()

    logmi = logmi(snap)
    np.savetxt(os.path.join(basepath, "run/" if is_under_run else "", "analysis/logmi.txt"), 
        logmi, fmt="%.6f")

def save_tave(basepath, a_target):
    ds, is_under_run = load_ds(basepath, a_target)
    snap = ds.all_data()

    tave = ave_time(snap)
    np.savetxt(os.path.join(basepath, "run/" if is_under_run else "", "analysis/tave.txt"), 
        tave, fmt="%.6f")

def save_tdur(basepath, a_target):
    ds, is_under_run = load_ds(basepath, a_target)
    snap = ds.all_data()

    tdur = duration(snap)
    np.savetxt(os.path.join(basepath, "run/" if is_under_run else "", "analysis/tdur.txt"), 
        tdur, fmt="%.6f")

def save_tspread(basepath, a_target):
    ds, is_under_run = load_ds(basepath, a_target)
    snap = ds.all_data()

    tspread = age_spread(snap)
    np.savetxt(os.path.join(basepath, "run/" if is_under_run else "", "analysis/tspread.txt"), 
        tspread, fmt="%.6f")

def save_all(basepath, a_target):
    ds, is_under_run = load_ds(basepath, a_target)
    snap = ds.all_data()

    logmi = log_init_mass(snap)
    np.savetxt(os.path.join(basepath, "run/" if is_under_run else "", "analysis/logmi.txt"), 
        logmi, fmt="%.6f")
    tave = ave_time(snap)
    np.savetxt(os.path.join(basepath, "run/" if is_under_run else "", "analysis/tave.txt"), 
        tave, fmt="%.6f")
    tdur = duration(snap)
    np.savetxt(os.path.join(basepath, "run/" if is_under_run else "", "analysis/tdur.txt"), 
        tdur, fmt="%.6f")
    tspread = age_spread(snap)
    np.savetxt(os.path.join(basepath, "run/" if is_under_run else "", "analysis/tspread.txt"), 
        tspread, fmt="%.6f")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        basepath = ""
        a_target = None
    elif len(sys.argv) == 2:
        basepath = ""
        a_target = sys.argv[1]
    elif len(sys.argv) == 3:
        basepath = float(sys.argv[2])
        a_target = sys.argv[1]

    assert not a_target is None

    save_all(basepath, a_target)