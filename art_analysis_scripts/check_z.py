"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import os
import time
import re

import numpy as np

def find_matching_file(folder_path):
    pattern = re.compile(r"^stdout_.+_(\d+)$")
    best_file = None
    max_num = -1
    for fname in os.listdir(folder_path):
        full_path = os.path.join(folder_path, fname)
        if os.path.isfile(full_path):
            match = pattern.match(fname)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                        best_file = full_path
                except ValueError:
                    continue
    return best_file

def scan_subfolders(root_folder):
    results = {}
    for entry in sorted(os.listdir(root_folder)):
        subfolder_path = os.path.join(root_folder, entry)

        f = open(os.path.join(subfolder_path, "run/log/timing.000.log"))
        data = f.read().split("\n")
        f.close()
        step = []
        total_run_time = [0]
        for line in data:
            x = line.split(" ")
            if x[0] == "#" or x[0] == "":
                continue

            step.append(int(x[0]))
            total_run_time.append(float(x[3]))

        f = open(os.path.join(subfolder_path, "run/log/times.log"))
        data = f.read().split("\n")
        f.close()
        step = []
        t = []
        dt = []
        a = []
        for line in data:
            x = line.split(" ")
            if x[0] == "#" or x[0] == "":
                continue

            step.append(int(x[0]))
            t.append(float(x[1]))
            dt.append(float(x[2]))
            a.append(float(x[3]))

        total_run_time = np.array(total_run_time)
        dt = np.array(dt)

        d_run_time = total_run_time[1:] - total_run_time[:-1]
        mask = d_run_time <= 0 # this happens in restarts
        d_run_time[mask] = total_run_time[1:][mask]
        runtime_per_t = (1e6/3600) * d_run_time / dt # hr per Myr

        results[entry] = ("step %d, t = %.1f Myr, a = %.4f, z = %.1f, runtime = %.3f hr, druntime/dt = %.3f hr/Myr"%(
            step[-1], t[-1]/1e6, a[-1], -1+1/a[-1], total_run_time[-1]/3600, runtime_per_t[-1]))

    return results

def check_stuck(root_path, root_folders):
    for root_folder in root_folders:
        for folder, info in scan_subfolders(os.path.join(root_path, root_folder)).items():
            print(f"{root_folder}/{folder}: {info}")

if __name__ == "__main__":
    root_path = "/scratch/08199/tg874988/art_simulations/hydro"
    root_folders = ["mh2e12_km", "mh3e12_km", "mh5e12_km", "mh2e12_p12", "mh3e12_p12", "mh5e12_p12"]
    root_folders = ["mh5e12_km", "mh5e12_p12"]
    check_stuck(root_path, root_folders)