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
        self.differences = []
        self.missing_on_remote = []
        self.missing_on_local = []

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
        ssh_cmd = (
            f"find {self.remote_path} -name '*.tar' -type f "
            "-exec sh -c 'echo \"$0|$(stat -c%s \"$0\")\"' {{}} \\;"
        )

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

                if local_info['size'] != remote_info['size']:
                    self.differences.append({
                        'path': rel_path,
                        'local_size': local_info['size'],
                        'remote_size': remote_info['size']
                    })

    def print_report(self):
        """Print comparison report"""
        print(f"Local:  {len(self.local_files)} tar files")
        print(f"Remote: {len(self.remote_files)} tar files")

        # Files that differ (most critical)
        if self.differences:
            print(f"\n[ERROR] {len(self.differences)} CONFLICTING FILES (size mismatch):")
            for diff in sorted(self.differences, key=lambda x: x['path'])[:5]:
                path = diff['path']
                local_size = diff['local_size']
                remote_size = diff['remote_size']
                print(f"  {path}")
                print(f"    Local:  {local_size} bytes")
                print(f"    Remote: {remote_size} bytes")
            if len(self.differences) > 5:
                print(f"  ... and {len(self.differences) - 5} more")

        # Files only on local
        if self.missing_on_remote:
            print(f"\n[INFO] {len(self.missing_on_remote)} files only on local (will be uploaded)")

        # Files only on remote
        if self.missing_on_local:
            print(f"[INFO] {len(self.missing_on_local)} files only on remote (will be preserved)")

    def has_conflicts(self):
        """Check if there are conflicting files that would be overwritten"""
        return len(self.differences) > 0

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

    if comparator.has_conflicts():
        print("[ERROR] SYNC BLOCKED: Conflicting files detected")
        return 1
    else:
        print("[OK] SAFE TO PROCEED: No conflicting files")
        return 0


if __name__ == '__main__':
    sys.exit(main())
