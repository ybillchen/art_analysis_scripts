"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import numpy as np
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt

import yt
yt.enable_parallelism()
import ytree

import prj_plotter as pp

if __name__ == "__main__":
    # assume that this script is executed in run/
    # snap_last = yt.load("out/snap_a1.0017.art")
    snap_last = yt.load("out/snap_a0.2510.art")
    a = ytree.load("rockstar_halos/trees/arbor/arbor.h5")
    trees = list(a[:])

    radius = 250.0  # in kpc
    box = [-radius, -radius, 2*radius, 2*radius]

    for tree in ytree.parallel_trees(trees, save_every=False):
        if tree["mass"] > a.quan(4.8e12, "Msun") and \
            tree["mass"] < a.quan(5.2e12, "Msun"):
            root = tree.find_root()
            hid = root["uid"]

            prog = list(tree["prog"])
            redshift_prog = np.array(tree["prog", "redshift"])
            idx = np.where((redshift_prog>2.95)&(redshift_prog<3.05))
            assert len(idx[0]) == 1
            root = prog[idx[0][0]]

            if root['pid'] >= 0: # must be the central halo
                continue

            redshift = root['redshift']
            # if redshift > 0: # must be the last snapshot
            #     continue
            scale_a = 1.0/(1.0+redshift)

            # in ytree, units are always comoving 
            # need to manually convert to physical
            center = root["position"].to("kpc") * scale_a
            rvir = root["virial_radius"].to("kpc") * scale_a

            sp = snap_last.sphere(center, (radius, "kpc"))

            fig, ax0 = plt.subplots()

            x = sp[("N-BODY", "POSITION_X")].to("kpc") - center[0]
            y = sp[("N-BODY", "POSITION_Y")].to("kpc") - center[1]

            pp.prj(ax0, x, y, 
                box=box, vmin=-4, vmax=1, log=True, capacity=64, 
                max_level=10, cmap=plt.cm.magma)

            vir_circ = plt.Circle((0.0, 0.0), rvir, ec='w', fc='none')
            ax0.add_patch(vir_circ)

            ax0.set_xlim(box[0], box[0]+box[2])
            ax0.set_ylim(box[1], box[1]+box[3])
            ax0.set_xlabel("x (kpc)")
            ax0.set_ylabel("y (kpc)")
            ax0.set_aspect("equal")

            plt.savefig("analysis/5e12/prj_z3_%d.png"%hid, 
                bbox_inches ="tight", pad_inches=0.05)