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
import tempfile


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
        # intermediate results
        self.local_smaller = []
        self.local_larger = []
        self.broken_local = []
        self.broken_remote = []
        # final cross-referenced categories
        self.smaller_broken = []        # local < remote, only local broken
        self.smaller_ok = []            # local < remote, only remote broken (local intact)
        self.larger_remote_broken = []  # local > remote, only remote broken
        self.larger_remote_ok = []      # local > remote, only local broken (remote intact)
        self.both_broken = []           # size mismatch, both broken
        self.both_intact = []           # size mismatch, both intact
        self.broken_size_match = []     # broken local, size matches remote
        self.broken_no_remote = []      # broken local, no remote counterpart
        self._ssh_socket = None

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

    def _ssh_args(self):
        """SSH args with ControlMaster multiplexing to reuse a single connection."""
        return ['ssh',
                '-o', f'ControlPath={self._ssh_socket}',
                '-o', 'ControlMaster=auto',
                '-o', 'ControlPersist=60s']

    def get_remote_tar_files(self):
        """Find all .tar files on remote backup server via SSH"""
        # Build SSH command to find tar files and get their sizes
        ssh_cmd = f"find {self.remote_path} -name '*.tar' -type f -exec sh -c 'echo \"$0|$(stat -c%s \"$0\")\"' {{}} \\;"

        try:
            result = subprocess.run(
                self._ssh_args() + [self.remote_host, ssh_cmd],
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

    def categorize_results(self):
        """Cross-reference integrity and size-mismatch results into output categories."""
        broken_local_map = {e['rel_path']: e for e in self.broken_local}
        broken_remote_rel = {e['rel_path'] for e in self.broken_remote}
        smaller_rel = {e['rel_path'] for e in self.local_smaller}
        larger_rel  = {e['rel_path'] for e in self.local_larger}

        for entry in self.local_smaller:
            bl = broken_local_map.get(entry['rel_path'])
            local_broken = bl is not None
            remote_broken = entry['rel_path'] in broken_remote_rel
            if local_broken and remote_broken:
                self.both_broken.append({**entry, 'error': bl['error']})
            elif local_broken:
                self.smaller_broken.append({**entry, 'error': bl['error']})
            elif remote_broken:
                self.smaller_ok.append(entry)
            else:
                self.both_intact.append(entry)

        for entry in self.local_larger:
            bl = broken_local_map.get(entry['rel_path'])
            local_broken = bl is not None
            remote_broken = entry['rel_path'] in broken_remote_rel
            if local_broken and remote_broken:
                self.both_broken.append({**entry, 'error': bl['error']})
            elif remote_broken:
                self.larger_remote_broken.append(entry)
            elif local_broken:
                self.larger_remote_ok.append(entry)
            else:
                self.both_intact.append(entry)

        mismatch_rel = smaller_rel | larger_rel
        missing_on_remote_set = set(self.missing_on_remote)
        for entry in self.broken_local:
            if entry['rel_path'] not in mismatch_rel:
                if entry['rel_path'] in missing_on_remote_set:
                    self.broken_no_remote.append(entry)
                else:
                    self.broken_size_match.append(entry)

    def print_report(self):
        """Print summary counts for all categories."""
        print(f"Local:  {len(self.local_files)} tar files  |  Remote: {len(self.remote_files)} tar files")
        print(f"  {len(self.missing_on_remote):4d}  only on local (will be uploaded)")
        print(f"  {len(self.missing_on_local):4d}  only on remote (will be preserved)")
        print(f"  {len(self.both_intact):4d}  size mismatch, both intact [SYNC BLOCKED]")
        print(f"  {len(self.larger_remote_ok):4d}  local > remote, only remote intact [SYNC BLOCKED]")
        print(f"  {len(self.larger_remote_broken):4d}  local > remote, only remote broken [re-sync will fix]")
        print(f"  {len(self.smaller_ok):4d}  local < remote, only local intact [re-sync will fix]")
        print(f"  {len(self.smaller_broken):4d}  local < remote, only local broken [offer delete]")
        print(f"  {len(self.both_broken):4d}  size mismatch, both broken [SYNC BLOCKED]")
        print(f"  {len(self.broken_size_match):4d}  broken local, size matches remote [offer delete]")
        print(f"  {len(self.broken_no_remote):4d}  broken local, no remote counterpart [offer delete]")

    def has_conflicts(self):
        """Block sync when broken/unexpected local files are present."""
        return bool(self.smaller_broken or self.both_intact or self.larger_remote_ok or self.both_broken or self.broken_size_match or self.broken_no_remote)

    def _clean_error(self, entry):
        return (entry.get('error') or '').replace('\n', ' ')

    def write_smaller_broken_file(self, path):
        with open(path, 'w') as f:
            for e in self.smaller_broken:
                f.write(f"{e['full_path']}|{e['local_size']}|{e['remote_size']}|{self._clean_error(e)}\n")

    def write_smaller_ok_file(self, path):
        with open(path, 'w') as f:
            for e in self.smaller_ok:
                f.write(f"{e['full_path']}|{e['local_size']}|{e['remote_size']}\n")

    def write_both_intact_file(self, path):
        with open(path, 'w') as f:
            for e in self.both_intact:
                f.write(f"{e['full_path']}|{e['local_size']}|{e['remote_size']}\n")

    def write_both_broken_file(self, path):
        with open(path, 'w') as f:
            for e in self.both_broken:
                f.write(f"{e['full_path']}|{e['local_size']}|{e['remote_size']}|{self._clean_error(e)}\n")

    def write_larger_remote_broken_file(self, path):
        with open(path, 'w') as f:
            for e in self.larger_remote_broken:
                remote_path = self.remote_files[e['rel_path']]['full_path']
                f.write(f"{remote_path}|{e['local_size']}|{e['remote_size']}\n")

    def write_larger_remote_ok_file(self, path):
        with open(path, 'w') as f:
            for e in self.larger_remote_ok:
                f.write(f"{e['full_path']}|{e['local_size']}|{e['remote_size']}\n")

    def write_broken_size_match_file(self, path):
        with open(path, 'w') as f:
            for e in self.broken_size_match:
                f.write(f"{e['full_path']}|{self._clean_error(e)}\n")

    def write_broken_no_remote_file(self, path):
        with open(path, 'w') as f:
            for e in self.broken_no_remote:
                f.write(f"{e['full_path']}|{self._clean_error(e)}\n")

    def write_missing_on_remote_file(self, path):
        with open(path, 'w') as f:
            for rel_path in self.missing_on_remote:
                info = self.local_files[rel_path]
                f.write(f"{info['full_path']}|{info['size']}\n")

    def check_local_integrity(self):
        """Run tar -tf on each local tar file in parallel, with progress."""
        def _check(item):
            rel_path, info = item
            result = subprocess.run(['tar', '-tf', info['full_path']], capture_output=True)
            ok = result.returncode == 0
            err = result.stderr.decode('utf-8', errors='replace').strip().split('\n')[0] if not ok else None
            return rel_path, info['full_path'], ok, err

        items = list(self.local_files.items())
        total = len(items)
        print(f"Checking integrity of {total} local tar files...", flush=True)
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_check, item) for item in items]
            for future in concurrent.futures.as_completed(futures):
                rel_path, full_path, ok, err = future.result()
                done += 1
                print(f"\r  {done}/{total}", end='', flush=True)
                if not ok:
                    self.broken_local.append({
                        'rel_path': rel_path,
                        'full_path': full_path,
                        'error': err
                    })
        print()

    def check_remote_integrity(self):
        """Run tar -tf on remote tar files that have a size mismatch with local."""
        mismatched = [
            self.remote_files[entry['rel_path']]['full_path']
            for entry in (self.local_smaller + self.local_larger)
            if entry['rel_path'] in self.remote_files
        ]
        if not mismatched:
            print("No size mismatches — skipping remote integrity check.")
            return True

        total = len(mismatched)
        print(f"Checking integrity of {total} mismatched remote tar files...", flush=True)
        # Receive paths on stdin, emit "exit_code|path" per file
        ssh_cmd = "xargs -P 8 -I{} sh -c 'tar -tf \"{}\" > /dev/null 2>&1; echo \"$?|{}\"'"
        try:
            proc = subprocess.Popen(
                self._ssh_args() + [self.remote_host, ssh_cmd],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            proc.stdin.write('\n'.join(mismatched) + '\n')
            proc.stdin.close()

            done = 0
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                status, _, path = line.partition('|')
                done += 1
                print(f"\r  {done}/{total}", end='', flush=True)
                if status.strip() != '0':
                    rel_path = os.path.relpath(path, self.remote_path)
                    self.broken_remote.append({'rel_path': rel_path, 'full_path': path})
            proc.wait()
            print()
        except Exception as e:
            print(f"\n[ERROR] Remote integrity check failed: {e}", file=sys.stderr)
            return False
        return True

    def run(self):
        """Run full comparison pipeline."""
        self._ssh_socket = os.path.join(tempfile.gettempdir(), f'ssh_ctrl_{os.getpid()}')
        try:
            if not self.get_local_tar_files():
                return False
            self.check_local_integrity()

            if not self.get_remote_tar_files():
                return False
            self.compare_files()

            if not self.check_remote_integrity():
                return False

            self.categorize_results()
            self.print_report()
            return True
        finally:
            subprocess.run(
                self._ssh_args() + ['-O', 'exit', self.remote_host],
                capture_output=True
            )


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
    parser.add_argument('--smaller-broken-file', default=None,
                        help='local < remote AND local broken: full_path|local_size|remote_size|error')
    parser.add_argument('--smaller-ok-file', default=None,
                        help='local < remote AND local intact (unexpected): full_path|local_size|remote_size')
    parser.add_argument('--both-intact-file', default=None,
                        help='size mismatch AND both intact: full_path|local_size|remote_size')
    parser.add_argument('--both-broken-file', default=None,
                        help='size mismatch AND both broken: full_path|local_size|remote_size|local_error')
    parser.add_argument('--larger-remote-broken-file', default=None,
                        help='local > remote AND only remote broken: remote_path|local_size|remote_size')
    parser.add_argument('--larger-remote-ok-file', default=None,
                        help='local > remote AND remote intact (unexpected): full_path|local_size|remote_size')
    parser.add_argument('--broken-size-match-file', default=None,
                        help='broken local, size matches remote: full_path|error')
    parser.add_argument('--broken-no-remote-file', default=None,
                        help='broken local, no remote counterpart: full_path|error')
    parser.add_argument('--missing-on-remote-file', default=None,
                        help='only on local (no remote counterpart): full_path|local_size')

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

    if args.smaller_broken_file is not None:
        comparator.write_smaller_broken_file(args.smaller_broken_file)
    if args.smaller_ok_file is not None:
        comparator.write_smaller_ok_file(args.smaller_ok_file)
    if args.both_intact_file is not None:
        comparator.write_both_intact_file(args.both_intact_file)
    if args.both_broken_file is not None:
        comparator.write_both_broken_file(args.both_broken_file)
    if args.larger_remote_broken_file is not None:
        comparator.write_larger_remote_broken_file(args.larger_remote_broken_file)
    if args.larger_remote_ok_file is not None:
        comparator.write_larger_remote_ok_file(args.larger_remote_ok_file)
    if args.broken_size_match_file is not None:
        comparator.write_broken_size_match_file(args.broken_size_match_file)
    if args.broken_no_remote_file is not None:
        comparator.write_broken_no_remote_file(args.broken_no_remote_file)
    if args.missing_on_remote_file is not None:
        comparator.write_missing_on_remote_file(args.missing_on_remote_file)

    if comparator.has_conflicts():
        print("[ERROR] SYNC BLOCKED: Conflicting files detected")
        return 1
    else:
        print("[OK] SAFE TO PROCEED: No conflicting files")
        return 0


if __name__ == '__main__':
    sys.exit(main())
