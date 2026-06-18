"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.

Generate gas surface density projections (3 views) of a small box around a given location.
Optionally find the top dense cores and produce per-core density/temperature/Mach panels.

Usage:
    python zoom_prj.py [basepath] [x] [y] [z] -a <scale_factor> [--cores] [--stars] [--level-dots]
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
from matplotlib.cm import ScalarMappable
import cmcrameri.cm as cmc
import yt

from prj import prj

# ---------------------------------------------------------------------------
# Main projection parameters
# ---------------------------------------------------------------------------
BOX_SIZE = 4.0   # kpc — full width of the main zoom box
LEVEL    = 12    # AMR level for main projection
VMIN     = 1e0   # Msun/pc^2  (column density color range)
VMAX     = 1e4

# ---------------------------------------------------------------------------
# Core zoom panel parameters  (--cores)
# ---------------------------------------------------------------------------
N_CORES       = 4      # number of dense cores to find
EXCLUSION_PC  = 100.0  # minimum separation between cores, pc
CORE_BOX_SIZE = 0.200  # kpc — full width of each core panel
CORE_LEVEL    = 18     # AMR level for core projections

# density row
CORE_VMIN = 1e0    # Msun/pc^2
CORE_VMAX = 1e4

# temperature row
TEMP_CMAP = cmc.vik
TEMP_VMIN = 1e0    # K
TEMP_VMAX = 1e3

# Mach number row
MACH_CMAP = cmc.vik_r
MACH_VMIN = 1e-1
MACH_VMAX = 1e0

# AMR level dots  (--level-dots)
ROOT_GRID    = 256   # root grid cells per side (for level → dx conversion)
LEVEL_COLORS = {14: 'blue', 15: 'cyan', 16: 'lime', 17: 'orange', 18: 'red'}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

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
    a_arr = np.array([e[0] for e in entries])
    idx = np.argmin(np.abs(a_arr - target_a))
    return entries[idx]


def find_dense_cores(box, n_cores=4, exclusion_pc=100.0):
    """Find n_cores densest cells, each separated by at least exclusion_pc (physical pc)."""
    cx = box[("index", "x")].to_value("kpc")
    cy = box[("index", "y")].to_value("kpc")
    cz = box[("index", "z")].to_value("kpc")
    density = box[("gas", "density")].to_value("g/cm**3")

    excl_kpc  = exclusion_pc * 1e-3
    remaining = np.arange(len(density))
    cores     = []

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


def extent_rel(region, core_y_kpc, core_x_kpc):
    """Relative extent for core panels: (Δy_min, Δy_max, Δx_min, Δx_max) in pc.
    prj_x='y' → horizontal; prj_y='x' → vertical."""
    return [region[1].to_value('pc') - core_y_kpc * 1e3,
            region[4].to_value('pc') - core_y_kpc * 1e3,
            region[0].to_value('pc') - core_x_kpc * 1e3,
            region[3].to_value('pc') - core_x_kpc * 1e3]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate 3-view gas density projections around a given location')
    parser.add_argument('basepath', nargs='?',
                        default='/scratch/08199/tg874988/art_simulations/hydro/zoomcloud/1116392',
                        help='Path to simulation folder (appends /run if needed)')
    parser.add_argument('x', type=float, nargs='?', default=8.322128272727333,
                        help='Center x (Mpccm/h)')
    parser.add_argument('y', type=float, nargs='?', default=8.137985234893238,
                        help='Center y (Mpccm/h)')
    parser.add_argument('z', type=float, nargs='?', default=7.7789764703224185,
                        help='Center z (Mpccm/h)')
    parser.add_argument('--scale-factor', '-a', type=float, required=True,
                        help='Target scale factor')
    parser.add_argument('--size', type=float, default=BOX_SIZE,
                        help='Main box full width in kpc (default: %.1f)' % BOX_SIZE)
    parser.add_argument('--level', type=int, default=LEVEL,
                        help='AMR level for main projection (default: %d)' % LEVEL)
    parser.add_argument('--cores', action='store_true',
                        help='Find top %d dense cores and plot per-core panels' % N_CORES)
    parser.add_argument('--stars', action='store_true',
                        help='Overlay star particles as green dots on main plot')
    parser.add_argument('--level-dots', action='store_true',
                        help='Mark AMR level cells as colored dots in core panels')
    args = parser.parse_args()

    basepath = args.basepath.rstrip('/')
    if not basepath.endswith('run'):
        basepath = os.path.join(basepath, 'run')

    a_found, snap_file = find_snapshot(basepath, args.scale_factor)
    print("Snapshot: %s  (a=%.4f)" % (snap_file, a_found))

    yt.funcs.mylog.setLevel(50)
    ds = yt.load(snap_file)

    x0   = ds.arr(args.x,    'Mpccm/h').to_value('code_length')
    y0   = ds.arr(args.y,    'Mpccm/h').to_value('code_length')
    z0   = ds.arr(args.z,    'Mpccm/h').to_value('code_length')
    size = ds.arr(args.size, 'kpc'    ).to_value('code_length')

    box = ds.box(
        ds.arr([x0 - size/2, y0 - size/2, z0 - size/2], 'code_length'),
        ds.arr([x0 + size/2, y0 + size/2, z0 + size/2], 'code_length'),
    )
    min_dx = box[("index", "dx")].min().to("pc")
    print("Smallest cell size in box: %.4f pc" % float(min_dx))

    # ---- star positions (optional) ----
    star_pos = None
    if args.stars:
        star_pos = {
            'x': box[("STAR", "POSITION_X")].to_value("kpc"),
            'y': box[("STAR", "POSITION_Y")].to_value("kpc"),
            'z': box[("STAR", "POSITION_Z")].to_value("kpc"),
        }
        print("Star particles in box: %d" % len(star_pos['x']))

    # ---- main 3-panel projection ----
    # (prj_x=horiz, prj_y=vert, idx_x, idx_y) — region indices: x=0, y=1, z=2
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
        xmin = region[idx_x  ].to_value('kpc')
        xmax = region[idx_x+3].to_value('kpc')
        ymin = region[idx_y  ].to_value('kpc')
        ymax = region[idx_y+3].to_value('kpc')
        ax.imshow(mesh.T, origin='lower', cmap='magma',
                  norm=LogNorm(vmin=VMIN, vmax=VMAX),
                  extent=[xmin, xmax, ymin, ymax])
        ax.set_aspect('equal')
        ax.set_axis_off()
        if star_pos is not None:
            ax.scatter(star_pos[prj_x], star_pos[prj_y],
                       s=2, color='lime', alpha=0.7, ec='none', rasterized=True)
        # 1 kpc ruler, lower right
        w, h = xmax - xmin, ymax - ymin
        rx2  = xmax - 0.05 * w
        rx1  = rx2 - 1.0
        ry   = ymin + 0.07 * h
        ax.plot([rx1, rx2], [ry, ry], lw=1.5, c='white', solid_capstyle='butt')
        ax.text((rx1 + rx2) / 2, ry + 0.03 * h, '1 kpc',
                ha='center', va='bottom', color='white', fontsize=8, fontweight='bold')

    # ---- core circles on main plot ----
    cores = None
    if args.cores:
        print("Finding top %d dense cores (exclusion: %.0f pc)..." % (N_CORES, EXCLUSION_PC))
        cores = find_dense_cores(box, n_cores=N_CORES, exclusion_pc=EXCLUSION_PC)
        for ax, (prj_x, prj_y, _, _) in zip(axs, projections):
            for core in cores:
                hx, hy = core[prj_x + '_kpc'], core[prj_y + '_kpc']
                ax.add_patch(plt.Circle((hx, hy), 0.1,
                                        fill=False, edgecolor='white',
                                        linewidth=1.0, linestyle='--'))
                ax.text(hx, hy + 0.12, str(core['rank']),
                        ha='center', va='bottom', color='white',
                        fontsize=8, fontweight='bold')

    out_dir = os.path.join(basepath, 'analysis/zoom')
    os.makedirs(out_dir, exist_ok=True)
    tag = 'a%.4f_x%.4f_y%.4f_z%.4f' % (a_found, args.x, args.y, args.z)
    plt.savefig(os.path.join(out_dir, 'zoom_prj_%s.png' % tag), dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved: zoom_prj_%s.png" % tag)

    # ---- per-core panels: density / temperature / Mach ----
    if cores is not None:
        cl_per_kpc = ds.arr(1.0, 'kpc').to_value('code_length')
        core_size  = CORE_BOX_SIZE * cl_per_kpc
        half_pc    = CORE_BOX_SIZE * 500.0   # half-width in pc
        X_H, m_H_g = 0.76, 1.673e-24        # hydrogen fraction, proton mass (g)

        ncores = len(cores)
        fig2, axs2 = plt.subplots(3, ncores, figsize=(3 * ncores, 9),
                                   sharex=True, sharey=True, constrained_layout=True)

        def _setup_ax(ax, row, col):
            ax.set_aspect('equal')
            ax.set_xlim(-half_pc, half_pc)
            ax.set_ylim(-half_pc, half_pc)
            if row == 2:
                ax.set_xlabel(r'$\Delta y$ (pc)')
            if col == 0:
                ax.set_ylabel(r'$\Delta x$ (pc)')

        domain_w = ds.domain_width[0].to_value('code_length')  # for level-dot calculation

        for i, core in enumerate(cores):
            cx_cl = core['x_kpc'] * cl_per_kpc
            cy_cl = core['y_kpc'] * cl_per_kpc
            cz_cl = core['z_kpc'] * cl_per_kpc
            ext   = None  # computed per projection below

            # row 0: density
            ax0 = axs2[0, i]
            mesh, region = prj(
                ds, [cx_cl, cy_cl, cz_cl], core_size, level=CORE_LEVEL,
                prj_x='y', prj_y='x',
                field='density', unit='Msun/pc**3', factor=0.6, weight='column',
            )
            ext = extent_rel(region, core['y_kpc'], core['x_kpc'])
            ax0.imshow(mesh.T + 1e-10, origin='lower', cmap='magma',
                       norm=LogNorm(vmin=CORE_VMIN, vmax=CORE_VMAX), extent=ext)
            _setup_ax(ax0, row=0, col=i)
            n_H = core['density'] * X_H / m_H_g
            ax0.set_title(r'$n_{\rm H} = %.1e\ {\rm cm}^{-3}$' % n_H, fontsize=10)
            ax0.text(-half_pc * 0.88, half_pc * 0.82, str(core['rank']),
                     ha='left', va='top', color='white', fontsize=14, fontweight='bold')

            # row 1: temperature
            ax1 = axs2[1, i]
            mesh_t, region_t = prj(
                ds, [cx_cl, cy_cl, cz_cl], core_size, level=CORE_LEVEL,
                prj_x='y', prj_y='x',
                field='temperature', unit='K', factor=0.6, weight='mass',
            )
            ax1.imshow(mesh_t.T + 1e-10, origin='lower', cmap=TEMP_CMAP,
                       norm=LogNorm(vmin=TEMP_VMIN, vmax=TEMP_VMAX),
                       extent=extent_rel(region_t, core['y_kpc'], core['x_kpc']))
            _setup_ax(ax1, row=1, col=i)

            # row 2: Mach number
            ax2 = axs2[2, i]
            mesh_m, region_m = prj(
                ds, [cx_cl, cy_cl, cz_cl], core_size, level=CORE_LEVEL,
                prj_x='y', prj_y='x',
                field='M', unit='1', factor=0.6, weight='mass',
            )
            ax2.imshow(mesh_m.T + 1e-10, origin='lower', cmap=MACH_CMAP,
                       norm=LogNorm(vmin=MACH_VMIN, vmax=MACH_VMAX),
                       extent=extent_rel(region_m, core['y_kpc'], core['x_kpc']))
            _setup_ax(ax2, row=2, col=i)

            # AMR level dots (optional)
            if args.level_dots:
                lev_box = ds.box(
                    ds.arr([cx_cl - core_size/2, cy_cl - core_size/2, cz_cl - core_size/2], 'code_length'),
                    ds.arr([cx_cl + core_size/2, cy_cl + core_size/2, cz_cl + core_size/2], 'code_length'),
                )
                dx_vals   = lev_box[("gas", "dx")].to_value('code_length')
                lev       = np.round(np.log2(domain_w / ROOT_GRID / dx_vals)).astype(int)
                cell_y    = lev_box[("index", "y")].to_value("kpc")
                cell_x    = lev_box[("index", "x")].to_value("kpc")
                print("  Core %d levels present: %s" % (core['rank'], np.unique(lev)))
                for lvl, color in LEVEL_COLORS.items():
                    mask = lev == lvl
                    if mask.any():
                        dy = (cell_y[mask] - core['y_kpc']) * 1e3
                        dx = (cell_x[mask] - core['x_kpc']) * 1e3
                        for ax_dot in (ax0, ax1, ax2):
                            ax_dot.scatter(dy, dx, s=4, color=color, alpha=0.8,
                                           ec='none', rasterized=True, label='L%d' % lvl)

        # colorbars — one per row
        for sm, ax_row, label in [
            (ScalarMappable(norm=LogNorm(vmin=CORE_VMIN, vmax=CORE_VMAX), cmap='magma'),
             axs2[0, :], r"Gas column density ($M_\odot\,{\rm pc}^{-2}$)"),
            (ScalarMappable(norm=LogNorm(vmin=TEMP_VMIN, vmax=TEMP_VMAX), cmap=TEMP_CMAP),
             axs2[1, :], "Temperature (K)"),
            (ScalarMappable(norm=LogNorm(vmin=MACH_VMIN, vmax=MACH_VMAX), cmap=MACH_CMAP),
             axs2[2, :], "Mach number"),
        ]:
            sm.set_array([])
            fig2.colorbar(sm, ax=ax_row, shrink=0.85, pad=0.02).set_label(label, fontsize=10)

        plt.savefig(os.path.join(out_dir, 'zoom_cores_%s.png' % tag), dpi=300, bbox_inches='tight')
        plt.close()
        print("Saved: zoom_cores_%s.png" % tag)
