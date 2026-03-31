"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import os
import tarfile
import glob
import re
from multiprocessing import Pool
import argparse

def validate_snap_a_files(identifier, files):
    """
    Validate that snap_a file groups have exactly three suffix types:
    .art, .g***, .p*** (where *** are 3 digits)

    Strict requirements:
    - Same number of .g*** and .p*** files
    - Digits must start at 000 and increment by 1
    - Valid example: g000, g001, g002, g003, p000, p001, p002, p003
    - Invalid: missing g003 or p003

    Returns (is_valid, message)
    """
    # Check if this is a snap_a file group
    if not identifier.startswith('snap_a'):
        return True, None

    # Extract suffixes from all files
    suffixes = set()
    for filepath in files:
        _, ext = os.path.splitext(filepath)
        suffixes.add(ext)

    # Check for .art file
    if '.art' not in suffixes:
        return False, "Missing .art file"

    # Check for .g*** and .p*** files (3 digits each)
    g_pattern = re.compile(r'^\.g(\d{3})$')
    p_pattern = re.compile(r'^\.p(\d{3})$')

    g_files = sorted([s for s in suffixes if g_pattern.match(s)])
    p_files = sorted([s for s in suffixes if p_pattern.match(s)])

    # Should have at least one .g*** and one .p*** file
    if len(g_files) == 0:
        return False, "Missing .g*** files (where *** are 3 digits)"
    if len(p_files) == 0:
        return False, "Missing .p*** files (where *** are 3 digits)"

    # Check that we only have these three types
    expected_suffixes = {'.art'} | set(g_files) | set(p_files)
    if suffixes != expected_suffixes:
        unexpected = suffixes - expected_suffixes
        return False, f"Unexpected suffix types: {unexpected}"

    # Strict check: equal number of .g*** and .p*** files
    if len(g_files) != len(p_files):
        return False, f"Unequal number of .g*** ({len(g_files)}) and .p*** ({len(p_files)}) files"

    # Extract digit sequences and validate they form a continuous sequence from 000
    g_digits = sorted([int(g_pattern.match(s).group(1)) for s in g_files])
    p_digits = sorted([int(p_pattern.match(s).group(1)) for s in p_files])

    # Check that .g*** digits form a sequence 0, 1, 2, ..., n-1
    expected_g_sequence = list(range(len(g_files)))
    if g_digits != expected_g_sequence:
        missing = set(expected_g_sequence) - set(g_digits)
        extra = set(g_digits) - set(expected_g_sequence)
        if missing:
            return False, f".g*** files missing digits: {sorted(missing)}"
        if extra:
            return False, f".g*** files have unexpected digits: {sorted(extra)}"

    # Check that .p*** digits form a sequence 0, 1, 2, ..., n-1
    expected_p_sequence = list(range(len(p_files)))
    if p_digits != expected_p_sequence:
        missing = set(expected_p_sequence) - set(p_digits)
        extra = set(p_digits) - set(expected_p_sequence)
        if missing:
            return False, f".p*** files missing digits: {sorted(missing)}"
        if extra:
            return False, f".p*** files have unexpected digits: {sorted(extra)}"

    return True, None

def archive_files(args):
    i, identifier, files, check_exists, ntot = args
    target_dir = os.path.dirname(files[0])

    # Validate snap_a file groups before archiving
    if os.path.basename(identifier).startswith('snap_a'):
        is_valid, error_msg = validate_snap_a_files(os.path.basename(identifier), files)
        if not is_valid:
            print(f'{i}/{ntot}: {identifier} validation failed: {error_msg}. Skipped. \n', end='')
            return

    if 'rockstar_halos' in identifier.split(os.sep):
        tar_filename = os.path.join(target_dir, 'rockstar_halos.tar')
    else:
        tar_filename = os.path.join(target_dir, f'{identifier}.tar')

    # Check if tar file exists and skip if option is set
    if check_exists and os.path.exists(tar_filename):
        print(f'{i}/{ntot}: {tar_filename} already exists. Skipped. \n', end='')
        return

    with tarfile.open(tar_filename, 'w') as tar:
        for file in files:
            tar.add(file, arcname=os.path.basename(file))
    print(f'{i}/{ntot}: {tar_filename} created. \n', end='')
    return

def find_files(base_dir):
    file_dict = {}
    exist_list = []
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            filename_parts = file.split('.')
            if 'out' in root.split(os.sep) and file.startswith('snap_a'):
                identifier = os.path.join(root, '.'.join(filename_parts[:-1]))
            elif 'rockstar_halos' in root.split(os.sep):
                identifier = root
            else:
                continue

            if file.endswith('tar'):
                assert not identifier in exist_list
                exist_list.append(identifier)
            else:
                full_path = os.path.join(root, file)
                if identifier in file_dict:
                    file_dict[identifier].append(full_path)
                else:
                    file_dict[identifier] = [full_path]


    # assert all(key in file_dict for key in exist_list)

    file_dict_not_exist = {key: value for key, value in file_dict.items() if key not in exist_list}

    return file_dict.items(), file_dict_not_exist.items()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Archive files based on identifiers')
    parser.add_argument('--max-processes', type=int, default=os.cpu_count(), help='Maximum number of parallel processes')
    parser.add_argument('--check-exists', action='store_true', help='Check if tar file exists and skip if so')
    args = parser.parse_args()
    
    # Base directory path
    base_dir = os.environ['SCRATCH']
    file_groups_all, file_groups_not_exist = find_files(base_dir)
    file_groups = file_groups_not_exist if args.check_exists else file_groups_all
    process_args = [(i, identifier, files, args.check_exists, len(file_groups)) for 
        i, (identifier, files) in enumerate(file_groups)]
    
    print('Number of tar files to create: %d'%len(file_groups))
    print('Number of processes: %d'%args.max_processes)
    with Pool(processes=args.max_processes) as pool:
        pool.map(archive_files, process_args)
