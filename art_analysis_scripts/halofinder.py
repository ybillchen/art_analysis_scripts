"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import yt

yt.enable_parallelism()
from yt_astro_analysis.halo_analysis import HaloCatalog

if __name__ == "__main__":

	ts = yt.load("out/snap_a*.art")

	for ds in ts:
		# https://yt-astro-analysis.readthedocs.io/en/latest/Installation.html
	    ds.parameters["format_revision"] = 2

	hc = HaloCatalog(data_ds=ts, finder_method="rockstar", 
		finder_kwargs={
			"num_readers": 1,
			"particle_type": "N-BODY",
			"restart": False
			})

	hc.create()