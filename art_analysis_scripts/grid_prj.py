"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.
"""

import os
import sys
sys.path.append('.')
from copy import copy

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
import yt

from prj import prj
from datatype import dtype_tree
from track_tree import smooth_time_series, find_main_mpb

ROOT_PATH     = "/scratch/08199/tg874988/art_simulations/hydro"
ANALYSIS_PATH = os.path.join(ROOT_PATH, "analysis")
KM_FOLDERS = ["mh2e12_km", "mh3e12_km", "mh5e12_km"]
TARGET_Z = 5.0
TARGET_A = 1.0 / (1.0 + TARGET_Z)

CMAP = 'magma'
FIELD = "density"
FIELD_UNIT = "Msun/pc**3"
WEIGHT = "column"
VMIN = 1e0
VMAX = 1e4


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
        dtype={'names': ('filename', 'snap_original'), 'formats': ('U20', int)}
    )
    tree = np.loadtxt(treepath, skiprows=49, dtype=dtype_tree)
    mpb = find_main_mpb(tree)

    lastsnap_original = snap_list['snap_original'][-1]
    lastsnap_tree = mpb['Snap_idx'][-1]
    dsnap = int(lastsnap_original - lastsnap_tree)
    filename_list = snap_list['filename'][dsnap:]

    da = 0.0025
    a_mpb = mpb['scale']
    x_smooth = smooth_time_series(a_mpb, mpb['x'], da)
    y_smooth = smooth_time_series(a_mpb, mpb['y'], da)
    z_smooth = smooth_time_series(a_mpb, mpb['z'], da)

    idx = np.argmin(np.abs(a_mpb - target_a))
    snapshot = copy(mpb[idx])
    snapshot['x'] = x_smooth[idx]
    snapshot['y'] = y_smooth[idx]
    snapshot['z'] = z_smooth[idx]
    filename = os.path.join(basepath, filename_list[snapshot['Snap_idx']])
    return snapshot, filename


def plot_panel(ax, basepath, label):
    snapshot, filename = get_snapshot_at_scalefactor(basepath, TARGET_A)
    ds = yt.load(filename)

    x0 = (snapshot['x'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
    y0 = (snapshot['y'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
    z0 = (snapshot['z'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
    size = (10.0 * ds.units.kpc).to_value('code_length')
    level = 10
    factor = 0.6
    unit = 'kpc'
    unit_convert = (1.0 * ds.units.code_length).to_value(unit)
    ruler = 1.0

    prj_x, prj_y = "x", "y"
    idx_x, idx_y = 0, 1
    centers = [x0, y0, z0]

    mesh, region = prj(
        ds, [x0, y0, z0], size, level=level,
        prj_x=prj_x, prj_y=prj_y,
        field=FIELD, unit=FIELD_UNIT, factor=factor, weight=WEIGHT
    )
    mesh += 1e-10

    ax.imshow(
        mesh.T, origin="lower", norm=LogNorm(vmin=VMIN, vmax=VMAX), cmap=CMAP,
        extent=[
            region[idx_x].to_value(unit), region[idx_x + 3].to_value(unit),
            region[idx_y].to_value(unit), region[idx_y + 3].to_value(unit)
        ]
    )

    # young stars
    d = ds.box(region[:3], region[3:])
    age = ds.current_time.to_value("Myr") - d[("STAR", "creation_time")].to_value("Myr")
    mask = age < 750
    rgba = np.ones((mask.sum(), 4))
    rgba[:, 3] = np.exp(-age[mask] / 150.0)
    ax.scatter(
        d["STAR", "POSITION_%s" % prj_x.upper()][mask].to_value(unit),
        d["STAR", "POSITION_%s" % prj_y.upper()][mask].to_value(unit),
        fc=rgba, ec='none', s=d["STAR", "MASS"][mask].to_value("Msun") / 2e6
    )

    # ruler
    ruler_x = (centers[idx_x] + 0.43 * size) * unit_convert
    ruler_y = (centers[idx_y] - 0.33 * size) * unit_convert
    ax.plot([ruler_x - ruler, ruler_x], [ruler_y, ruler_y], lw=1.5, c="w")
    ax.text(ruler_x - 0.5 * ruler, ruler_y, r"%d %s" % (ruler, unit),
            ha="center", va="bottom", color="w", fontsize=10)

    # redshift label (top-left)
    ax.text(
        (centers[idx_x] - 0.45 * size) * unit_convert,
        (centers[idx_y] + 0.45 * size) * unit_convert,
        r"z = %.1f" % (1 / ds.scale_factor - 1),
        ha="left", va="top", color="w", fontsize=10
    )

    # galaxy label (top-right)
    ax.text(
        (centers[idx_x] + 0.45 * size) * unit_convert,
        (centers[idx_y] + 0.45 * size) * unit_convert,
        label, ha="right", va="top", color="w", fontsize=10
    )

    ax.set_xlim((centers[idx_x] - 0.5 * size) * unit_convert,
                (centers[idx_x] + 0.5 * size) * unit_convert)
    ax.set_ylim((centers[idx_y] - 0.5 * size) * unit_convert,
                (centers[idx_y] + 0.5 * size) * unit_convert)
    ax.set_axis_off()

    print("Done: %s" % basepath)


if __name__ == '__main__':
    yt.funcs.mylog.setLevel(50)

    basepaths = collect_basepaths(ROOT_PATH, KM_FOLDERS)
    assert len(basepaths) == 10, \
        "Expected 10 KM simulations, found %d: %s" % (len(basepaths), basepaths)

    sim_group = KM_FOLDERS[0].split('_')[-1]  # "km" or "p12"
    z_str = "%g" % TARGET_Z
    os.makedirs(ANALYSIS_PATH, exist_ok=True)
    output_path = os.path.join(ANALYSIS_PATH, "grid_prj_%s_z%s.png" % (sim_group, z_str))

    # --- layout (inches) ---
    FIG_W    = 10.0  # figure width, inches
    MARGIN   = 0.05  # margin on left, top, bottom, inches
    RMARGIN  = 0.50  # right margin — must fit colorbar tick labels, inches
    GAP      = 0.05  # gap between panels, same horizontally and vertically, inches
    CBAR_W   = 0.30  # colorbar width, inches
    CBAR_GAP = 0.10  # gap between panels and colorbar, inches
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

    # colorbar: spans full height of the panel area
    cbar_left   = (MARGIN + panel_area_w + CBAR_GAP) / FIG_W
    cbar_bottom = MARGIN / FIG_H
    cbar_height = (N_ROWS * panel_h + (N_ROWS - 1) * GAP) / FIG_H
    cbar_ax = fig.add_axes([cbar_left, cbar_bottom, CBAR_W / FIG_W, cbar_height])
    sm = ScalarMappable(norm=LogNorm(vmin=VMIN, vmax=VMAX), cmap=CMAP)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    cbar.ax.yaxis.set_ticks_position('right')
    cbar.ax.yaxis.set_label_position('right')
    cbar.ax.yaxis.set_tick_params(labelsize=10, labelcolor='black')
    cbar.ax.text(
        0.5, 0.5, r"$\Sigma_{\rm gas}$ [$M_\odot\,{\rm pc}^{-2}$]",
        transform=cbar.ax.transAxes, ha='center', va='center',
        color='black', fontsize=10, rotation=90,
        path_effects=[pe.withStroke(linewidth=2, foreground='white')]
    )

    for i, (ax, basepath) in enumerate(zip(axs.flat, basepaths)):
        label = chr(ord('a') + i)
        try:
            plot_panel(ax, basepath, label)
        except Exception as e:
            print("Skipped %s: %s" % (basepath, e))
            ax.set_visible(False)

    plt.savefig(output_path, dpi=150)
    plt.close()
    print("Saved: %s" % output_path)
