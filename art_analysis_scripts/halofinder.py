"""
BSD 3-Clause License
Copyright (c) 2024-2025 Yingtian Chen
All rights reserved.
"""

import os
import sys

import yt

yt.enable_parallelism()
from yt_astro_analysis.halo_analysis import HaloCatalog

def rockstar_halofinder(base="", restart=False, 
    particle_type="N-BODY_0", num_readers=16, num_writers=16):

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


def findall(basepath, subpath_list, restart=False, 
    particle_type="N-BODY_0", num_readers=1, num_writers=1):

    num_groups = len(subpath_list)
    group_size = num_readers + num_writers + 1
    total_cores = group_size * num_groups

    processes = []

    for i, subpath in enumerate(subpath_list):
        base = os.path.join(basepath, subpath)
        cores = list(range(i * group_size, (i + 1) * group_size))
        p = mp.Process(
            target=worker, 
            args=(base, restart, particle_type, num_readers, num_writers)
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

if __name__ == "__main__":

    if len(sys.argv) == 1:
        restart = False
        particle_type = "N-BODY_0"
        num_readers = 1
        num_writers = 1
    elif len(sys.argv) == 2:
        restart = bool(int(sys.argv[1]))
        particle_type = "N-BODY_0"
        num_readers = 1
        num_writers = 1
    elif len(sys.argv) == 3:
        restart = bool(int(sys.argv[1]))
        particle_type = sys.argv[2]
        num_readers = 1
        num_writers = 1
    elif len(sys.argv) == 4:
        restart = bool(int(sys.argv[1]))
        particle_type = sys.argv[2]
        num_readers = int(sys.argv[3])
        num_writers = 1
    elif len(sys.argv) == 5:
        restart = bool(int(sys.argv[1]))
        particle_type = sys.argv[2]
        num_readers = int(sys.argv[3])
        num_writers = int(sys.argv[4])
    else:
        raise Exception("Invalid number of arguments")

    # rockstar_halofinder(
    #     restart=restart, 
    #     particle_type=particle_type, 
    #     num_readers=num_readers, 
    #     num_writers=num_writers
    # )

    basepath = "/scratch/08199/tg874988/art_simulations/hydro/"
    subpath_list = [
        "m2e12_km/1113433",
        "m2e12_km/1113673",
        "m2e12_km/1113831",
        "m2e12_km/1117028",
        "m2e12_km/1117038",
        "m3e12_km/1116392",
        "m3e12_km/1117206",
        "m3e12_km/1118550",
        "m5e12_km/1112809",
        "m5e12_km/1116287",
        "m2e12_p12/1113433",
        "m2e12_p12/1113673",
        "m2e12_p12/1113831",
        "m2e12_p12/1117028",
        "m2e12_p12/1117038",
        "m3e12_p12/1116392",
        "m3e12_p12/1117206",
        "m3e12_p12/1118550",
        "m5e12_p12/1112809",
        "m5e12_p12/1116287",
    ]

    findall(
        basepath=basepath, 
        subpath_list=subpath_list, 
        restart=restart, 
        particle_type=particle_type, 
        num_readers=num_readers, 
        num_writers=num_writers
    )
