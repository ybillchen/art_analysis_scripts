"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import numpy as np

import yt
# yt.enable_parallelism()
import ytree

def verify_enclosed_from_z3(factor=1):
    snap = yt.load("out/snap_a0.2510.art")
    # snap_first = yt.load("out/snap_a0.0100.art").all_data()
    # pids_first = snap_first[("N-BODY", "PID")].astype(int)
    a = ytree.load("rockstar_halos/trees/arbor/arbor.h5")
    trees = list(a[:])

    tree = trees[np.argmax(a["mass"])]

    prog = list(tree["prog"])
    redshift_prog = np.array(tree["prog", "redshift"])
    idx = np.where((redshift_prog>2.95)&(redshift_prog<3.05))
    assert len(idx[0]) == 1
    node = prog[idx[0][0]]

    redshift = node['redshift']
    scale_a = 1.0/(1.0+redshift)

    # in ytree, units are always comoving 
    # need to manually convert to physical
    center = node["position"].to("kpc") * scale_a
    rvir = node["virial_radius"].to("kpc") * scale_a

    sp = snap.sphere(center, rvir * factor)

    print("# of N-BODY_0: %d"%len(sp[("N-BODY_0", "PID")]))
    print("# of N-BODY_1: %d"%len(sp[("N-BODY_1", "PID")]))
    print("# of N-BODY_2: %d"%len(sp[("N-BODY_2", "PID")]))
    print("# of N-BODY_3: %d"%len(sp[("N-BODY_3", "PID")]))
    print("# of N-BODY_4: %d"%len(sp[("N-BODY_4", "PID")]))

if __name__ == "__main__":
    zoom_particles_from_z3()