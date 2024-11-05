"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import os
import sys

import numpy as np

import yt
yt.enable_parallelism()

from age_spreads import time_units, duration, ave_time, age_spread

# scale(0) id(1) desc_scale(2) desc_id(3) num_prog(4) pid(5) upid(6) desc_pid(7) 
# phantom(8) sam_Mvir(9) Mvir(10) Rvir(11) rs(12) vrms(13) mmp?(14) scale_of_last_MM(15) 
# vmax(16) x(17) y(18) z(19) vx(20) vy(21) vz(22) Jx(23) Jy(24) Jz(25) Spin(26) 
# Breadth_first_ID(27) Depth_first_ID(28) Tree_root_ID(29) Orig_halo_ID(30) Snap_idx(31) 
# Next_coprogenitor_depthfirst_ID(32) Last_progenitor_depthfirst_ID(33) 
# Last_mainleaf_depthfirst_ID(34) Tidal_Force(35) Tidal_ID(36)

def find_most_massive_halos(tree, a_target, num=1):
    # TODO: move this to a more general place
    snap = tree[:,31]

    if a_target is None or a_target < 0 or a_target > 1.1:
        mask_now = snap == np.max(snap)
    else:
        mask_now = np.abs(tree[:,0]-a_target)<5e-5

    idxs_mmax = np.argsort(tree[mask_now,10])[::-1]

    mbs = []

    for i in range(num):
        idx_mmax = idxs_mmax[i]
        mainleaf_id = tree[mask_now,34][idx_mmax]

        mask_mb = tree[:,34] == mainleaf_id
        mb = tree[mask_mb]
        mb = mb[np.argsort(mb[:,0])]
        mbs.append(mb)

    return mbs

def sfr(region, agecut=50.0):
    tnow  = region.ds.current_time.to_value("Myr")
    ms_i = region[("STAR", "INITIAL_MASS")].to_value("Msun")
    tform = region[("STAR", "creation_time")].to_value("Myr")
    tage = tnow - tform
    mask = tage < agecut
    ms_cut = np.sum(ms_i[mask])
    return 1e-6*ms_cut/agecut # in Msun/yr

def stellar_mass(region):
    return np.sum(region[("STAR", "MASS")].to_value("Msun"))

def frac_above(region, masscut=1e5):
    ms = region[("STAR", "MASS")].to_value("Msun")
    fbound0 = region[("STAR", "INITIAL_BOUND_FRACTION")].to_value("1")
    fbound = region[("STAR", "BOUND_FRACTION")].to_value("1")
    mc = ms * fbound * fbound0
    ms_cut = np.sum(mc[mc>masscut])
    return ms_cut/np.sum(ms)


def histories(ts, branches, func, **kwargs):
    storage = {}

    for store, ds in ts.piter(storage=storage):
        scale = 1 / (ds.current_redshift+1)
        tnow  = ds.current_time.to_value("Myr")

        out = (scale, tnow)

        for branch in branches:
            idx = np.where(np.abs(branch[:,0]-scale)<5e-5)[0]
            if len(idx) == 0:
                out += (np.nan,)
                continue

            assert len(idx) == 1

            line = branch[idx[0]]
            hpos = line[17:20] * ds.arr(1, "Mpccm/h")
            rvir = line[11] * ds.arr(1, "kpccm/h")
            sp = ds.sphere(hpos, rvir)

            out += (func(sp, **kwargs),)

        store.result = out

    result = np.array(list(storage.values()))
    return result[np.argsort(result[:,0])]

def save_histories_most_massive_halos(basepath, a_target, agecut=50.0, masscut=1e5):

    tree = np.loadtxt(os.path.join(basepath, "rockstar_halos/trees/tree_0_0_0.dat"), skiprows=48)
    ts = yt.load(os.path.join(basepath, "out/snap_a*.art"))

    mbs = find_most_massive_halos(tree, a_target, num=10)

    sfr_histories = histories(ts, mbs, sfr, agecut=agecut)
    np.savetxt(os.path.join(basepath, "analysis/sfr_histories_%g.txt"%agecut), sfr_histories, fmt="%.6e")

    ms_histories = histories(ts, mbs, stellar_mass)
    np.savetxt(os.path.join(basepath, "analysis/ms_histories.txt"), ms_histories, fmt="%.6e")

    fabove_histories = histories(ts, mbs, frac_above, masscut=masscut)
    np.savetxt(os.path.join(basepath, "analysis/fabove_histories_%g.txt"%(masscut/1e5)), fabove_histories, fmt="%.6e")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        basepath = ""
        a_target = None
    elif len(sys.argv) == 2:
        basepath = ""
        a_target = float(sys.argv[1])
    elif len(sys.argv) == 3:
        basepath = sys.argv[2]
        a_target = float(sys.argv[1])

    save_histories_most_massive_halos(basepath, a_target, agecut=50.0)