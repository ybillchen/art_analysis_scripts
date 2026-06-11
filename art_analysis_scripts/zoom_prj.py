"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.

Generate xy and xz gas surface density projections of a small box
around a given location.

Usage:
    python zoom_prj.py <basepath> <x> <y> <z> -a 0.1657
"""

import os
import sys
import glob
import argparse
sys.path.append(os.path.dirname(__file__))

import numpy as np
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import yt

from prj import prj

BOX_SIZE   = 1.0    # kpc
LEVEL      = 12
VMIN, VMAX = 1e0, 1e4


def find_snapshot(basepath, target_a):
    snaps = sorted(glob.glob(os.path.join(basepath, 'out/snap_a*.art')))
    entries = []
    for s in snaps:
        try:
            a = float(os.path.basename(s).replace('snap_a', '').replace('.art', ''))
            entries.append((a, s))
        except ValueError:
            continue
    entries.sort()
    a_arr = np.array([a for a, _ in entries])
    idx = np.argmin(np.abs(a_arr - target_a))
    return entries[idx]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate xy/xz projections of a small box around a given location')
    parser.add_argument('basepath', help='Path to simulation run folder')
    parser.add_argument('x', type=float, help='Center x (Mpccm/h)')
    parser.add_argument('y', type=float, help='Center y (Mpccm/h)')
    parser.add_argument('z', type=float, help='Center z (Mpccm/h)')
    parser.add_argument('--scale-factor', '-a', type=float, required=True,
                        help='Target scale factor')
    parser.add_argument('--size', type=float, default=BOX_SIZE,
                        help='Box size in kpc (default: %.1f)' % BOX_SIZE)
    parser.add_argument('--level', type=int, default=LEVEL,
                        help='AMR level for projection (default: %d)' % LEVEL)
    args = parser.parse_args()

    basepath = args.basepath.rstrip('/')
    if not basepath.endswith('run'):
        basepath = os.path.join(basepath, 'run')

    a_found, snap_file = find_snapshot(basepath, args.scale_factor)
    print("Snapshot: %s  (a=%.4f)" % (snap_file, a_found))

    yt.funcs.mylog.setLevel(50)
    ds = yt.load(snap_file)

    x0 = ds.arr(args.x, 'Mpccm/h').to_value('code_length')
    y0 = ds.arr(args.y, 'Mpccm/h').to_value('code_length')
    z0 = ds.arr(args.z, 'Mpccm/h').to_value('code_length')
    size = ds.arr(args.size, 'kpc').to_value('code_length')

    unit = 'kpc'
    projections = [('x', 'y', 0, 1), ('x', 'z', 0, 2)]

    fig, axs = plt.subplots(1, 2, figsize=(6, 3))
    axs[0].set_position([0.01, 0.02, 0.48, 0.96])
    axs[1].set_position([0.51, 0.02, 0.48, 0.96])

    for ax, (prj_x, prj_y, idx_x, idx_y) in zip(axs, projections):
        mesh, region = prj(
            ds, [x0, y0, z0], size, level=args.level,
            prj_x=prj_x, prj_y=prj_y,
            field='density', unit='Msun/pc**3', factor=0.6, weight='column',
        )
        mesh += 1e-10
        ax.imshow(
            mesh.T, origin='lower', cmap='magma',
            norm=LogNorm(vmin=VMIN, vmax=VMAX),
            extent=[region[idx_x].to_value(unit), region[idx_x+3].to_value(unit),
                    region[idx_y].to_value(unit), region[idx_y+3].to_value(unit)],
        )
        ax.set_xlabel('%s (kpc)' % prj_x)
        ax.set_ylabel('%s (kpc)' % prj_y)

    out_dir = os.path.join(basepath, 'analysis/zoom')
    os.makedirs(out_dir, exist_ok=True)
    fname = 'zoom_prj_a%.4f_x%.4f_y%.4f_z%.4f.png' % (a_found, args.x, args.y, args.z)
    output = os.path.join(out_dir, fname)
    plt.savefig(output, dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved: %s" % output)
