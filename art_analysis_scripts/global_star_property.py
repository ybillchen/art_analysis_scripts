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


def save_logmi(basepath, a_target):
    ds = yt.load(os.path.join(basepath, "run/out/snap_a%.4f.art"%a_target))
    snap = ds.all_data()
    logmi = np.log10(snap[("STAR", "INITIAL_MASS")].to_value("Msun"))
    np.savetxt(os.path.join(basepath, "run/analysis/logmi.txt"), logmi)

def save_tave(basepath, a_target):
    ds = yt.load(os.path.join(basepath, "run/out/snap_a%.4f.art"%a_target))
    snap = ds.all_data()
    tave = ave_time(snap).to_value("Myr")
    np.savetxt(os.path.join(basepath, "run/analysis/tave.txt"), tave)

def save_tdur(basepath, a_target):
    ds = yt.load(os.path.join(basepath, "run/out/snap_a%.4f.art"%a_target))
    snap = ds.all_data()
    tave = duration(snap).to_value("Myr")
    np.savetxt(os.path.join(basepath, "run/analysis/tdur.txt"), tdur)

def save_tspread(basepath, a_target):
    ds = yt.load(os.path.join(basepath, "run/out/snap_a%.4f.art"%a_target))
    snap = ds.all_data()
    tspread = age_spread(snap).to_value("Myr")
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
        a_target = sys.argv[2]

    assert not a_target is None

    save_icmf(basepath, a_target)
    save_tave(basepath, a_target)
    save_tdur(basepath, a_target)
    save_tspread(basepath, a_target)