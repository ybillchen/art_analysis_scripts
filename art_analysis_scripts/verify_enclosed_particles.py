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

    mass0 = sp[("N-BODY_0", "MASS")]
    mass1 = sp[("N-BODY_1", "MASS")]
    mass2 = sp[("N-BODY_2", "MASS")]
    mass3 = sp[("N-BODY_3", "MASS")]
    mass4 = sp[("N-BODY_4", "MASS")]

    print("# of N-BODY_0: %d, total mass: %.2e Msun"%(
        len(mass0),np.sum(mass0).to("Msun")))
    print("# of N-BODY_1: %d, total mass: %.2e Msun"%(
        len(mass1),np.sum(mass1).to("Msun")))
    print("# of N-BODY_2: %d, total mass: %.2e Msun"%(
        len(mass2),np.sum(mass2).to("Msun")))
    print("# of N-BODY_3: %d, total mass: %.2e Msun"%(
        len(mass3),np.sum(mass3).to("Msun")))
    print("# of N-BODY_4: %d, total mass: %.2e Msun"%(
        len(mass4),np.sum(mass4).to("Msun")))

if __name__ == "__main__":
    verify_enclosed_from_z3()