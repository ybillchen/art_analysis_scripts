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

def sfh(ts, branches, agecut=50.0):
    storage = {}

    for store, ds in ts.piter(storage=storage):
        scale = 1 / (ds.current_redshift+1)
        tnow  = ds.current_time.to_value("Myr")

        out = (scale, tnow)

        for branch in branches:
            idx = np.where(np.abs(branch[:,0]-scale)<5e-5)[0]
            if len(idx) == 0:
                out += (-1,)
                continue

            assert len(idx) == 1

            line = branch[idx[0]]
            hpos = line[17:20] * ds.arr(1, "Mpccm/h")
            rvir = line[11] * ds.arr(1, "kpccm/h")
            sp = ds.sphere(hpos, rvir)

            ms_i = sp[("STAR", "INITIAL_MASS")].to_value("Msun")
            tform = sp[("STAR", "creation_time")].to_value("Myr")
            tage = tnow - tform
            mask = tage < agecut
            ms_cut = np.sum(ms_i[mask])
            out += (1e-6*ms_cut/agecut,)

        store.result = out

    return np.array(list(storage.values()))

def save_sfh_most_massive_halos(basepath, a_target):

    tree = np.loadtxt(os.path.join(basepath, "rockstar_halos/trees/tree_0_0_0.dat"), skiprows=48)
    ts = yt.load(os.path.join(basepath, "out/snap_a*.art"))

    mbs = find_most_massive_halos(tree, a_target, num=2)
    mass_histories_50 = sfh(ts, mbs, agecut=50.0)

    print(mass_histories_50)

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

    save_sfh_most_massive_halos(basepath, a_target)