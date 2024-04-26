"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import numpy as np
from tqdm import tqdm

def prj(ds, center, size, level=10, prj_x="x", prj_y="y", field="density", unit="Msun/pc**3"):
    """
    generate quadtree-like projection for gas
    effective volume weighted projection
    ds: ARTIODataset
    center: [x0, y0, z0] in code_length
    """

    dx_level = 2**-level # in code_length

    N0 = {}
    N0["x"] = np.floor((center[0]-size/2)/dx_level)
    N0["y"] = np.floor((center[1]-size/2)/dx_level)
    N0["z"] = np.floor((center[2]-size/2)/dx_level)
    N1 = {}
    N1["x"] = np.ceil((center[0]+size/2)/dx_level)
    N1["y"] = np.ceil((center[1]+size/2)/dx_level)
    N1["z"] = np.ceil((center[2]+size/2)/dx_level)

    N = int(np.max((N1["x"]-N0["x"],N1["y"]-N0["y"],N1["z"]-N0["z"])))
    mesh = np.zeros((N, N)) # pixel mesh
    N1["x"] = N0["x"] + N # update to the longest side
    N1["y"] = N0["y"] + N
    N1["z"] = N0["z"] + N

    # the smallest integer region that covers the box
    region = [
        N0["x"]*dx_level*ds.units.code_length,
        N0["y"]*dx_level*ds.units.code_length,
        N0["z"]*dx_level*ds.units.code_length,
        N1["x"]*dx_level*ds.units.code_length,
        N1["y"]*dx_level*ds.units.code_length,
        N1["z"]*dx_level*ds.units.code_length]

    d = ds.box(region[:3], region[3:])

    x = d["gas", prj_x].to("code_length").value
    y = d["gas", prj_y].to("code_length").value
    dx = d["gas", "dx"].to("code_length").value
    z = d["gas", field].to(unit).value


    for i in tqdm(range(len(x))):
        if dx[i] <= dx_level:
            # the cell is within a pixel
            ix = np.floor(x[i]/dx_level-N0[prj_x]).astype(int)
            iy = np.floor(y[i]/dx_level-N0[prj_y]).astype(int)
            normalize = dx[i]**3 / (N*dx_level**3) # volume weighted
            mesh[ix, iy] += z[i] * normalize
        else:
            # the cell covers many pixels
            ix0 = np.rint((x[i]-dx[i]/2)/dx_level-N0[prj_x]).astype(int)
            iy0 = np.rint((y[i]-dx[i]/2)/dx_level-N0[prj_y]).astype(int)
            ix1 = np.rint((x[i]+dx[i]/2)/dx_level-N0[prj_x]).astype(int)
            iy1 = np.rint((y[i]+dx[i]/2)/dx_level-N0[prj_y]).astype(int)
            normalize = dx[i] * dx_level**2 / (N*dx_level**3) # volume weighted
            mesh[ix0:ix1, iy0:iy1] += z[i] * normalize

    return mesh, region

if __name__ == "__main__":
    
    import matplotlib.pyplot as plt
    import yt

    ds = yt.load("out/snap_a0.0862.art")
    # d = ds.all_data()
    # x0 = np.median(d["N-BODY_0", "POSITION_X"].to("code_length").value)
    # y0 = np.median(d["N-BODY_0", "POSITION_Y"].to("code_length").value)
    # z0 = np.median(d["N-BODY_0", "POSITION_Z"].to("code_length").value)

    x0 = 127.25
    y0 = 128.75
    z0 = 128.5

    fig, [ax0, ax1] = plt.subplots(1,2)

    mesh, region = prj(ds, [x0, y0, z0], 1.0, level=10, prj_x="x", prj_y="y", field="density", unit="Msun/pc**3")
    ax0.imshow(np.log10(mesh.T), origin="lower", extent=[region[0],region[3],region[1],region[4]])
    mesh, region = prj(ds, [x0, y0, z0], 1.0, level=10, prj_x="x", prj_y="z", field="density", unit="Msun/pc**3")
    ax1.imshow(np.log10(mesh.T), origin="lower", extent=[region[0],region[3],region[2],region[5]])

    ax0.set_xlabel(r"x (code_length)")
    ax1.set_xlabel(r"x (code_length)")
    ax0.set_ylabel(r"y (code_length)")
    ax1.set_ylabel(r"z (code_length)")
    ax0.set_aspect("equal")
    ax1.set_aspect("equal")

    plt.savefig("analysis/prj.png", bbox_inches ="tight", pad_inches=0.05, dpi=300)

