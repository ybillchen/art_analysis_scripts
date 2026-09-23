"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.

Standard entry point for loading ART snapshots.

Snapshots are archived by pack_files.py as a sibling tar holding the whole
file group: ``snap_a0.1667.art`` plus its ``.g***``/``.p***`` companions. yt
needs every one of them, so the presence of the ``.art`` alone does not mean
the snapshot is usable -- a partial unpack leaves a loadable-looking ``.art``
whose companions are missing.

``load_art`` therefore checks the whole group, using the tar's own member list
as the source of truth (the same test unpack_files.py applies), and extracts
the archive when anything is missing.

Use it in place of ``yt.load`` anywhere a snapshot is opened:

    from art_io import load_art
    ds = load_art(filename)
"""

import errno
import os
import subprocess
import tarfile
import time

import yt

# Seconds to wait for another process to finish extracting the same tar.
EXTRACT_TIMEOUT = 1800


def tar_for(art_path):
    """Archive holding an .art snapshot: out/snap_a0.1667.art -> out/snap_a0.1667.tar"""
    return os.path.splitext(art_path)[0] + '.tar'


def missing_members(tar_path):
    """Files in tar_path that are not present next to it on disk.

    pack_files.py stores members flat (arcname=basename), so each one belongs
    beside the archive.
    """
    tar_dir = os.path.dirname(tar_path) or '.'
    try:
        with tarfile.open(tar_path, 'r') as tar:
            names = tar.getnames()
    except Exception as e:
        raise RuntimeError("Cannot read archive %s: %s" % (tar_path, e))
    return [n for n in names if not os.path.exists(os.path.join(tar_dir, n))]


def missing_without_tar(art_path):
    """Minimum group a snapshot needs when no archive is around to consult."""
    base = os.path.splitext(art_path)[0]
    return [p for p in (art_path, base + '.g000', base + '.p000')
            if not os.path.exists(p)]


def _extract(tar_path):
    result = subprocess.run(
        ['tar', '-xf', tar_path, '-C', os.path.dirname(tar_path) or '.'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        err = (result.stderr or '').strip().split('\n')[0]
        raise RuntimeError("Failed to extract %s: %s" % (tar_path, err))


def ensure_art(art_path, timeout=EXTRACT_TIMEOUT):
    """Make sure a snapshot and all of its companion files are on disk.

    Extracts the snapshot's tar when any of the group is missing. Returns
    art_path. Raises if the group cannot be completed.
    """
    tar_path = tar_for(art_path)

    if not os.path.exists(tar_path):
        missing = missing_without_tar(art_path)
        if missing:
            raise FileNotFoundError(
                "%s: missing %s, and there is no archive %s to restore them"
                % (art_path, ', '.join(os.path.basename(m) for m in missing), tar_path)
            )
        return art_path

    if not missing_members(tar_path):
        return art_path

    # Workers may race for the same tar; the first to create the lock extracts,
    # the rest wait for the group to be complete.
    lock_path = tar_path + '.lock'
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
        waited = 0.0
        while waited < timeout:
            if not missing_members(tar_path):
                return art_path
            if not os.path.exists(lock_path):
                break          # holder finished or died; fall through and retry
            time.sleep(1.0)
            waited += 1.0
        if missing_members(tar_path):
            raise RuntimeError(
                "Timed out waiting for %s to be extracted (stale %s?)"
                % (art_path, lock_path)
            )
        return art_path

    try:
        os.close(fd)
        missing = missing_members(tar_path)      # re-check under the lock
        if missing:
            print("Extracting %s (%d file(s) missing)" % (tar_path, len(missing)))
            _extract(tar_path)
            still = missing_members(tar_path)
            if still:
                raise RuntimeError(
                    "%s did not restore %s"
                    % (tar_path, ', '.join(os.path.basename(m) for m in still))
                )
        if not os.path.exists(art_path):
            raise RuntimeError("%s is not in %s" % (art_path, tar_path))
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass

    return art_path


def load_art(filename, *args, **kwargs):
    """yt.load, first making sure the snapshot's whole file group is unpacked.

    Anything that is not a plain path to a single .art file (a glob such as
    ``snap_a*.art``, or any other format) is passed straight through.
    """
    if (isinstance(filename, str) and filename.endswith('.art')
            and not any(c in filename for c in '*?[')):
        ensure_art(filename)
    return yt.load(filename, *args, **kwargs)
