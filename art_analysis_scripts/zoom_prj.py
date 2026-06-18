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
from matplotlib.cm import ScalarMappable
import cmcrameri.cm as cmc
import yt

from prj import prj

BOX_SIZE      = 4.0    # kpc
LEVEL         = 12
VMIN, VMAX           = 1e0, 1e4
CORE_VMIN, CORE_VMAX = 1e0, 1e4
CORE_BOX_SIZE = 0.200  # kpc 
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
                        default='/scratch/08199/tg874988/art_simulations/hydro/zoomcloud/1116392',
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

    # --- dense core zoom panels (density row + Mach row) ---
    if cores is not None:

        cl_per_kpc  = ds.arr(1.0, 'kpc').to_value('code_length')
        core_size   = CORE_BOX_SIZE * cl_per_kpc
        half_pc     = CORE_BOX_SIZE * 500.0
        X_H, m_H_g = 0.76, 1.673e-24

        MACH_CMAP = cmc.vik_r
        MACH_VMIN, MACH_VMAX = 1e-1, 1e1
        TEMP_CMAP = cmc.vik
        TEMP_VMIN, TEMP_VMAX = 1e0, 1e3
        DENS_CBAR_LABEL = r"Gas column density ($M_\odot\,{\rm pc}^{-2}$)"
        TEMP_CBAR_LABEL = "Temperature (K)"
        MACH_CBAR_LABEL = "Mach number"

        # ruler: largest power-of-10 * {1,2,5} that fits in ~40% of half_pc
        def _nice_ruler(half):
            for scale in [500, 200, 100, 50, 20, 10, 5, 2, 1]:
                if scale <= half * 0.45:
                    return scale
            return 1

        def _extent_rel(reg, core):
            return [reg[1].to_value('pc') - core['y_kpc'] * 1e3,
                    reg[4].to_value('pc') - core['y_kpc'] * 1e3,
                    reg[0].to_value('pc') - core['x_kpc'] * 1e3,
                    reg[3].to_value('pc') - core['x_kpc'] * 1e3]

        def _finish_ax(ax, row, col, text_color='w'):
            ax.set_aspect('equal')
            ax.set_xlim(-half_pc, half_pc)
            ax.set_ylim(-half_pc, half_pc)
            if row == 2:
                ax.set_xlabel(r'$\Delta y$ (pc)')
            if col == 0:
                ax.set_ylabel(r'$\Delta x$ (pc)')

        ncores = len(cores)
        fig2, axs2 = plt.subplots(3, ncores, figsize=(3 * ncores, 9),
                                   sharex=True, sharey=True, constrained_layout=True)

        for i, core in enumerate(cores):
            cx_cl = core['x_kpc'] * cl_per_kpc
            cy_cl = core['y_kpc'] * cl_per_kpc
            cz_cl = core['z_kpc'] * cl_per_kpc

            # --- row 0: density ---
            ax0 = axs2[0, i]
            mesh, region = prj(
                ds, [cx_cl, cy_cl, cz_cl], core_size, level=CORE_LEVEL,
                prj_x='y', prj_y='x',
                field='density', unit='Msun/pc**3', factor=0.6, weight='column',
            )
            mesh += 1e-10
            ax0.imshow(mesh.T, origin='lower', cmap='magma',
                       norm=LogNorm(vmin=CORE_VMIN, vmax=CORE_VMAX),
                       extent=_extent_rel(region, core))
            _finish_ax(ax0, row=0, col=i, text_color='w')
            n_H = core['density'] * X_H / m_H_g
            ax0.set_title(r'$n_{\rm H} = %.1e\ {\rm cm}^{-3}$' % n_H, fontsize=10)
            ax0.text(-half_pc * 0.88, half_pc * 0.82, str(core['rank']),
                     ha='left', va='top', color='white', fontsize=14, fontweight='bold')

            if args.level_dots:
                lev_box = ds.box(
                    ds.arr([cx_cl - core_size/2, cy_cl - core_size/2, cz_cl - core_size/2], 'code_length'),
                    ds.arr([cx_cl + core_size/2, cy_cl + core_size/2, cz_cl + core_size/2], 'code_length'),
                )
                domain_w = ds.domain_width[0].to_value('code_length')
                dx_vals = lev_box[("gas", "dx")].to_value('code_length')
                lev = np.round(np.log2(domain_w / 256.0 / dx_vals)).astype(int)
                print("  Core %d levels in box: %s" % (core['rank'], np.unique(lev)))
                cell_y_kpc = lev_box[("index", "y")].to_value("kpc")
                cell_x_kpc = lev_box[("index", "x")].to_value("kpc")
                level_colors = {14: 'blue', 15: 'cyan', 16: 'lime', 17: 'orange', 18: 'red'}
                for lvl, color in level_colors.items():
                    mask = lev == lvl
                    if mask.any():
                        cell_dy = (cell_y_kpc[mask] - core['y_kpc']) * 1e3
                        cell_dx = (cell_x_kpc[mask] - core['x_kpc']) * 1e3
                        for ax_dot in (ax0, axs2[1, i], axs2[2, i]):
                            ax_dot.scatter(cell_dy, cell_dx, s=4, color=color, alpha=0.8,
                                           ec='none', rasterized=True, label='L%d' % lvl)

            # --- row 1: temperature ---
            ax1 = axs2[1, i]
            mesh_t, region_t = prj(
                ds, [cx_cl, cy_cl, cz_cl], core_size, level=CORE_LEVEL,
                prj_x='y', prj_y='x',
                field='temperature', unit='K', factor=0.6, weight='mass',
            )
            mesh_t += 1e-10
            ax1.imshow(mesh_t.T, origin='lower', cmap=TEMP_CMAP,
                       norm=LogNorm(vmin=TEMP_VMIN, vmax=TEMP_VMAX),
                       extent=_extent_rel(region_t, core))
            _finish_ax(ax1, row=1, col=i, text_color='k')

            # --- row 2: Mach ---
            ax2 = axs2[2, i]
            mesh_m, region_m = prj(
                ds, [cx_cl, cy_cl, cz_cl], core_size, level=CORE_LEVEL,
                prj_x='y', prj_y='x',
                field='M', unit='1', factor=0.6, weight='mass',
            )
            mesh_m += 1e-10
            ax2.imshow(mesh_m.T, origin='lower', cmap=MACH_CMAP,
                       norm=LogNorm(vmin=MACH_VMIN, vmax=MACH_VMAX),
                       extent=_extent_rel(region_m, core))
            _finish_ax(ax2, row=2, col=i, text_color='k')

        # colorbars — one per row, spanning all panels
        sm_dens = ScalarMappable(norm=LogNorm(vmin=CORE_VMIN, vmax=CORE_VMAX), cmap='magma')
        sm_dens.set_array([])
        cbar0 = fig2.colorbar(sm_dens, ax=axs2[0, :], shrink=0.85, pad=0.02)
        cbar0.set_label(DENS_CBAR_LABEL, fontsize=10)

        sm_temp = ScalarMappable(norm=LogNorm(vmin=TEMP_VMIN, vmax=TEMP_VMAX), cmap=TEMP_CMAP)
        sm_temp.set_array([])
        cbar1 = fig2.colorbar(sm_temp, ax=axs2[1, :], shrink=0.85, pad=0.02)
        cbar1.set_label(TEMP_CBAR_LABEL, fontsize=10)

        sm_mach = ScalarMappable(norm=LogNorm(vmin=MACH_VMIN, vmax=MACH_VMAX), cmap=MACH_CMAP)
        sm_mach.set_array([])
        cbar2 = fig2.colorbar(sm_mach, ax=axs2[2, :], shrink=0.85, pad=0.02)
        cbar2.set_label(MACH_CBAR_LABEL, fontsize=10)

        fname2 = 'zoom_cores_a%.4f_x%.4f_y%.4f_z%.4f.png' % (a_found, args.x, args.y, args.z)
        output2 = os.path.join(out_dir, fname2)
        plt.savefig(output2, dpi=300, bbox_inches='tight')
        plt.close()
        print("Saved: %s" % output2)
