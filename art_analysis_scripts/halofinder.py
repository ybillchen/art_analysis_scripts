"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
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

if __name__ == "__main__":

    if len(sys.argv) == 1:
        restart = False
        particle_type = "N-BODY_0"
        num_readers = 16
        num_writers = 16
    elif len(sys.argv) == 2:
        restart = bool(int(sys.argv[1]))
        particle_type = "N-BODY_0"
        num_readers = 16
        num_writers = 16
    elif len(sys.argv) == 3:
        restart = bool(int(sys.argv[1]))
        particle_type = sys.argv[2]
        num_readers = 16
        num_writers = 16
    elif len(sys.argv) == 4:
        restart = bool(int(sys.argv[1]))
        particle_type = sys.argv[2]
        num_readers = int(sys.argv[3])
        num_writers = 16
    elif len(sys.argv) == 5:
        restart = bool(int(sys.argv[1]))
        particle_type = sys.argv[2]
        num_readers = int(sys.argv[3])
        num_writers = int(sys.argv[4])
    else:
        raise Exception("Invalid number of arguments")

    rockstar_halofinder(
        restart=restart, 
        particle_type=particle_type, 
        num_readers=num_readers, 
        num_writers=num_writers
    )
