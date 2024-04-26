"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import numpy as 
import tqdm

def prj(ds, center, size, level=10, prj_x="x", prj_y="y", field="density", unit="Msun/pc**2"):
    """
    generate quadtree-like projection for gas
    effective volume weighted projection
    ds: ARTIODataset
    center: [x0, y0, z0] in code_length
    """

    dx_level = 2**-level # in code_length

    N_left = np.floor((center[0]-size/2)/dx_level)
    N_right = np.ceil((center[0]+size/2)/dx_level)

    N = int(N_right-N_left)
    mesh = np.zeros((N, N)) # pixel mesh

    # the smallest integer region that covers the box
    region = [
        N_left*dx_level*ds.units.code_length,
        N_left*dx_level*ds.units.code_length,
        N_left*dx_level*ds.units.code_length,
        N_right*dx_level*ds.units.code_length,
        N_right*dx_level*ds.units.code_length,
        N_right*dx_level*ds.units.code_length]

    d = ds.box(region[:3], region[3:])

    x = d["gas", prj_x].to("code_length").value
    y = d["gas", prj_y].to("code_length").value
    dx = d["gas", "dx"].to("code_length").value
    z = d["gas", field].to(unit).value


    for i in tqdm(range(len(x))):
        if dx[i] <= dx_level:
            # the cell is within a pixel
            ix = np.floor(x[i]/dx_level).astype(int)
            iy = np.floor(y[i]/dx_level).astype(int)
            normalize = dx[i]**3 / (N*dx_level**3) # volume weighted
            mesh[ix, iy] += z[i] * normalize
        else:
            # the cell covers many pixels
            ix0 = np.rint((x[i]-dx[i]/2)/dx_level).astype(int)
            iy0 = np.rint((y[i]-dx[i]/2)/dx_level).astype(int)
            ix1 = np.rint((x[i]+dx[i]/2)/dx_level).astype(int)
            iy1 = np.rint((y[i]+dx[i]/2)/dx_level).astype(int)
            normalize = dx[i] * dx_level**2 / (N*dx_level**3) # volume weighted
            mesh[ix0:ix1, iy0:iy1] += z[i] * normalize

    return mesh

if __name__ == "__main__":
    
    import matplotlib.pyplot as plt
    import yt

    ds = yt.load("out/snap_a0.0862.art")
    d = ds.all_data()
    x0 = d["N-BODY_0", "POSITION_X"].to("code_length").median().value
    y0 = d["N-BODY_0", "POSITION_Y"].to("code_length").median().value
    z0 = d["N-BODY_0", "POSITION_Z"].to("code_length").median().value

    mesh = prj(ds, [x0, y0, z0], 1.0, level=10, prj_x="x", prj_y="y", field="density", unit="Msun/pc**2")

    fig, ax0 = plt.subplots()

    ax0.imshow(np.log10(mesh))

    ax0.set_xlabel(r"x (code_length)")
    ax0.set_ylabel(r"y (code_length)")
    ax0.set_aspect("equal")

    plt.savefig("analysis/prj.png", bbox_inches ="tight", pad_inches=0.05)

