"""
BSD 3-Clause License
Copyright (c) 2024-2025 Yingtian Chen
All rights reserved.
"""

import os
import sys
import subprocess

if __name__ == '__main__':

    restart = False
    particle_type = "N-BODY_0"
    num_readers = 1
    num_writers = 2
    subpath_list = [
        # "mh2e12_km/1113433",
        # "mh2e12_km/1113673",
        # "mh2e12_km/1113831",
        # "mh2e12_km/1117028",
        # "mh2e12_km/1117038",
        # "mh3e12_km/1116392",
        # "mh3e12_km/1117206",
        # "mh3e12_km/1118550",
        # "mh5e12_km/1112809",
        # "mh5e12_km/1116287",
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

    args = sys.argv[1:]

    if len(args) > 5:
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
        z = float(args[4])

    scriptpath = "/home1/08199/tg874988/art_analysis_scripts/art_analysis_scripts/"
    basepath = "/scratch/08199/tg874988/art_simulations/hydro/"

    procs = []

    for subpath in subpath_list:
        cmd = [
            "mpirun", "-n", "%d"%(num_readers+num_writers+1), 
            "python", os.path.join(scriptpath, "halofinder.py"), 
            "%d"%int(restart), "N-BODY_0", "%d"%num_readers, "%d"%num_writers, 
            os.path.join(basepath, subpath, "run"), "%f"%z
        ]
        p = subprocess.Popen(cmd)
        procs.append(p)

    for p in procs:
        p.wait()