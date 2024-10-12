"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import numpy as np
import yt

import yt
# yt.enable_parallelism()
import ytree

def art2skirt(ds, region, center, savenamebase):
    print("loading star positions")
    xs = region[("STAR", "POSITION_X")].to_value("pc") - center[0].to_value("pc")
    ys = region[("STAR", "POSITION_Y")].to_value("pc") - center[1].to_value("pc")
    zs = region[("STAR", "POSITION_Z")].to_value("pc") - center[2].to_value("pc")
    es = np.zeros_like(xs)
    print("loading star velocities")
    vxs = region[("STAR", "VELOCITY_X")].to_value("km/s")
    vys = region[("STAR", "VELOCITY_Y")].to_value("km/s")
    vzs = region[("STAR", "VELOCITY_Z")].to_value("km/s")
    print("loading star masses, metallicities, and ages")
    ms = region[("STAR", "INITIAL_MASS")].to_value("Msun")
    Zs = (region[('STAR', 'METALLICITY_SNII')]+region[('STAR', 'METALLICITY_SNIa')]+region[('STAR', 'METALLICITY_AGB')]).to_value("1")
    ts = (ds.current_time - region[("STAR", "creation_time")]).to_value("Gyr")

    savenames = savenamebase + "_star.txt"
    headers = (
        "%s.txt: import file for particle source\n"%savenames + 
        "Column 1: position x (pc)\n"
        "Column 2: position y (pc)\n"
        "Column 2: position z (pc)\n"
        "Column 4: smoothing length (pc)\n"
        "Column 5: velocity vx (km/s)\n"
        "Column 6: velocity vy (km/s)\n"
        "Column 7: velocity vz (km/s)\n"
        "Column 8: mass (Msun)\n"
        "Column 9: metallicity (1)\n"
        "Column 10: age (Gyr)\n"
        )
    outs = np.column_stack([xs, ys, zs, es, vxs, vys, vzs, ms, Zs, ts])
    np.savetxt(savenames, outs, header=headers, fmt="%.6e")

    print("loading gas positions")
    xg = region[("gas", "x")].to_value("pc") - center[0].to_value("pc")
    yg = region[("gas", "y")].to_value("pc") - center[1].to_value("pc")
    zg = region[("gas", "z")].to_value("pc") - center[2].to_value("pc")
    dx = region[("gas", "dx")].to_value("pc")
    x0g = xg - 0.5*dx
    y0g = yg - 0.5*dx
    z0g = zg - 0.5*dx
    x1g = xg + 0.5*dx
    y1g = yg + 0.5*dx
    z1g = zg + 0.5*dx
    print("loading gas masses, metallicities, and temperature")
    mg = region[("gas", "mass")].to_value("Msun")
    Zg = region[("gas", "metallicity")].to_value("1")
    Tg = region[("gas", "temperature")].to_value("K")
    print("loading gas velocities")
    vxg = region[("gas", "velocity_x")].to_value("km/s")
    vyg = region[("gas", "velocity_y")].to_value("km/s")
    vzg = region[("gas", "velocity_z")].to_value("km/s")

    savenameg = savenamebase + "_gas.txt"
    headerg = (
        "%s.txt: import file for cell media -- dust\n"%savenameg + 
        "column 1: xmin (pc)\n"
        "column 2: ymin (pc)\n"
        "column 3: zmin (pc)\n"
        "column 4: xmax (pc)\n"
        "column 5: ymax (pc)\n"
        "column 6: zmax (pc)\n"
        "Column 7: gas mass (Msun/pc3)\n"
        "Column 8: metallicity (1)\n"
        "Column 9: temperature (K)\n"
        "Column 10: velocity vx (km/s)\n"
        "Column 11: velocity vy (km/s)\n"
        "Column 12: velocity vz (km/s)\n"
        )
    outg = np.column_stack([x0g, y0g, z0g, x1g, y1g, z1g, mg, Zg, Tg, vxg, vyg, vzg])
    np.savetxt(savenameg, outg, header=headerg, fmt="%.6e")


if __name__ == "__main__":
    # assume that this script is executed in run/
    scale_a = 0.1708

    ds = yt.load("out/snap_a%.4f.art"%scale_a)
    a = ytree.load("rockstar_halos/trees/arbor/arbor.h5")

    tree = a[0] # a[0] should be the most massive 
    center = tree["position"].to("kpc") * scale_a # note: ytree cannot deal with comoving units

    radius = 100.0 * ds.units.kpc # in kpc
    box = [-radius, -radius, 2*radius, 2*radius]
    region = [
        center[0]-radius, center[1]-radius, center[2]-radius, 
        center[0]+radius, center[1]+radius, center[2]+radius]

    region = ds.box(region[:3], region[3:])
    art2skirt(ds, region, center, "analysis/skirt_a%.4f"%scale_a)