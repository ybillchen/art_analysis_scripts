"""
BSD 3-Clause License
Copyright (c) 2024-2025 Yingtian Chen
All rights reserved.
"""

import os
import subprocess

if __name__ == '__main__':

    basepath = "/scratch/08199/tg874988/art_simulations/hydro/"
    subpath_list = [
        "mh2e12_km/1113433",
        "mh2e12_km/1113673",
        "mh2e12_km/1113831",
        "mh2e12_km/1117028",
        "mh2e12_km/1117038",
        "mh3e12_km/1116392",
        "mh3e12_km/1117206",
        "mh3e12_km/1118550",
        "mh5e12_km/1112809",
        "mh5e12_km/1116287",
        "mh2e12_p12/1113433",
        "mh2e12_p12/1113673",
        "mh2e12_p12/1113831",
        "mh2e12_p12/1117028",
        "mh2e12_p12/1117038",
        "mh3e12_p12/1116392",
        "mh3e12_p12/1117206",
        "mh3e12_p12/1118550",
        "mh5e12_p12/1112809",
        "mh5e12_p12/1116287",
    ]

    procs = []

    for subpath in subpath_list:
        cmd = [
            "mpirun", "-n", "3", "python", "halofinder.py", 
            "0", "N-BODY_0", "1", "1", os.path.join(basepath, subpath, "run")
        ]
        p = subprocess.Popen(cmd)
        procs.append(p)

    for p in procs:
        p.wait()