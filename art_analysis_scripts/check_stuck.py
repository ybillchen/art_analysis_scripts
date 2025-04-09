"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import os
import time
import re

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
    for entry in os.listdir(root_folder):
        subfolder_path = os.path.join(root_folder, entry)
        if os.path.isdir(subfolder_path):
            matched_file = find_matching_file(os.path.join(subfolder_path, "run"))
            if matched_file:
                try:
                    filesize = os.path.getsize(matched_file)
                    results[entry] = filesize
                except Exception as e:
                    print(f"Error reading file {matched_file}: {e}")
            else:
                print(f"No matching file found in subfolder: {subfolder_path}")
    return results

def check_stuck(root_folders):

    print("Initial scan of subfolders...")
    initial_counts = {}
    for root_folder in root_folders:
        initial_counts[root_folder] = scan_subfolders(root_folder)
    
    time.sleep(5)
    
    print("Second scan of subfolders after 5 seconds...")
    second_counts = {}
    for root_folder in root_folders:
        second_counts[root_folder] = scan_subfolders(root_folder)

        for folder, initial_count in initial_counts[root_folder].items():
            if folder in second_counts[root_folder]:
                delta = second_counts[root_folder][folder] - initial_count
                print(f"Subfolder '{folder}': Change = {delta} bytes")
            else:
                print(f"Subfolder '{folder}' was not found in the second scan.")

if __name__ == "__main__":
    root_folders = ["mh2e12_km", "mh3e12_km", "mh5e12_km", "mh2e12_p12", "mh3e12_p12", "mh5e12_p12"]
    check_stuck(root_folders)