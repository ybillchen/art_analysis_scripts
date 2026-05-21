#!/usr/bin/env python3
"""
Compare tar files between local SCRATCH and remote backup server.

This script validates tar file integrity before running rsync to prevent
accidental truncation of important backup files.

Usage:
    python compare_tar_files.py [--verbose] [--local-path PATH] [--remote-host HOST] [--remote-path PATH]

Environment variables:
    SCRATCH         - Local source directory (default from env)
    ARCHIVER        - Remote hostname (default from env)
"""

import os
import sys
import subprocess
import argparse


class TarFileComparator:
    def __init__(self, local_path, remote_host, remote_path, verbose=False):
        self.local_path = local_path
        self.remote_host = remote_host
        self.remote_path = remote_path
        self.verbose = verbose
        self.local_files = {}
        self.remote_files = {}
        self.missing_on_remote = []
        self.missing_on_local = []
        self.local_smaller = []  # local < remote: local may be damaged
        self.local_larger = []   # local > remote: remote may be wrong

    def log(self, msg, level="INFO"):
        """Print log message (only DEBUG with verbose flag)"""
        if level == "DEBUG" and not self.verbose:
            return
        if level == "DEBUG":
            print(f"[DEBUG] {msg}", file=sys.stderr)

    def get_local_tar_files(self):
        """Find all .tar files in local SCRATCH directory"""
        try:
            for root, dirs, files in os.walk(self.local_path):
                for file in files:
                    if file.endswith('.tar'):
                        full_path = os.path.join(root, file)
                        try:
                            size = os.path.getsize(full_path)
                            rel_path = os.path.relpath(full_path, self.local_path)
                            self.local_files[rel_path] = {
                                'size': size,
                                'full_path': full_path
                            }
                        except Exception as e:
                            print(f"[WARN] Error reading {full_path}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Error scanning local directory: {e}", file=sys.stderr)
            return False

        return True

    def get_remote_tar_files(self):
        """Find all .tar files on remote backup server via SSH"""
        # Build SSH command to find tar files and get their sizes
        ssh_cmd = f"find {self.remote_path} -name '*.tar' -type f -exec sh -c 'echo \"$0|$(stat -c%s \"$0\")\"' {{}} \\;"

        try:
            result = subprocess.run(
                ['ssh', self.remote_host, ssh_cmd],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                print(f"[ERROR] SSH error: {result.stderr}", file=sys.stderr)
                return False

            # Parse output
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    full_path, size = line.split('|')
                    size = int(size)
                    rel_path = os.path.relpath(full_path, self.remote_path)
                    self.remote_files[rel_path] = {
                        'size': size,
                        'full_path': full_path
                    }
                except ValueError:
                    continue
        except subprocess.TimeoutExpired:
            print("[ERROR] SSH command timed out", file=sys.stderr)
            return False
        except Exception as e:
            print(f"[ERROR] Error querying remote: {e}", file=sys.stderr)
            return False

        return True


    def compare_files(self):
        """Compare tar files between local and remote by size"""
        all_keys = set(self.local_files.keys()) | set(self.remote_files.keys())

        for rel_path in sorted(all_keys):
            if rel_path not in self.local_files:
                self.missing_on_local.append(rel_path)
            elif rel_path not in self.remote_files:
                self.missing_on_remote.append(rel_path)
            else:
                # Both exist - check if sizes match
                local_info = self.local_files[rel_path]
                remote_info = self.remote_files[rel_path]

                if local_info['size'] < remote_info['size']:
                    self.local_smaller.append({
                        'full_path': local_info['full_path'],
                        'rel_path': rel_path,
                        'local_size': local_info['size'],
                        'remote_size': remote_info['size']
                    })
                elif local_info['size'] > remote_info['size']:
                    self.local_larger.append({
                        'full_path': local_info['full_path'],
                        'rel_path': rel_path,
                        'local_size': local_info['size'],
                        'remote_size': remote_info['size']
                    })

    def print_report(self):
        """Print comparison report"""
        print(f"Local:  {len(self.local_files)} tar files")
        print(f"Remote: {len(self.remote_files)} tar files")

        # Category 1: local < remote (local may be damaged)
        if self.local_smaller:
            print(f"\n[WARN] {len(self.local_smaller)} files where local < remote (local may be damaged):")
            for entry in self.local_smaller[:5]:
                print(f"  {entry['rel_path']}")
                print(f"    Local:  {entry['local_size']} bytes")
                print(f"    Remote: {entry['remote_size']} bytes")
            if len(self.local_smaller) > 5:
                print(f"  ... and {len(self.local_smaller) - 5} more")

        # Category 2: local > remote (remote may be wrong)
        if self.local_larger:
            print(f"\n[INFO] {len(self.local_larger)} files where local > remote (check remote):")
            for entry in self.local_larger:
                print(f"  {entry['rel_path']}")
                print(f"    Local:  {entry['local_size']} bytes")
                print(f"    Remote: {entry['remote_size']} bytes")

        # Files only on local
        if self.missing_on_remote:
            print(f"\n[INFO] {len(self.missing_on_remote)} files only on local (will be uploaded)")

        # Files only on remote
        if self.missing_on_local:
            print(f"[INFO] {len(self.missing_on_local)} files only on remote (will be preserved)")

    def has_conflicts(self):
        """Block sync only when local is smaller than remote (local may be damaged)"""
        return len(self.local_smaller) > 0

    def write_suspect_file(self, path):
        """Write local paths of files where local < remote."""
        with open(path, 'w') as f:
            for entry in self.local_smaller:
                f.write(entry['full_path'] + '\n')

    def write_local_larger_file(self, path):
        """Write local paths of files where local > remote."""
        with open(path, 'w') as f:
            for entry in self.local_larger:
                f.write(entry['full_path'] + '\n')

    def run(self):
        """Run full comparison"""
        if not self.get_local_tar_files():
            return False

        if not self.get_remote_tar_files():
            return False

        self.compare_files()
        self.print_report()

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Compare tar files between local and remote before rsync'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--local-path', default=os.environ.get('SCRATCH'),
                        help='Local path to scan (default: $SCRATCH)')
    parser.add_argument('--remote-host', default=os.environ.get('ARCHIVER'),
                        help='Remote host (default: $ARCHIVER)')
    parser.add_argument('--remote-path', default='/scoutfs/projects/TG-AST200017/stampede3/',
                        help='Remote path (default: /scoutfs/projects/TG-AST200017/stampede3/)')
    parser.add_argument('--suspect-file', default=None,
                        help='Write local paths of files where local < remote to this file')
    parser.add_argument('--local-larger-file', default=None,
                        help='Write local paths of files where local > remote to this file')

    args = parser.parse_args()

    # Validate inputs
    if not args.local_path:
        print("ERROR: Local path not provided. Set $SCRATCH or use --local-path", file=sys.stderr)
        return 1

    if not args.remote_host:
        print("ERROR: Remote host not provided. Set $ARCHIVER or use --remote-host", file=sys.stderr)
        return 1

    if not os.path.exists(args.local_path):
        print(f"ERROR: Local path does not exist: {args.local_path}", file=sys.stderr)
        return 1

    comparator = TarFileComparator(
        args.local_path,
        args.remote_host,
        args.remote_path,
        verbose=args.verbose
    )

    if not comparator.run():
        print("\nERROR: Comparison failed", file=sys.stderr)
        return 1

    if args.suspect_file is not None:
        comparator.write_suspect_file(args.suspect_file)

    if args.local_larger_file is not None:
        comparator.write_local_larger_file(args.local_larger_file)

    if comparator.has_conflicts():
        print("[ERROR] SYNC BLOCKED: Conflicting files detected")
        return 1
    else:
        print("[OK] SAFE TO PROCEED: No conflicting files")
        return 0


if __name__ == '__main__':
    sys.exit(main())
