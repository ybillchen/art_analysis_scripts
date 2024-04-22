"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import numpy as np
from scipy.spatial import ConvexHull

import yt
# yt.enable_parallelism()
import ytree

def zoom_particles_from_a(hid, a_target, factor=4):
    snap = yt.load("out/snap_a%.4f.art"%a_target)
    ds_first = yt.load("out/snap_a0.0100.art")
    snap_first = ds_first.all_data()
    pids_first = snap_first[("N-BODY", "PID")].astype(int)
    a = ytree.load("rockstar_halos/trees/arbor/arbor.h5")
    trees = list(a[:])

    idx = np.where(np.array(a["uid"], dtype=int)==hid)
    assert len(idx[0]) == 1
    tree = trees[idx[0][0]]

    prog = list(tree["prog"])
    redshift_prog = np.array(tree["prog", "redshift"])
    idx = np.where(
                (redshift_prog>(1/a_target-1)-0.001)&
                (redshift_prog<(1/a_target-1)+0.001))
    assert len(idx[0]) == 1
    node = prog[idx[0][0]]

    redshift = node['redshift']
    scale_a = 1.0/(1.0+redshift)

    # in ytree, units are always comoving 
    # need to manually convert to physical
    center = node["position"].to("kpc") * scale_a
    rvir = node["virial_radius"].to("kpc") * scale_a

    sp = snap.sphere(center, rvir * factor)
    pids = sp[("N-BODY", "PID")].astype(int)

    xy, x_ind, y_ind = np.intersect1d(pids, pids_first, 
        assume_unique=True, return_indices=True)
    assert len(xy) == len(pids)

    x = snap_first[("N-BODY", "POSITION_X")][y_ind].to("unitary").value
    y = snap_first[("N-BODY", "POSITION_Y")][y_ind].to("unitary").value
    z = snap_first[("N-BODY", "POSITION_Z")][y_ind].to("unitary").value

    print("x range: %.3f - %.3f"%(np.min(x), np.max(x)))
    print("y range: %.3f - %.3f"%(np.min(y), np.max(y)))
    print("z range: %.3f - %.3f"%(np.min(z), np.max(z)))

    out = np.column_stack([x,y,z])
    np.savetxt("analysis/2e12/zoom_particles_from_a%.4f_%d.txt"%(a_target,hid), 
        out, fmt="%.6f %.6f %.6f")

    hull = ConvexHull(out)
    np.savetxt("analysis/2e12/zoom_particles_simplices_from_a%.4f_%d.txt"%(a_target,hid), 
        out[hull.simplices], fmt="%.6f %.6f %.6f")

if __name__ == "__main__":
    hid = 1117028
    a_target = 0.2501
    zoom_particles_from_a(hid=hid, a_target=a_target)