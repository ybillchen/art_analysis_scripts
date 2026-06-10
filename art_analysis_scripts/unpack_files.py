"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.
"""

import os
import tarfile
import subprocess
from multiprocessing import Pool
import argparse


def check_extracted(args):
    """Check if every file in a tar already exists next to it on disk."""
    i, tar_path, ntot = args
    tar_dir = os.path.dirname(tar_path)
    try:
        with tarfile.open(tar_path, 'r') as tar:
            members = tar.getnames()
    except Exception as e:
        print(f'{i}/{ntot}: ERROR          {tar_path}: {e} \n', end='')
        return tar_path, False, []

    missing = [m for m in members if not os.path.exists(os.path.join(tar_dir, m))]
    if missing:
        print(f'{i}/{ntot}: NOT EXTRACTED  {tar_path}  ({len(missing)}/{len(members)} files missing) \n', end='')
        return tar_path, False, missing
    else:
        print(f'{i}/{ntot}: OK             {tar_path} \n', end='')
        return tar_path, True, []


def extract_tar(args):
    """Extract a tar file into its own directory."""
    i, tar_path, ntot = args
    result = subprocess.run(
        ['tar', '-xf', tar_path, '-C', os.path.dirname(tar_path)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f'{i}/{ntot}: EXTRACTED  {tar_path} \n', end='')
    else:
        err = result.stderr.strip().split('\n')[0]
        print(f'{i}/{ntot}: FAILED     {tar_path}: {err} \n', end='')


def find_tar_files(base_dir):
    tar_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in sorted(files):
            if file.endswith('.tar'):
                tar_files.append(os.path.join(root, file))
    return tar_files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check whether tar files are extracted; optionally extract missing ones')
    parser.add_argument('--max-processes', type=int,
                        default=int(os.environ.get('SLURM_NTASKS_PER_NODE', os.cpu_count())),
                        help='Maximum number of parallel processes')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Extract without prompting for confirmation')
    args = parser.parse_args()

    base_dir = os.environ['SCRATCH']
    tar_files = find_tar_files(base_dir)
    ntot = len(tar_files)
    print(f'Found {ntot} tar files under {base_dir}')

    check_args = [(i, p, ntot) for i, p in enumerate(tar_files)]
    with Pool(processes=args.max_processes) as pool:
        results = pool.map(check_extracted, check_args)

    not_extracted = [path for path, ok, _ in results if not ok]
    print(f'\n{len(not_extracted)} tar file(s) not fully extracted.')

    if not not_extracted:
        print('Nothing to do.')
    else:
        if args.yes:
            answer = 'y'
        else:
            answer = input(f'Extract {len(not_extracted)} tar file(s)? [y/N] ').strip().lower()
        if answer == 'y':
            extract_args = [(i, path, len(not_extracted)) for i, path in enumerate(not_extracted)]
            with Pool(processes=args.max_processes) as pool:
                pool.map(extract_tar, extract_args)
