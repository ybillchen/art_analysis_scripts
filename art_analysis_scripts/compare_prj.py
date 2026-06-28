"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.

Multi-galaxy × multi-field projection comparison grid.
Each row is a galaxy, each column is a projection field (density, temperature, …).
Bottom row shows horizontal colorbars.

Usage:
    python compare_prj.py mh2e12_km/1234 mh3e12_km/5678 -z 5
    python compare_prj.py mh2e12_km/1234 -z 5 --parallel 4
"""

import os
import sys
import argparse
sys.path.append(os.path.dirname(__file__))
from multiprocessing import Pool

MPLCONFIGDIR = os.path.join(os.path.dirname(__file__), ".matplotlib")
os.environ.setdefault("MPLCONFIGDIR", MPLCONFIGDIR)
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import numpy as np
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
plt.style.use(os.path.join(os.path.dirname(__file__), "sans.mplstyle"))
print("Font: %s" % fm.findfont(fm.FontProperties(family=matplotlib.rcParams['font.family'])))
from matplotlib.colors import LogNorm
from matplotlib.cm import ScalarMappable
import matplotlib.patheffects as pe
import cmcrameri.cm as cmc
import yt

from prj import prj
from grid_prj import get_snapshot_at_scalefactor
from galaxy_names import get_label, resolve_galaxy

# ---------------------------------------------------------------------------
# Column definitions — add/remove/reorder entries to change the grid columns
# ---------------------------------------------------------------------------
COLUMNS = [
    dict(name='density',     field='density',     unit='Msun/pc**3', weight='column',
         cmap='magma',       vmin=1e0,  vmax=1e4,
         label=r"Gas column density ($M_\odot\,{\rm pc}^{-2}$)", text_color='w',
         show_stars=True),
    dict(name='temperature', field='temperature', unit='K',          weight='mass',
         cmap=cmc.vik,       vmin=1e3,  vmax=1e7,
         label="Temperature (K)",                                    text_color='k'),
    dict(name='mach',        field='M',           unit='1',          weight='mass',
         cmap=cmc.vik_r,     vmin=1e-2, vmax=1e2,
         label="Mach number",                                        text_color='k'),
    dict(name='metallicity', field='metallicity', unit='1',          weight='mass',
         cmap=cmc.vik,       vmin=1e-3, vmax=1e-1,
         label=r"Metallicity ($Z/Z_\odot$)",                         text_color='k'),
]

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ROOT_PATH     = "/scratch/08199/tg874988/art_simulations/hydro"
ANALYSIS_PATH = os.path.join(ROOT_PATH, "analysis")
TARGET_Z  = 5.0
TARGET_A  = 1.0 / (1.0 + TARGET_Z)
BOX_SIZE  = 10.0   # kpc
LEVEL     = 10
SHOW_STARS = True

# ---------------------------------------------------------------------------
# Layout (inches)
# ---------------------------------------------------------------------------
FIG_W      = 10.0
MARGIN     = 0.05   # left / top / right margin
BMARGIN    = 0.35   # bottom margin (colorbar + tick labels)
GAP        = 0.05   # gap between panels
CBAR_H     = 0.15   # colorbar strip height
CBAR_INSET = 0.15   # inset at each end so tick labels don't overlap


# ---------------------------------------------------------------------------
# Panel rendering (adapted from grid_prj.render_panel, parameterised)
# ---------------------------------------------------------------------------

def render_panel(ax, data, cmap, vmin, vmax, text_color, label=None, show_z=True):
    cx, cy, size = data['cx'], data['cy'], data['size']
    ruler = 1.0

    ax.imshow(
        data['mesh'].T, origin="lower", norm=LogNorm(vmin=vmin, vmax=vmax), cmap=cmap,
        rasterized=True, extent=data['extent']
    )

    if data['stars'] is not None:
        s = data['stars']
        ax.scatter(s['x'], s['y'], color='white', alpha=0.5,
                   ec='none', s=s['s'], rasterized=True)

    stroke_ruler = [pe.withStroke(linewidth=5, foreground='white')] if text_color != 'w' else []
    stroke = [pe.withStroke(linewidth=3, foreground='white')] if text_color != 'w' else []

    ruler_x = cx + 0.4 * size
    ruler_y = cy - 0.43 * size
    ax.plot([ruler_x - ruler, ruler_x], [ruler_y, ruler_y], lw=1.5, c=text_color,
            path_effects=stroke_ruler)
    ax.text(ruler_x - 0.5 * ruler, ruler_y + 0.3, r"%d %s" % (ruler, 'kpc'),
            ha="center", va="bottom", color=text_color, fontsize=12, fontweight='bold',
            path_effects=stroke)

    if show_z:
        z_str = f"{data['redshift']:.1f}".rstrip('0').rstrip('.')
        ax.text(cx - 0.45 * size, cy + 0.45 * size,
                f"$z={z_str}$",
                ha="left", va="top", color=text_color, fontsize=15, fontweight='bold',
                path_effects=stroke)

    if label is not None:
        ax.text(cx + 0.45 * size, cy + 0.45 * size,
                label, ha="right", va="top", color=text_color, fontsize=15, fontweight='bold',
                path_effects=stroke)

    ax.set_xlim(cx - 0.5 * size, cx + 0.5 * size)
    ax.set_ylim(cy - 0.5 * size, cy + 0.5 * size)
    ax.set_axis_off()


# ---------------------------------------------------------------------------
# Data computation (one call per galaxy row; safe for multiprocessing.Pool)
# ---------------------------------------------------------------------------

def compute_row(basepath):
    """Load one galaxy and compute projections for all columns. Returns list of dicts or None."""
    try:
        snapshot, filename = get_snapshot_at_scalefactor(basepath, TARGET_A)
        ds = yt.load(filename)

        x0 = (snapshot['x'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
        y0 = (snapshot['y'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
        z0 = (snapshot['z'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
        size_cl = (BOX_SIZE * ds.units.kpc).to_value('code_length')
        unit_convert = (1.0 * ds.units.code_length).to_value('kpc')

        cx_kpc = x0 * unit_convert
        cy_kpc = y0 * unit_convert
        size_kpc = size_cl * unit_convert

        results = []
        stars_cached = None
        for col in COLUMNS:
            mesh, region = prj(
                ds, [x0, y0, z0], size_cl, level=LEVEL,
                prj_x="x", prj_y="y",
                field=col['field'], unit=col['unit'], factor=0.6, weight=col['weight']
            )
            mesh += 1e-10

            extent = [
                region[0].to_value('kpc'), region[3].to_value('kpc'),
                region[1].to_value('kpc'), region[4].to_value('kpc'),
            ]

            stars = None
            if col.get('show_stars') and SHOW_STARS:
                if stars_cached is None:
                    d = ds.box(region[:3], region[3:])
                    stars_cached = dict(
                        x=d["STAR", "POSITION_X"].to_value('kpc'),
                        y=d["STAR", "POSITION_Y"].to_value('kpc'),
                        s=d["STAR", "MASS"].to_value("Msun") / 1e7,
                    )
                stars = stars_cached

            results.append(dict(
                mesh=mesh, extent=extent,
                redshift=1.0 / ds.scale_factor - 1,
                cx=cx_kpc, cy=cy_kpc, size=size_kpc, stars=stars,
            ))

        print("Done: %s" % basepath)
        return results
    except Exception as e:
        print("Skipped %s: %s" % (basepath, e))
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Multi-galaxy × multi-field projection comparison grid')
    parser.add_argument('galaxies', nargs='*',
                        default=['f', 'h'],
                        help='galaxy labels or folder paths relative to --root (default: f h)')
    parser.add_argument('--root', default=ROOT_PATH,
                        help='root simulation directory')
    parser.add_argument('-a', '--scale-factor', type=float, default=None,
                        help='target scale factor (overrides -z)')
    parser.add_argument('-z', '--redshift', type=float, default=TARGET_Z,
                        help='target redshift (default: %.1f)' % TARGET_Z)
    parser.add_argument('--size', type=float, default=BOX_SIZE,
                        help='projection box size in kpc (default: %.1f)' % BOX_SIZE)
    parser.add_argument('--level', type=int, default=LEVEL,
                        help='AMR projection level (default: %d)' % LEVEL)
    parser.add_argument('--no-stars', action='store_true',
                        help='hide star particles (only applicable in density mode)')
    parser.add_argument('--parallel', type=int, default=1, metavar='N',
                        help='number of parallel worker processes (default: 1)')
    parser.add_argument('--labels', nargs='+', default=None,
                        help='panel labels, one per galaxy (default: a, b, c, ...)')
    parser.add_argument('-o', '--output', default=None,
                        help='output filename (default: compare_prj_z{Z}.pdf)')
    args = parser.parse_args()

    # --- resolve module-level globals from CLI ---
    if args.scale_factor is not None:
        TARGET_A = args.scale_factor
    else:
        TARGET_A = 1.0 / (1.0 + args.redshift)
    BOX_SIZE   = args.size
    LEVEL      = args.level
    SHOW_STARS = not args.no_stars

    yt.funcs.mylog.setLevel(50)

    galaxies = [resolve_galaxy(g) for g in args.galaxies]
    basepaths = [os.path.join(args.root, g, 'run') for g in galaxies]
    N = len(basepaths)   # rows (galaxies)
    M = len(COLUMNS)     # columns (fields)

    if args.labels is not None:
        labels = args.labels
    else:
        labels = [get_label(bp) or chr(ord('a') + i) for i, bp in enumerate(basepaths)]

    # --- compute all panels ---
    if args.parallel > 1:
        with Pool(args.parallel) as pool:
            all_rows = pool.map(compute_row, basepaths)
    else:
        all_rows = [compute_row(bp) for bp in basepaths]

    # --- figure layout ---
    panel_w = (FIG_W - 2 * MARGIN - GAP * (M - 1)) / M
    panel_h = panel_w   # square panels
    FIG_H   = MARGIN + BMARGIN + N * panel_h + (N - 1) * GAP

    fig, axs = plt.subplots(N, M, figsize=(FIG_W, FIG_H), squeeze=False)

    for r in range(N):
        for c in range(M):
            left   = (MARGIN + c * (panel_w + GAP)) / FIG_W
            bottom = (BMARGIN + (N - 1 - r) * (panel_h + GAP)) / FIG_H
            axs[r, c].set_position([left, bottom, panel_w / FIG_W, panel_h / FIG_H])

    # --- render panels ---
    for r in range(N):
        row_data = all_rows[r]
        if row_data is None:
            for c in range(M):
                axs[r, c].set_visible(False)
            continue
        for c, col in enumerate(COLUMNS):
            render_panel(
                axs[r, c], row_data[c],
                cmap=col['cmap'], vmin=col['vmin'], vmax=col['vmax'],
                text_color=col['text_color'],
                label=labels[r] if c == 0 else None,
                show_z=(c == 0),
            )

    # --- horizontal colorbars (bottom row, text-inside-bar like grid_prj) ---
    for c, col in enumerate(COLUMNS):
        cbar_left = (MARGIN + c * (panel_w + GAP) + CBAR_INSET) / FIG_W
        cbar_w    = (panel_w - 2 * CBAR_INSET) / FIG_W
        cbar_bottom = MARGIN / FIG_H
        cbar_ax = fig.add_axes([cbar_left, cbar_bottom, cbar_w, CBAR_H / FIG_H])
        sm = ScalarMappable(norm=LogNorm(vmin=col['vmin'], vmax=col['vmax']), cmap=col['cmap'])
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
        cbar.ax.tick_params(labelsize=9)
        cbar.ax.text(
            0.5, 0.5, col['label'],
            transform=cbar.ax.transAxes, ha='center', va='center',
            color='black', fontsize=9, fontweight='bold',
            path_effects=[pe.withStroke(linewidth=3, foreground='white')]
        )

    # --- save ---
    z_str = "%g" % (1.0 / TARGET_A - 1)
    os.makedirs(ANALYSIS_PATH, exist_ok=True)
    if args.output is not None:
        output_path = args.output
    else:
        output_path = os.path.join(ANALYSIS_PATH, "compare_prj_z%s.pdf" % z_str)
    plt.savefig(output_path, dpi=500)
    plt.close()
    print("Saved: %s" % output_path)
