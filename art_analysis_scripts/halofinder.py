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

def rockstar_halofinder(restart=0, base="", num_readers=8, 
	particle_type="N-BODY"):

	ts = yt.load(os.path.join(base, "out/snap_a*.art"))

	for ds in ts:
		# https://yt-astro-analysis.readthedocs.io/en/latest/Installation.html
	    ds.parameters["format_revision"] = 2

	hc = HaloCatalog(data_ds=ts, finder_method="rockstar", 
		finder_kwargs={
			"num_readers": num_readers,
			"particle_type": particle_type,
			"outbase": os.path.join(base, "rockstar_halos"),
			"restart": bool(restart)
			})

	hc.create()

if __name__ == "__main__":

    if len(sys.argv) != 2:
        restart = 0
    else:
        restart = sys.argv[1]

	rockstar_halofinder(restart=restart)