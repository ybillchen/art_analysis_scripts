"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.

Standard entry point for loading ART snapshots.

Snapshots are archived by pack_files.py as a sibling tar holding the whole
file group (``snap_a0.1667.art`` plus its ``.g***``/``.p***`` companions), so a
missing ``.art`` usually means the group is still packed. ``load_art`` extracts
that tar on demand and then hands off to ``yt.load``.

Use it in place of ``yt.load`` anywhere a snapshot is opened:

    from art_io import load_art
    ds = load_art(filename)
"""

import errno
import os
import subprocess
import time

import yt

# Seconds to wait for another process to finish extracting the same tar.
EXTRACT_TIMEOUT = 1800


def tar_for(art_path):
    """Archive holding an .art snapshot: out/snap_a0.1667.art -> out/snap_a0.1667.tar"""
    return os.path.splitext(art_path)[0] + '.tar'


def _extract(tar_path):
    result = subprocess.run(
        ['tar', '-xf', tar_path, '-C', os.path.dirname(tar_path) or '.'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        err = (result.stderr or '').strip().split('\n')[0]
        raise RuntimeError("Failed to extract %s: %s" % (tar_path, err))


def ensure_art(art_path, timeout=EXTRACT_TIMEOUT):
    """Make sure art_path exists on disk, extracting its tar if it does not.

    Returns art_path. Raises FileNotFoundError if neither the snapshot nor its
    archive is present.
    """
    if os.path.exists(art_path):
        return art_path

    tar_path = tar_for(art_path)
    if not os.path.exists(tar_path):
        raise FileNotFoundError(
            "Neither the snapshot %s nor its archive %s exists" % (art_path, tar_path)
        )

    # Workers may race for the same tar; the first to create the lock extracts,
    # the rest wait for the snapshot to appear.
    lock_path = tar_path + '.lock'
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
        waited = 0.0
        while waited < timeout:
            if os.path.exists(art_path):
                return art_path
            if not os.path.exists(lock_path):
                break          # holder finished or died; fall through and retry
            time.sleep(1.0)
            waited += 1.0
        if os.path.exists(art_path):
            return art_path
        raise RuntimeError(
            "Timed out waiting for %s to be extracted (stale %s?)" % (art_path, lock_path)
        )

    try:
        os.close(fd)
        print("Extracting %s" % tar_path)
        _extract(tar_path)
        if not os.path.exists(art_path):
            raise RuntimeError("%s is not in %s" % (art_path, tar_path))
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass

    return art_path


def load_art(filename, *args, **kwargs):
    """yt.load, extracting the snapshot's tar first when the .art is missing.

    Anything that is not a plain path to a single .art file (a glob such as
    ``snap_a*.art``, or any other format) is passed straight through.
    """
    if (isinstance(filename, str) and filename.endswith('.art')
            and not any(c in filename for c in '*?[')):
        ensure_art(filename)
    return yt.load(filename, *args, **kwargs)
