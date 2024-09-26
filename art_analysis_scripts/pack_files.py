import os
import tarfile
import glob
from multiprocessing import Pool
import argparse

# Base directory path
base_dir = os.environ['SCRATCH']

def archive_files(args):
    i, identifier, files, check_exists, ntot = args
    target_dir = os.path.dirname(files[0])
    tar_filename = os.path.join(target_dir, f'{identifier}.tar')
    
    # Check if tar file exists and skip if option is set
    if check_exists and os.path.exists(tar_filename):
        print(f'{i}/{ntot}: {tar_filename} already exists. Skipped. \n', end='')
        return
    
    with tarfile.open(tar_filename, 'w') as tar:
        for file in files:
            tar.add(file, arcname=os.path.basename(file))
    print(f'{i}/{ntot}: {tar_filename} created. \n', end='')

def find_files():
    file_dict = {}
    exist_list = []
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if 'out' in root.split(os.sep) and file.startswith('snap_a') and not file.endswith('tar'):
                filename_parts = file.split('.')
                identifier = os.path.join(root, '.'.join(filename_parts[:-1]))
                full_path = os.path.join(root, file)
                if identifier in file_dict:
                    file_dict[identifier].append(full_path)
                else:
                    file_dict[identifier] = [full_path]
            if 'out' in root.split(os.sep) and file.startswith('snap_a') and file.endswith('tar'):
                filename_parts = file.split('.')
                identifier = os.path.join(root, '.'.join(filename_parts[:-1]))
                assert not identifier in exist_list
                exist_list.append(identifier)

    assert all(key in file_dict for key in exist_list)

    file_dict_not_exist = {key: value for key, value in file_dict.items() if key not in exist_list}

    return file_dict.items(), file_dict_not_exist.items()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Archive files based on identifiers')
    parser.add_argument('--max-processes', type=int, default=os.cpu_count(), help='Maximum number of parallel processes')
    parser.add_argument('--check-exists', action='store_true', help='Check if tar file exists and skip if so')
    args = parser.parse_args()
    
    file_groups_all, file_groups_not_exist = find_files()
    file_groups = file_groups_not_exist if args.check_exists else file_groups_all
    process_args = [(i, identifier, files, args.check_exists, len(file_groups)) for 
        i, (identifier, files) in enumerate(file_groups)]
    
    print('Number of tar files to create: %d'%len(file_groups))
    print('Number of processes: %d'%args.max_processes)
    with Pool(processes=args.max_processes) as pool:
        pool.map(archive_files, process_args)
