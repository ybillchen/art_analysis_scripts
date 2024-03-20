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
    snap_last = yt.load("out/snap_a1.0017.art")
    a = ytree.load("rockstar_halos/trees/arbor/arbor.h5")
    trees = list(a[:])

    box = [-0.5, -0.5, 1.0, 1.0]

    for tree in ytree.parallel_trees(trees):
        if tree["mass"] > a.quan(4.8e12, "Msun") and \
            tree["mass"] < a.quan(5.2e12, "Msun"):
            root = tree.find_root()

            hid = root["uid"]
            center = root["position"]
            # radius = root["virial_radius"]

            sp = snap_last.sphere(center, (np.min(box[2:]), "Mpc"))

            fig, ax0 = plt.subplots()

            x = sp[("N-BODY", "POSITION_X")] - center[0]
            y = sp[("N-BODY", "POSITION_Y")] - center[1]

            pp.prj(ax0, x.to("Mpc"), y.to("Mpc"), 
                box=box, vmin=3, vmax=5, log=True, 
                capacity=64, max_level=10, cmap=plt.cm.magma)

            ax0.set_xlim(box[0], box[0]+box[2])
            ax0.set_ylim(box[1], box[1]+box[3])

            ax0.set_aspect("equal")
            plt.savefig("analysis/prj_%d.png"%hid, 
                bbox_inches ="tight", pad_inches=0.05)