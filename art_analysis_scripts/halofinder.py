"""
BSD 3-Clause License
Copyright (c) 2024-2025 Yingtian Chen
All rights reserved.
"""

import os
import sys
# from multiprocessing import Process

import numpy as np
import yt

yt.enable_parallelism()
from yt_astro_analysis.halo_analysis import HaloCatalog

def rockstar_halofinder(base="", restart=False, 
    particle_type="N-BODY_0", num_readers=3, num_writers=4):

    ts = yt.load(os.path.join(base, "out/snap_a*.art"))

    for ds in ts:
        # https://yt-astro-analysis.readthedocs.io/en/latest/Installation.html
        ds.parameters["format_revision"] = 2

    hc = HaloCatalog(data_ds=ts, finder_method="rockstar", 
        finder_kwargs={
            "num_readers": num_readers,
            "num_writers": num_writers,
            "particle_type": particle_type,
            "outbase": os.path.join(base, "rockstar_halos"),
            "restart": restart
            })

    hc.create()

def rockstar_halofinder_at_z(z, base="", restart=False, 
    particle_type="N-BODY_0", num_readers=3, num_writers=4):

    ts = yt.load(os.path.join(base, "out/snap_a*.art"))

    z_list = []

    for ds in ts:
        # https://yt-astro-analysis.readthedocs.io/en/latest/Installation.html
        ds.parameters["format_revision"] = 2
        z_list.append(ds.current_redshift)

    z_list = np.array(z_list)

    idx = np.argmin(np.abs(z-z_list))

    hc = HaloCatalog(data_ds=ts[idx], finder_method="rockstar", 
        finder_kwargs={
            "num_readers": num_readers,
            "num_writers": num_writers,
            "particle_type": particle_type,
            "outbase": os.path.join(base, "rockstar_halos_at_z"),
            "restart": restart
            })

    hc.create()

if __name__ == "__main__":

    restart = False
    particle_type = "N-BODY_0"
    num_readers = 1
    num_writers = 1
    base = ""
    z = -1.0

    args = sys.argv[1:]

    if len(args) > 6:
        raise ValueError("Too many arguments")

    if len(args) > 0:
        restart = bool(int(args[0]))
    if len(args) > 1:
        particle_type = args[1]
    if len(args) > 2:
        num_readers = int(args[2])
    if len(args) > 3:
        num_writers = int(args[3])
    if len(args) > 4:
        base = args[4]
    if len(args) > 5:
        z = float(args[5])

    if z > -0.5:
        rockstar_halofinder_at_z(
            z=z,
            base=base,
            restart=restart, 
            particle_type=particle_type, 
            num_readers=num_readers, 
            num_writers=num_writers
        )
    else:
        rockstar_halofinder(
            base=base,
            restart=restart, 
            particle_type=particle_type, 
            num_readers=num_readers, 
            num_writers=num_writers
        )

    # basepath = "/scratch/08199/tg874988/art_simulations/hydro/"
    # subpath_list = [
    #     "mh2e12_km/1113433",
    #     "mh2e12_km/1113673",
    #     "mh2e12_km/1113831",
    #     "mh2e12_km/1117028",
    #     "mh2e12_km/1117038",
    #     "mh3e12_km/1116392",
    #     "mh3e12_km/1117206",
    #     "mh3e12_km/1118550",
    #     "mh5e12_km/1112809",
    #     "mh5e12_km/1116287",
    #     "mh2e12_p12/1113433",
    #     "mh2e12_p12/1113673",
    #     "mh2e12_p12/1113831",
    #     "mh2e12_p12/1117028",
    #     "mh2e12_p12/1117038",
    #     "mh3e12_p12/1116392",
    #     "mh3e12_p12/1117206",
    #     "mh3e12_p12/1118550",
    #     "mh5e12_p12/1112809",
    #     "mh5e12_p12/1116287",
    # ]

    # findall(
    #     basepath=basepath, 
    #     subpath_list=subpath_list, 
    #     restart=restart, 
    #     particle_type=particle_type, 
    #     num_readers=num_readers, 
    #     num_writers=num_writers
    # )
