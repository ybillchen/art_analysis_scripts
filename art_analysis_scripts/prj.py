"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import sys
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
    factor = 0.5

    N0 = {}
    N0["x"] = np.floor((center[0]-factor*size)/dx_level)
    N0["y"] = np.floor((center[1]-factor*size)/dx_level)
    N0["z"] = np.floor((center[2]-factor*size)/dx_level)
    N1 = {}
    N1["x"] = np.ceil((center[0]+factor*size)/dx_level)
    N1["y"] = np.ceil((center[1]+factor*size)/dx_level)
    N1["z"] = np.ceil((center[2]+factor*size)/dx_level)

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

    x = d["gas", prj_x].to_value("code_length")
    y = d["gas", prj_y].to_value("code_length")
    dx = d["gas", "dx"].to_value("code_length")
    z = d["gas", field].to_value(unit)


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

    import matplotlib
    matplotlib.use("agg")
    import matplotlib.pyplot as plt
    import yt

    assert len(sys.argv) >= 3

    basepath = sys.argv[1]
    a = float(sys.argv[2])

    ds = yt.load(basepath+"run/out/snap_a%.4f.art"%a)
    d = ds.all_data()
    # x0 = np.median(d["N-BODY_0", "POSITION_X"].to_value("code_length"))
    # y0 = np.median(d["N-BODY_0", "POSITION_Y"].to_value("code_length"))
    # z0 = np.median(d["N-BODY_0", "POSITION_Z"].to_value("code_length"))

    density = d["gas", "density"]
    wdens = np.where(density == np.max(density))
    x0 = d["gas", "x"][wdens][0].to_value("code_length")
    y0 = d["gas", "y"][wdens][0].to_value("code_length")
    z0 = d["gas", "z"][wdens][0].to_value("code_length")

    # x0 = 128
    # y0 = 128
    # z0 = 128
    size = 0.125

    unit = "kpc"
    unit_convert = (1*ds.units.code_length).to_value(unit)

    fig, [ax0, ax1] = plt.subplots(1,2)

    # gas
    mesh, region = prj(ds, [x0, y0, z0], size, level=12, prj_x="x", prj_y="y", field="density", unit="Msun/pc**3")
    ax0.imshow(np.log10(mesh.T), origin="lower", 
        extent=[region[0].to(unit),region[3].to(unit),region[1].to(unit),region[4].to(unit)])
    mesh, region = prj(ds, [x0, y0, z0], size, level=12, prj_x="x", prj_y="z", field="density", unit="Msun/pc**3")
    ax1.imshow(np.log10(mesh.T), origin="lower", 
        extent=[region[0].to(unit),region[3].to(unit),region[2].to(unit),region[5].to(unit)])

    # stars
    d = ds.box(region[:3], region[3:])
    ax0.scatter(d["STAR", "POSITION_X"].to(unit),d["STAR", "POSITION_Y"].to(unit), 
        fc='w', ec='none', s=d["STAR", "MASS"].to("Msun")/1e5)
    ax1.scatter(d["STAR", "POSITION_X"].to(unit),d["STAR", "POSITION_Z"].to(unit), 
        fc='w', ec='none', s=d["STAR", "MASS"].to("Msun")/1e5)

    ax0.set_xlabel(r"x (%s)"%unit)
    ax1.set_xlabel(r"x (%s)"%unit)
    ax0.set_ylabel(r"y (%s)"%unit)
    ax1.set_ylabel(r"z (%s)"%unit)
    ax0.set_aspect("equal")
    ax1.set_aspect("equal")
    ax0.set_xlim((x0-0.5*size)*unit_convert, (x0+0.5*size)*unit_convert)
    ax1.set_xlim((x0-0.5*size)*unit_convert, (x0+0.5*size)*unit_convert)
    ax0.set_ylim((y0-0.5*size)*unit_convert, (y0+0.5*size)*unit_convert)
    ax1.set_ylim((z0-0.5*size)*unit_convert, (z0+0.5*size)*unit_convert)

    plt.tight_layout()
    plt.savefig("outputs/prj/prj_a%.4f.png"%a, bbox_inches ="tight", pad_inches=0.05, dpi=300)

