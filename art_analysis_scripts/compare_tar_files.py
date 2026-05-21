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
import concurrent.futures


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
        self.check_integrity = True
        self.broken_local = []
        self.broken_remote = []

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

        # Broken local tars
        if self.broken_local:
            print(f"\n[ERROR] {len(self.broken_local)} broken local tar files (failed tar -tf):")
            for entry in self.broken_local:
                print(f"  {entry['rel_path']}")
                print(f"    Error: {entry['error']}")

        # Broken remote tars
        if self.broken_remote:
            print(f"\n[WARN] {len(self.broken_remote)} broken remote tar files (failed tar -tf):")
            for entry in self.broken_remote:
                print(f"  {entry['rel_path']}")

        # Files only on local
        if self.missing_on_remote:
            print(f"\n[INFO] {len(self.missing_on_remote)} files only on local (will be uploaded)")

        # Files only on remote
        if self.missing_on_local:
            print(f"[INFO] {len(self.missing_on_local)} files only on remote (will be preserved)")

    def has_conflicts(self):
        """Block sync when local may be damaged (smaller than remote, or broken)"""
        return len(self.local_smaller) > 0 or len(self.broken_local) > 0

    def write_suspect_file(self, path):
        """Write path|local_size|remote_size for files where local < remote."""
        with open(path, 'w') as f:
            for entry in self.local_smaller:
                f.write(f"{entry['full_path']}|{entry['local_size']}|{entry['remote_size']}\n")

    def write_local_larger_file(self, path):
        """Write path|local_size|remote_size for files where local > remote."""
        with open(path, 'w') as f:
            for entry in self.local_larger:
                f.write(f"{entry['full_path']}|{entry['local_size']}|{entry['remote_size']}\n")

    def write_broken_local_file(self, path):
        """Write path|error for each broken local tar file."""
        with open(path, 'w') as f:
            for entry in self.broken_local:
                error = (entry.get('error') or '').replace('\n', ' ')
                f.write(f"{entry['full_path']}|{error}\n")

    def write_broken_remote_file(self, path):
        """Write remote path for each broken remote tar file."""
        with open(path, 'w') as f:
            for entry in self.broken_remote:
                f.write(entry['full_path'] + '\n')

    def check_local_integrity(self):
        """Run tar -tf on each local tar file in parallel."""
        def _check(item):
            rel_path, info = item
            result = subprocess.run(['tar', '-tf', info['full_path']], capture_output=True)
            ok = result.returncode == 0
            err = result.stderr.decode('utf-8', errors='replace').strip().split('\n')[0] if not ok else None
            return rel_path, info['full_path'], ok, err

        print(f"Checking integrity of {len(self.local_files)} local tar files...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for rel_path, full_path, ok, err in executor.map(_check, self.local_files.items()):
                if not ok:
                    self.broken_local.append({
                        'rel_path': rel_path,
                        'full_path': full_path,
                        'error': err
                    })

    def check_remote_integrity(self):
        """Run tar -tf on all remote tar files via a single parallel SSH call."""
        print(f"Checking integrity of {len(self.remote_files)} remote tar files...")
        ssh_cmd = (
            f"find {self.remote_path} -name '*.tar' -type f "
            f"| xargs -P 8 -I{{}} sh -c 'tar -tf \"{{}}\" > /dev/null 2>&1 || echo \"{{}}\"'"
        )
        try:
            result = subprocess.run(
                ['ssh', self.remote_host, ssh_cmd],
                capture_output=True, text=True, timeout=3600
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line:
                    rel_path = os.path.relpath(line, self.remote_path)
                    self.broken_remote.append({
                        'rel_path': rel_path,
                        'full_path': line
                    })
        except subprocess.TimeoutExpired:
            print("[ERROR] Remote integrity check timed out", file=sys.stderr)
            return False
        except Exception as e:
            print(f"[ERROR] Remote integrity check failed: {e}", file=sys.stderr)
            return False
        return True

    def run(self):
        """Run full comparison"""
        if not self.get_local_tar_files():
            return False

        if not self.get_remote_tar_files():
            return False

        self.compare_files()

        if self.check_integrity:
            self.check_local_integrity()
            if not self.check_remote_integrity():
                return False

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
    parser.add_argument('--no-check-integrity', dest='check_integrity', action='store_false',
                        help='Skip tar -tf integrity check on each tar file')
    parser.set_defaults(check_integrity=True)
    parser.add_argument('--broken-local-file', default=None,
                        help='Write path|error for broken local tar files to this file')
    parser.add_argument('--broken-remote-file', default=None,
                        help='Write remote paths of broken remote tar files to this file')

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
    comparator.check_integrity = args.check_integrity

    if not comparator.run():
        print("\nERROR: Comparison failed", file=sys.stderr)
        return 1

    if args.suspect_file is not None:
        comparator.write_suspect_file(args.suspect_file)

    if args.local_larger_file is not None:
        comparator.write_local_larger_file(args.local_larger_file)

    if args.broken_local_file is not None:
        comparator.write_broken_local_file(args.broken_local_file)

    if args.broken_remote_file is not None:
        comparator.write_broken_remote_file(args.broken_remote_file)

    if comparator.has_conflicts():
        print("[ERROR] SYNC BLOCKED: Conflicting files detected")
        return 1
    else:
        print("[OK] SAFE TO PROCEED: No conflicting files")
        return 0


if __name__ == '__main__':
    sys.exit(main())
