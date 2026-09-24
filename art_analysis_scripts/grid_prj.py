"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.
"""

import argparse
import os
import sys
sys.path.append('.')
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
from art_io import load_art
from prj import prj
from datatype import dtype_tree
from track_tree import find_main_mpb
from galaxy_names import get_label

ROOT_PATH     = "/scratch/08199/tg874988/art_simulations/hydro"
ANALYSIS_PATH = os.path.join(ROOT_PATH, "analysis")
SIM_FOLDERS = {
    "km":  ["mh2e12_km",  "mh3e12_km",  "mh5e12_km"],
    "p12": ["mh2e12_p12", "mh3e12_p12", "mh5e12_p12"],
}
TARGET_Z = 5.0
TARGET_A = 1.0 / (1.0 + TARGET_Z)

# TEMPORARY: zoom the KM runs into the inner 2 kpc. Revert both dicts to 10.0 /
# 1.0 to restore the standard 10 kpc panels.
BOX_SIZE_KPC = {"km": 2.0, "p12": 10.0}   # projection box, kpc
RULER_KPC    = {"km": 0.5, "p12": 1.0}    # scale bar drawn on each panel, kpc

def weighted_median(values, weights):
    """Coordinate at which the cumulative weight first reaches half the total.

    Applied per axis, this is the marginal weighted median: unlike a mean it is
    not dragged off the galaxy by a handful of distant particles.
    """
    order = np.argsort(values)
    cw = np.cumsum(weights[order])
    if cw[-1] <= 0:
        raise ValueError("total weight is zero")
    return float(values[order][np.searchsorted(cw, 0.5 * cw[-1])])


def halo_sphere(ds, snapshot):
    """Sphere of radius Rvir around the halo center from the merger tree."""
    return ds.sphere(
        ds.arr([snapshot['x'], snapshot['y'], snapshot['z']], 'Mpccm/h'),
        ds.arr(snapshot['Rvir'], 'kpccm/h')
    )


def ruler_label(ruler_kpc):
    """Scale-bar text: sub-kpc rulers read better in pc (0.5 -> '500 pc')."""
    if ruler_kpc < 1.0:
        return r"%g pc" % (ruler_kpc * 1e3)
    return r"%g kpc" % ruler_kpc


def collect_basepaths(root_path, km_folders):
    basepaths = []
    for folder in km_folders:
        folder_path = os.path.join(root_path, folder)
        for entry in sorted(os.listdir(folder_path)):
            if not entry.isdigit():
                continue
            bp = os.path.join(folder_path, entry, "run")
            if os.path.isdir(bp):
                basepaths.append(bp)
    return basepaths


def get_snapshot_at_scalefactor(basepath, target_a):
    treepath = os.path.join(basepath, 'rockstar_halos/trees/tree_0_0_0.dat')
    snap_list = np.loadtxt(
        os.path.join(basepath, 'rockstar_halos/datasets.txt'),
        dtype={'names': ('filename', 'snap_original'), 'formats': ('U256', int)}
    )
    tree = np.loadtxt(treepath, skiprows=49, dtype=dtype_tree)
    mpb = find_main_mpb(tree)

    lastsnap_original = snap_list['snap_original'][-1]
    lastsnap_tree = mpb['Snap_idx'][-1]
    dsnap = int(lastsnap_original - lastsnap_tree)
    filename_list = snap_list['filename'][dsnap:]

    idx = np.argmin(np.abs(mpb['scale'] - target_a))
    snapshot = mpb[idx]
    filename = os.path.join(basepath, filename_list[snapshot['Snap_idx']])
    return snapshot, filename


def compute_panel(basepath):
    """Load data and compute projection; returns dict of numpy arrays, or None on failure."""
    try:
        snapshot, filename = get_snapshot_at_scalefactor(basepath, TARGET_A)
        ds = load_art(filename)

        x0 = (snapshot['x'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
        y0 = (snapshot['y'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
        z0 = (snapshot['z'] * ds.units.Mpccm / ds.units.h).to_value('code_length')

        if CENTER_STAR_MEDIAN:
            # Mass-weighted median position of the star particles inside Rvir:
            # a robust centre that ignores outliers, unlike the densest cell.
            d = halo_sphere(ds, snapshot)
            m = d['STAR', 'MASS'].to_value('Msun')
            name = get_label(basepath) or basepath
            if len(m) == 0:
                print("star median %s: no star particles within Rvir, using halo center" % name)
            else:
                xs = weighted_median(d['STAR', 'POSITION_X'].to_value('code_length'), m)
                ys = weighted_median(d['STAR', 'POSITION_Y'].to_value('code_length'), m)
                zs = weighted_median(d['STAR', 'POSITION_Z'].to_value('code_length'), m)
                kpc = (1.0 * ds.units.code_length).to_value('kpc')
                offset = kpc * np.sqrt((xs - x0)**2 + (ys - y0)**2 + (zs - z0)**2)
                print("star median %s: N=%d  Mstar=%.3e Msun (within Rvir)  "
                      "center=(%.3f, %.3f, %.3f) kpc  offset from halo center=%.3f kpc"
                      % (name, len(m), m.sum(), xs * kpc, ys * kpc, zs * kpc, offset))
                x0, y0, z0 = xs, ys, zs
        elif CENTER_MAX_DENSITY:
            # Densest gas cell anywhere inside Rvir -- note this can land in a
            # satellite rather than the central galaxy.
            sp = halo_sphere(ds, snapshot)
            imax = int(np.argmax(sp['gas', 'density']))
            x0 = sp['gas', 'x'][imax].to_value('code_length')
            y0 = sp['gas', 'y'][imax].to_value('code_length')
            z0 = sp['gas', 'z'][imax].to_value('code_length')

        size_cl = (BOX_SIZE * ds.units.kpc).to_value('code_length')
        unit_convert = (1.0 * ds.units.code_length).to_value('kpc')

        mesh, region = prj(
            ds, [x0, y0, z0], size_cl, level=10,
            prj_x="x", prj_y="y",
            field=FIELD, unit=FIELD_UNIT, factor=0.6, weight=WEIGHT
        )
        mesh += 1e-10

        cx, cy = x0 * unit_convert, y0 * unit_convert
        size = size_cl * unit_convert
        extent = [
            region[0].to_value('kpc'), region[3].to_value('kpc'),
            region[1].to_value('kpc'), region[4].to_value('kpc'),
        ]

        stars = None
        if SHOW_STARS:
            d = ds.box(region[:3], region[3:])
            stars = dict(
                x=d["STAR", "POSITION_X"].to_value('kpc'),
                y=d["STAR", "POSITION_Y"].to_value('kpc'),
                s=d["STAR", "MASS"].to_value("Msun") / 1e7,
            )

        print("Done: %s" % basepath)
        return dict(mesh=mesh, extent=extent, redshift=1/ds.scale_factor - 1,
                    cx=cx, cy=cy, size=size, stars=stars)
    except Exception as e:
        print("Skipped %s: %s" % (basepath, e))
        return None


def render_panel(ax, data, label):
    """Draw a pre-computed panel onto ax."""
    cx, cy, size = data['cx'], data['cy'], data['size']
    ruler = RULER

    ax.imshow(
        data['mesh'].T, origin="lower", norm=LogNorm(vmin=VMIN, vmax=VMAX), cmap=CMAP,
        rasterized=True, extent=data['extent']
    )

    if data['stars'] is not None:
        s = data['stars']
        ax.scatter(s['x'], s['y'], color='white', alpha=0.5, ec='none', s=s['s'], rasterized=True)

    stroke_ruler = [pe.withStroke(linewidth=5, foreground='white')] if TEXT_COLOR != 'w' else []
    stroke = [pe.withStroke(linewidth=3, foreground='white')] if TEXT_COLOR != 'w' else []

    ruler_x = cx + 0.4 * size
    ruler_y = cy - 0.43 * size
    ax.plot([ruler_x - ruler, ruler_x], [ruler_y, ruler_y], lw=1.5, c=TEXT_COLOR,
            path_effects=stroke_ruler)
    ax.text(ruler_x - 0.5 * ruler, ruler_y + 0.03 * size, ruler_label(ruler),
            ha="center", va="bottom", color=TEXT_COLOR, fontsize=12, fontweight='bold',
            path_effects=stroke)

    z_str = f"{data['redshift']:.1f}".rstrip('0').rstrip('.')
    ax.text(cx - 0.45 * size, cy + 0.45 * size,
            f"$z={z_str}$",
            ha="left", va="top", color=TEXT_COLOR, fontsize=15, fontweight='bold',
            path_effects=stroke)
    ax.text(cx + 0.45 * size, cy + 0.45 * size,
            label, ha="right", va="top", color=TEXT_COLOR, fontsize=15, fontweight='bold',
            path_effects=stroke)

    ax.set_xlim(cx - 0.5 * size, cx + 0.5 * size)
    ax.set_ylim(cy - 0.5 * size, cy + 0.5 * size)
    ax.set_axis_off()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='density',
                        choices=['density', 'temperature', 'mach', 'metallicity'])
    parser.add_argument('--sim-group', default='km', choices=['km', 'p12'])
    parser.add_argument('-z', '--redshift', type=float, default=TARGET_Z,
                        help='target redshift (default: %.1f)' % TARGET_Z)
    center_group = parser.add_mutually_exclusive_group()
    center_group.add_argument('--center-max-density', action='store_true',
                              help='center on the densest gas cell within Rvir (default: halo center)')
    center_group.add_argument('--center-star-median', action='store_true',
                              help='center on the mass-weighted median position of all star particles')
    parser.add_argument('--vmin', type=float, default=None,
                        help='colorbar minimum (default: per-mode value)')
    parser.add_argument('--vmax', type=float, default=None,
                        help='colorbar maximum (default: per-mode value)')
    parser.add_argument('--no-stars', action='store_true',
                        help='hide star particles (only applicable in density mode)')
    parser.add_argument('--parallel', type=int, default=1, metavar='N',
                        help='number of parallel worker processes (default: 1)')
    args = parser.parse_args()
    MODE = args.mode
    sim_group = args.sim_group
    SHOW_STARS = (MODE == 'density') and not args.no_stars
    TARGET_Z = args.redshift
    TARGET_A = 1.0 / (1.0 + TARGET_Z)
    CENTER_MAX_DENSITY = args.center_max_density
    CENTER_STAR_MEDIAN = args.center_star_median
    BOX_SIZE = BOX_SIZE_KPC[sim_group]
    RULER    = RULER_KPC[sim_group]
    print("Projection box: %g kpc (%s), z=%g" % (BOX_SIZE, sim_group, TARGET_Z))

    if MODE == "density":
        CMAP       = 'magma'
        FIELD      = "density"
        FIELD_UNIT = "Msun/pc**3"
        WEIGHT     = "column"
        VMIN       = 1e0
        VMAX       = 1e4
        CBAR_LABEL = r"Gas column density ($M_\odot\,{\rm pc}^{-2}$)"
        TEXT_COLOR = 'w'
    elif MODE == "temperature":
        CMAP       = cmc.vik
        FIELD      = "temperature"
        FIELD_UNIT = "K"
        WEIGHT     = "mass"
        VMIN       = 1e3
        VMAX       = 1e7
        CBAR_LABEL = "Temperature (K)"
        TEXT_COLOR = 'k'
    elif MODE == "mach":
        CMAP       = cmc.vik_r
        FIELD      = "M"
        FIELD_UNIT = "1"
        WEIGHT     = "mass"
        VMIN       = 1e-2
        VMAX       = 1e2
        CBAR_LABEL = "Mach number"
        TEXT_COLOR = 'k'
    else:  # metallicity
        CMAP       = cmc.vik
        FIELD      = "metallicity"
        FIELD_UNIT = "1"
        WEIGHT     = "mass"
        VMIN       = 1e-3
        VMAX       = 1e-1
        CBAR_LABEL = r"Metallicity ($Z/Z_\odot$)"
        TEXT_COLOR = 'k'

    # CLI overrides the per-mode defaults above
    if args.vmin is not None:
        VMIN = args.vmin
    if args.vmax is not None:
        VMAX = args.vmax
    print("Color range: %g to %g (%s)" % (VMIN, VMAX, MODE))

    yt.funcs.mylog.setLevel(50)

    basepaths = collect_basepaths(ROOT_PATH, SIM_FOLDERS[sim_group])
    assert len(basepaths) == 10, \
        "Expected 10 simulations, found %d: %s" % (len(basepaths), basepaths)
    z_str = "%g" % TARGET_Z
    os.makedirs(ANALYSIS_PATH, exist_ok=True)
    if CENTER_MAX_DENSITY:
        center_tag = "_maxdens"
    elif CENTER_STAR_MEDIAN:
        center_tag = "_starmed"
    else:
        center_tag = ""
    output_path = os.path.join(
        ANALYSIS_PATH, "grid_prj_%s_%s_z%s%s.pdf" % (sim_group, MODE, z_str, center_tag))

    # --- layout (inches) ---
    FIG_W    = 10.0  # figure width, inches
    MARGIN      = 0.05  # margin on left, top, bottom, inches
    RMARGIN     = 0.37  # right margin — must fit colorbar tick labels, inches
    GAP         = 0.05  # gap between panels, same horizontally and vertically, inches
    CBAR_W      = 0.30  # colorbar width, inches
    CBAR_GAP    = 0.10  # gap between panels and colorbar, inches
    CBAR_INSET  = 0.10  # inset at each end of colorbar so extreme tick labels aren't clipped, inches
    N_ROWS, N_COLS = 2, 5

    panel_area_w = FIG_W - MARGIN - RMARGIN - CBAR_GAP - CBAR_W
    panel_w = (panel_area_w - GAP*(N_COLS - 1)) / N_COLS  # inches; panel is square
    panel_h = panel_w
    FIG_H   = 2*MARGIN + N_ROWS*panel_h + GAP*(N_ROWS - 1)  # derived from square constraint

    fig, axs = plt.subplots(N_ROWS, N_COLS, figsize=(FIG_W, FIG_H))
    for r in range(N_ROWS):
        for c in range(N_COLS):
            left   = (MARGIN + c * (panel_w + GAP)) / FIG_W
            bottom = (MARGIN + (N_ROWS - 1 - r) * (panel_h + GAP)) / FIG_H
            axs[r, c].set_position([left, bottom, panel_w / FIG_W, panel_h / FIG_H])

    # colorbar: inset slightly at each end so extreme tick labels aren't clipped
    cbar_left   = (MARGIN + panel_area_w + CBAR_GAP) / FIG_W
    cbar_bottom = (MARGIN + CBAR_INSET) / FIG_H
    cbar_height = (N_ROWS * panel_h + (N_ROWS - 1) * GAP - 2 * CBAR_INSET) / FIG_H
    cbar_ax = fig.add_axes([cbar_left, cbar_bottom, CBAR_W / FIG_W, cbar_height])
    sm = ScalarMappable(norm=LogNorm(vmin=VMIN, vmax=VMAX), cmap=CMAP)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    cbar.ax.yaxis.set_ticks_position('right')
    cbar.ax.yaxis.set_label_position('right')
    cbar.ax.yaxis.set_tick_params(labelsize=12, labelcolor='black')
    cbar.ax.text(
        0.5, 0.5, CBAR_LABEL,
        transform=cbar.ax.transAxes, ha='center', va='center',
        color='black', fontsize=12, fontweight='bold', rotation=90,
        path_effects=[pe.withStroke(linewidth=3, foreground='white')]
    )

    if args.parallel > 1:
        with Pool(args.parallel) as pool:
            panel_data = pool.map(compute_panel, basepaths)
    else:
        panel_data = [compute_panel(bp) for bp in basepaths]

    for i, (ax, data) in enumerate(zip(axs.flat, panel_data)):
        if data is None:
            ax.set_visible(False)
        else:
            render_panel(ax, data, get_label(basepaths[i]) or chr(ord('a') + i))

    plt.savefig(output_path, dpi=500)
    plt.close()
    print("Saved: %s" % output_path)
