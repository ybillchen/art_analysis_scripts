"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.

Single-panel gas column density projection for use as a slide cover image.
No axes, no labels, no borders — the projection fills the whole canvas.

Usage:
    python cover_prj.py f -z 5
    python cover_prj.py mh3e12_km/1116392 -z 5 --level 11 --dpi 400
"""

import os
import sys
import argparse
sys.path.append(os.path.dirname(__file__))

MPLCONFIGDIR = os.path.join(os.path.dirname(__file__), ".matplotlib")
os.environ.setdefault("MPLCONFIGDIR", MPLCONFIGDIR)
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import numpy as np
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
plt.style.use(os.path.join(os.path.dirname(__file__), "sans.mplstyle"))
from matplotlib.colors import LogNorm
import yt

from prj import prj
from grid_prj import get_snapshot_at_scalefactor
from galaxy_names import resolve_galaxy, GALAXY_PATHS

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ROOT_PATH     = "/scratch/08199/tg874988/art_simulations/hydro"
ANALYSIS_PATH = os.path.join(ROOT_PATH, "analysis")
TARGET_Z   = 5.0
BOX_SIZE   = 10.0    # kpc, horizontal extent of the final image
LEVEL      = 11      # AMR projection level — mesh is ~2x finer than at level 10
ASPECT     = 16 / 9  # width / height; 16:9 fills a widescreen slide
FIG_W      = 13.333  # inches — 16:9 slide at 13.333 x 7.5 in
DPI        = 400     # 13.333 in x 400 dpi = 5333 px wide
CMAP       = 'magma'
VMIN       = 1e0
VMAX       = 1e4
STAR_SCALE = 1e7     # Msun per unit scatter area
STAR_ALPHA = 0.5


def main():
    parser = argparse.ArgumentParser(
        description='Single-panel borderless density projection for slide covers')
    parser.add_argument('galaxy',
                        help='galaxy label (a-j) or folder path relative to --root')
    parser.add_argument('--root', default=ROOT_PATH,
                        help='root simulation directory')
    parser.add_argument('-a', '--scale-factor', type=float, default=None,
                        help='target scale factor (overrides -z)')
    parser.add_argument('-z', '--redshift', type=float, default=TARGET_Z,
                        help='target redshift (default: %.1f)' % TARGET_Z)
    parser.add_argument('--size', type=float, default=BOX_SIZE,
                        help='horizontal image extent in kpc (default: %.1f)' % BOX_SIZE)
    parser.add_argument('--level', type=int, default=LEVEL,
                        help='AMR projection level (default: %d)' % LEVEL)
    parser.add_argument('--aspect', type=float, default=ASPECT,
                        help='image aspect ratio width/height (default: %.4f = 16:9)' % ASPECT)
    parser.add_argument('--fig-width', type=float, default=FIG_W,
                        help='figure width in inches (default: %.3f)' % FIG_W)
    parser.add_argument('--dpi', type=int, default=DPI,
                        help='output resolution in dpi (default: %d)' % DPI)
    parser.add_argument('--prj-x', default='x', choices=['x', 'y', 'z'],
                        help='horizontal projection axis (default: x)')
    parser.add_argument('--prj-y', default='y', choices=['x', 'y', 'z'],
                        help='vertical projection axis (default: y)')
    parser.add_argument('--cmap', default=CMAP,
                        help='colormap (default: %s)' % CMAP)
    parser.add_argument('--vmin', type=float, default=VMIN,
                        help='colorbar minimum (default: %g)' % VMIN)
    parser.add_argument('--vmax', type=float, default=VMAX,
                        help='colorbar maximum (default: %g)' % VMAX)
    parser.add_argument('--no-stars', action='store_true',
                        help='hide star particles')
    parser.add_argument('--star-scale', type=float, default=STAR_SCALE,
                        help='Msun per unit star marker area (default: %g)' % STAR_SCALE)
    parser.add_argument('-o', '--output', default=None,
                        help='output filename (default: cover_prj_{galaxy}_z{Z}.png)')
    args = parser.parse_args()

    yt.funcs.mylog.setLevel(50)

    target_a = args.scale_factor if args.scale_factor is not None \
        else 1.0 / (1.0 + args.redshift)

    # 'f' and friends are nicknames — resolve to the real folder path
    galaxy = resolve_galaxy(args.galaxy)
    basepath = os.path.join(args.root, galaxy, 'run')
    if galaxy != args.galaxy:
        print("Galaxy '%s' -> %s" % (args.galaxy, galaxy))
    elif not os.path.isdir(basepath):
        sys.exit("Unknown galaxy '%s': not a nickname (%s) and %s does not exist"
                 % (args.galaxy, ', '.join(sorted(GALAXY_PATHS)), basepath))

    snapshot, filename = get_snapshot_at_scalefactor(basepath, target_a)
    if not os.path.exists(filename):
        sys.exit("Snapshot not found: %s" % filename)
    print("Snapshot: %s (a=%.6f)" % (filename, snapshot['scale']))
    ds = yt.load(filename)

    x0 = (snapshot['x'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
    y0 = (snapshot['y'] * ds.units.Mpccm / ds.units.h).to_value('code_length')
    z0 = (snapshot['z'] * ds.units.Mpccm / ds.units.h).to_value('code_length')

    # Crop window in kpc: full width, height set by the aspect ratio.
    half_w = 0.5 * args.size
    half_h = 0.5 * args.size / args.aspect
    # Project a square large enough to cover whichever dimension is bigger.
    prj_size_kpc = 2.0 * max(half_w, half_h)
    prj_size_cl = (prj_size_kpc * ds.units.kpc).to_value('code_length')
    unit_convert = (1.0 * ds.units.code_length).to_value('kpc')

    mesh, region = prj(
        ds, [x0, y0, z0], prj_size_cl, level=args.level,
        prj_x=args.prj_x, prj_y=args.prj_y,
        field='density', unit='Msun/pc**3', factor=0.6, weight='column'
    )
    mesh += 1e-10

    idx = {'x': 0, 'y': 1, 'z': 2}
    ix, iy = idx[args.prj_x], idx[args.prj_y]
    extent = [
        region[ix].to_value('kpc'), region[ix + 3].to_value('kpc'),
        region[iy].to_value('kpc'), region[iy + 3].to_value('kpc'),
    ]

    cx = [x0, y0, z0][ix] * unit_convert
    cy = [x0, y0, z0][iy] * unit_convert

    # --- borderless single-panel figure ---
    fig_h = args.fig_width / args.aspect
    fig = plt.figure(figsize=(args.fig_width, fig_h))
    fig.patch.set_facecolor('k')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('k')
    ax.set_axis_off()

    ax.imshow(
        mesh.T, origin='lower', norm=LogNorm(vmin=args.vmin, vmax=args.vmax),
        cmap=args.cmap, extent=extent, interpolation='bilinear'
    )

    if not args.no_stars:
        d = ds.box(region[:3], region[3:])
        sx = d['STAR', 'POSITION_%s' % args.prj_x.upper()].to_value('kpc')
        sy = d['STAR', 'POSITION_%s' % args.prj_y.upper()].to_value('kpc')
        ss = d['STAR', 'MASS'].to_value('Msun') / args.star_scale
        ax.scatter(sx, sy, color='white', alpha=STAR_ALPHA, ec='none', s=ss)

    ax.set_xlim(cx - half_w, cx + half_w)
    ax.set_ylim(cy - half_h, cy + half_h)
    ax.set_aspect('equal')

    z_str = "%g" % (1.0 / ds.scale_factor - 1)
    if args.output is not None:
        output_path = args.output
    else:
        os.makedirs(ANALYSIS_PATH, exist_ok=True)
        output_path = os.path.join(
            ANALYSIS_PATH,
            "cover_prj_%s_z%s.png" % (galaxy.replace('/', '_'), z_str)
        )

    plt.savefig(output_path, dpi=args.dpi, facecolor='k')
    plt.close()
    print("Saved: %s  (%d x %d px)" % (
        output_path, round(args.fig_width * args.dpi), round(fig_h * args.dpi)))


if __name__ == '__main__':
    main()
