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

BOX_SIZE      = 4.0    # kpc
LEVEL         = 12
VMIN, VMAX           = 1e0, 1e4
CORE_VMIN, CORE_VMAX = 1e2, 1e5
CORE_BOX_SIZE = 0.010  # kpc  (200 pc, -100 to +100 pc)
CORE_LEVEL    = 18
EXCLUSION_PC  = 100.0  # minimum separation between cores, pc


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


def find_dense_cores(ds, box, n_cores=4, exclusion_pc=100.0):
    """Find n_cores densest cells, each separated by at least exclusion_pc (physical pc)."""
    cx = box[("index", "x")].to_value("kpc")
    cy = box[("index", "y")].to_value("kpc")
    cz = box[("index", "z")].to_value("kpc")
    density = box[("gas", "density")].to_value("g/cm**3")

    excl_kpc = exclusion_pc * 1e-3
    remaining = np.arange(len(density))
    cores = []

    for rank in range(1, n_cores + 1):
        if len(remaining) == 0:
            break
        best = remaining[np.argmax(density[remaining])]
        cores.append(dict(
            rank=rank,
            x_kpc=cx[best], y_kpc=cy[best], z_kpc=cz[best],
            density=density[best],
        ))
        print("  Core %d: x=%.4f y=%.4f z=%.4f kpc,  rho=%.3e g/cm^3" % (
            rank, cx[best], cy[best], cz[best], density[best]))
        dist2 = ((cx[remaining] - cx[best])**2 +
                 (cy[remaining] - cy[best])**2 +
                 (cz[remaining] - cz[best])**2)
        remaining = remaining[dist2 > excl_kpc**2]

    return cores


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate xy/xz projections of a small box around a given location')
    parser.add_argument('basepath', nargs='?',
                        default='/scratch/08199/tg874988/art_simulations/hydro/mh3e12_km/1116392',
                        help='Path to simulation run folder')
    parser.add_argument('x', type=float, nargs='?', default=8.322128272727333,
                        help='Center x (Mpccm/h)')
    parser.add_argument('y', type=float, nargs='?', default=8.137985234893238,
                        help='Center y (Mpccm/h)')
    parser.add_argument('z', type=float, nargs='?', default=7.7789764703224185,
                        help='Center z (Mpccm/h)')
    parser.add_argument('--scale-factor', '-a', type=float, required=True,
                        help='Target scale factor')
    parser.add_argument('--size', type=float, default=BOX_SIZE,
                        help='Box size in kpc (default: %.1f)' % BOX_SIZE)
    parser.add_argument('--level', type=int, default=LEVEL,
                        help='AMR level for projection (default: %d)' % LEVEL)
    parser.add_argument('--cores', action='store_true',
                        help='Find top 4 dense cores and plot 200 pc zoom panels at level %d' % CORE_LEVEL)
    parser.add_argument('--stars', action='store_true',
                        help='Overlay star particles as green dots')
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

    box = ds.box(
        ds.arr([x0 - size/2, y0 - size/2, z0 - size/2], 'code_length'),
        ds.arr([x0 + size/2, y0 + size/2, z0 + size/2], 'code_length'),
    )
    min_dx = box[("index", "dx")].min().to("pc")
    print("Smallest cell size in box: %.4f pc" % float(min_dx))

    star_pos = None
    if args.stars:
        star_pos = {
            'x': box[("STAR", "POSITION_X")].to_value("kpc"),
            'y': box[("STAR", "POSITION_Y")].to_value("kpc"),
            'z': box[("STAR", "POSITION_Z")].to_value("kpc"),
        }
        print("Star particles in box: %d" % len(star_pos['x']))

    unit = 'kpc'
    # (prj_x=horiz, prj_y=vert, idx_x, idx_y)  — region indices: x=0, y=1, z=2
    projections = [
        ('y', 'x', 1, 0),   # x vs y: y horizontal, x vertical
        ('z', 'x', 2, 0),   # x vs z: z horizontal, x vertical
        ('z', 'y', 2, 1),   # y vs z: z horizontal, y vertical
    ]

    fig, axs = plt.subplots(1, 3, figsize=(9, 3))

    for ax, (prj_x, prj_y, idx_x, idx_y) in zip(axs, projections):
        mesh, region = prj(
            ds, [x0, y0, z0], size, level=args.level,
            prj_x=prj_x, prj_y=prj_y,
            field='density', unit='Msun/pc**3', factor=0.6, weight='column',
        )
        mesh += 1e-10
        xmin = region[idx_x].to_value(unit)
        xmax = region[idx_x+3].to_value(unit)
        ymin = region[idx_y].to_value(unit)
        ymax = region[idx_y+3].to_value(unit)
        ax.imshow(
            mesh.T, origin='lower', cmap='magma',
            norm=LogNorm(vmin=VMIN, vmax=VMAX),
            extent=[xmin, xmax, ymin, ymax],
        )
        ax.set_aspect('equal')
        ax.set_axis_off()
        if star_pos is not None:
            ax.scatter(star_pos[prj_x], star_pos[prj_y],
                       s=2, color='lime', alpha=0.7, ec='none', rasterized=True)
        # 1 kpc ruler, lower right
        w = xmax - xmin
        h = ymax - ymin
        rx2 = xmax - 0.05 * w
        rx1 = rx2 - 1.0
        ry  = ymin + 0.07 * h
        ax.plot([rx1, rx2], [ry, ry], lw=1.5, c='white', solid_capstyle='butt')
        ax.text((rx1 + rx2) / 2, ry + 0.03 * h, '1 kpc',
                ha='center', va='bottom', color='white', fontsize=8, fontweight='bold')

    # --- find cores before saving so circles appear on the main figure ---
    cores = None
    if args.cores:
        print("Finding top 4 dense cores (exclusion radius: %.0f pc)..." % EXCLUSION_PC)
        cores = find_dense_cores(ds, box, n_cores=4, exclusion_pc=EXCLUSION_PC)
        for ax, (prj_x, prj_y, _, _) in zip(axs, projections):
            for core in cores:
                hx = core[prj_x + '_kpc']
                hy = core[prj_y + '_kpc']
                circle = plt.Circle(
                    (hx, hy), 0.1,
                    fill=False, edgecolor='white', linewidth=1.0, linestyle='--',
                )
                ax.add_patch(circle)
                ax.text(hx, hy + 0.12, str(core['rank']),
                        ha='center', va='bottom', color='white',
                        fontsize=8, fontweight='bold')

    out_dir = os.path.join(basepath, 'analysis/zoom')
    os.makedirs(out_dir, exist_ok=True)
    fname = 'zoom_prj_a%.4f_x%.4f_y%.4f_z%.4f.png' % (a_found, args.x, args.y, args.z)
    output = os.path.join(out_dir, fname)
    plt.savefig(output, dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved: %s" % output)

    # --- dense core zoom panels ---
    if cores is not None:

        cl_per_kpc = ds.arr(1.0, 'kpc').to_value('code_length')
        core_size  = CORE_BOX_SIZE * cl_per_kpc  # code_length

        half_pc = CORE_BOX_SIZE * 500.0  # half-size in pc (0.2 kpc / 2 * 1000)
        X_H, m_H_g = 0.76, 1.673e-24   # hydrogen mass fraction, proton mass in g

        fig2, axs2 = plt.subplots(2, 2, figsize=(6, 6))
        for ax, core in zip(axs2.flat, cores):
            cx_cl = core['x_kpc'] * cl_per_kpc
            cy_cl = core['y_kpc'] * cl_per_kpc
            cz_cl = core['z_kpc'] * cl_per_kpc

            mesh, region = prj(
                ds, [cx_cl, cy_cl, cz_cl], core_size, level=CORE_LEVEL,
                prj_x='y', prj_y='x',
                field='density', unit='Msun/pc**3', factor=0.6, weight='column',
            )
            mesh += 1e-10
            ax.imshow(
                mesh.T, origin='lower', cmap='magma',
                norm=LogNorm(vmin=CORE_VMIN, vmax=CORE_VMAX),
                extent=[-half_pc, half_pc, -half_pc, half_pc],
            )
            ax.set_aspect('equal')
            ax.set_xlabel(r'$\Delta y$ (pc)')
            ax.set_ylabel(r'$\Delta x$ (pc)')

            # TEMP: mark level >= 17 cells as red dots
            cb = ds.box(
                ds.arr([cx_cl - core_size/2, cy_cl - core_size/2, cz_cl - core_size/2], 'code_length'),
                ds.arr([cx_cl + core_size/2, cy_cl + core_size/2, cz_cl + core_size/2], 'code_length'),
            )
            domain_w = ds.domain_width[0].to_value('code_length')
            dx = cb[("gas", "dx")].to_value('code_length')
            lev = np.round(np.log2(domain_w / 256 / dx)).astype(int)
            mask = lev >= 17
            if mask.any():
                cell_dy = (cb[("gas", "y")].to_value("kpc")[mask] - core['y_kpc']) * 1e3
                cell_dx = (cb[("gas", "x")].to_value("kpc")[mask] - core['x_kpc']) * 1e3
                ax.scatter(cell_dy, cell_dx, s=1, color='red', alpha=0.6, ec='none', rasterized=True)

            n_H = core['density'] * X_H / m_H_g
            ax.set_title(r'$n_{\rm H} = %.1e\ {\rm cm}^{-3}$' % n_H, fontsize=10)
            ax.text(-half_pc * 0.88, half_pc * 0.82, str(core['rank']),
                    ha='left', va='top', color='white', fontsize=14, fontweight='bold')

        plt.tight_layout()
        fname2 = 'zoom_cores_a%.4f_x%.4f_y%.4f_z%.4f.png' % (a_found, args.x, args.y, args.z)
        output2 = os.path.join(out_dir, fname2)
        plt.savefig(output2, dpi=300, bbox_inches='tight')
        plt.close()
        print("Saved: %s" % output2)
