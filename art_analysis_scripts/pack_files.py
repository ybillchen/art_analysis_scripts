"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import os
import tarfile
import glob
import re
import subprocess
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

def verify_tar(args):
    """Check tar integrity by listing contents. Returns (path, is_valid, error)."""
    i, tar_path, ntot = args
    result = subprocess.run(
        ['tar', '-tf', tar_path],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f'{i}/{ntot}: OK      {tar_path} \n', end='')
        return tar_path, True, None
    else:
        err = result.stderr.strip().split('\n')[0]
        print(f'{i}/{ntot}: BROKEN  {tar_path}: {err} \n', end='')
        return tar_path, False, err

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
    exist_tars = {}  # identifier -> tar_path

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
                assert identifier not in exist_tars
                exist_tars[identifier] = os.path.join(root, file)
            else:
                full_path = os.path.join(root, file)
                if identifier in file_dict:
                    file_dict[identifier].append(full_path)
                else:
                    file_dict[identifier] = [full_path]

    file_dict_not_exist = {key: value for key, value in file_dict.items() if key not in exist_tars}

    return file_dict.items(), file_dict_not_exist.items(), exist_tars

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Archive files based on identifiers')
    parser.add_argument('--max-processes', type=int, default=int(os.environ.get('SLURM_NTASKS_PER_NODE', os.cpu_count())), help='Maximum number of parallel processes')
    parser.add_argument('--check-exists', action='store_true', help='Check if tar file exists and skip if so')
    parser.add_argument('--repair', action='store_true', help='Verify existing tar files, delete broken ones, then archive missing files')
    args = parser.parse_args()

    base_dir = os.environ['SCRATCH']
    file_groups_all, file_groups_not_exist, exist_tars = find_files(base_dir)

    if args.repair:
        tar_paths = list(exist_tars.values())
        ntot = len(tar_paths)
        print(f'Checking {ntot} existing tar files...')
        verify_args = [(i, p, ntot) for i, p in enumerate(tar_paths)]
        with Pool(processes=args.max_processes) as pool:
            results = pool.map(verify_tar, verify_args)

        broken = [(path, err) for path, ok, err in results if not ok]
        if broken:
            print(f'\n{len(broken)} broken tar file(s) found — deleting:')
            for path, err in broken:
                os.remove(path)
                print(f'  Deleted: {path}')
                print(f'    Reason: {err}')
        else:
            print('All existing tar files are valid.')

        # Re-scan after deletion so missing list is up to date
        file_groups_all, file_groups_not_exist, exist_tars = find_files(base_dir)

    file_groups = file_groups_not_exist if (args.check_exists or args.repair) else file_groups_all
    ntot = len(file_groups)
    process_args = [(i, identifier, files, True, ntot) for
        i, (identifier, files) in enumerate(file_groups)]

    print(f'Number of tar files to create: {ntot}')
    print(f'Number of processes: {args.max_processes}')
    with Pool(processes=args.max_processes) as pool:
        pool.map(archive_files, process_args)
