import os
import tarfile
import glob
from multiprocessing import Pool
import argparse

# Base directory path
base_dir = os.environ['SCRATCH']

def archive_files(args):
    identifier, files, check_exists = args
    target_dir = os.path.dirname(files[0])
    tar_filename = os.path.join(target_dir, f'{identifier}.tar')
    
    # Check if tar file exists and skip if option is set
    if check_exists and os.path.exists(tar_filename):
        print(f'{tar_filename} already exists. Skipping...')
        return
    
    print(f'Creating {tar_filename}')
    with tarfile.open(tar_filename, 'w') as tar:
        for file in files:
            tar.add(file, arcname=os.path.basename(file))
    print(f'Created {tar_filename}')

def find_files():
    file_dict = {}
    
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
    return file_dict.items()

def main(args):
    file_groups = find_files()
    process_args = [(identifier, files, args.check_exists) for identifier, files in file_groups]
    
    print('Number of tar files to create: %d'%len(file_groups))
    print('Number of processes: %d'%args.max_processes)

    with Pool(processes=args.max_processes) as pool:
        pool.map(archive_files, process_args)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Archive files based on identifiers')
    parser.add_argument('--max-processes', type=int, default=os.cpu_count(), help='Maximum number of parallel processes')
    parser.add_argument('--check-exists', action='store_true', help='Check if tar file exists and skip if so')
    args = parser.parse_args()
    
    main(args)
