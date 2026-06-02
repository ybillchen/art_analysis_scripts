"""
BSD 3-Clause License
Copyright (c) 2025-2025 Yingtian Chen
All rights reserved.
"""


import os
import sys
import argparse
import h5py
sys.path.append('.')
from copy import copy

import numpy as np
import matplotlib
matplotlib.use("agg")
from matplotlib.colors import LogNorm
import matplotlib.pyplot as plt
import yt

from prj import prj
from age_spreads import *
from utils import *
from datatype import *
from skirt_interface import art2skirt

#ID DescID Mvir Vmax Vrms Rvir Rs Np X Y Z VX VY VZ JX JY JZ Spin rs_klypin Mvir_all M200b M200c M500c M2500c Xoff Voff spin_bullock b_to_a c_to_a A[x] A[y] A[z] b_to_a(500c) c_to_a(500c) A[x](500c) A[y](500c) A[z](500c) T/|U| M_pe_Behroozi M_pe_Diemer Type SM Gas BH_Mass


def get_cutouts(ds, halocat, mhmin=1e10):
    mh = ds.arr(halocat[:,2], 'Msun/h')
    halos = halocat[mh.to_value('Msun')>mhmin]
    mh = mh[mh.to_value('Msun')>mhmin]
    if len(halos) == 0:
        return []
    centers = ds.arr(halos[:,8:11], 'Mpccm/h')
    rvirs = ds.arr(halos[:,5], 'kpccm/h')

    cutouts = []
    for i in range(len(halos)):
        center = centers[i]
        rvir = rvirs[i]
        cutouts.append(ds.sphere(center, rvir))
    return cutouts, mh

def analyse(simpath, halocatpath, savebase, all_data=False):

    ds = yt.load(simpath)
    halocat = np.loadtxt(halocatpath)

    if all_data:
        cutouts, mh = [ds.all_data()], [-1]
    else:
        cutouts, mh = get_cutouts(ds, halocat)

    np.savetxt('/home1/08199/tg874988/sfh_cimf/haloinfo_%s_z6.txt'%savebase, 
        np.c_[np.arange(len(mh)), mh.to_value('Msun')], fmt='%d %.6e')

    for i, d in enumerate(cutouts):

        initial_mass = d[('STAR', 'initial_mass')].to_value('Msun')
        f_bound0 = get_fbound0(d)
        t_form = d[("STAR", "creation_time")].to_value("Myr")
        t_ave = ave_time(d)
        out = np.column_stack([initial_mass, f_bound0, t_form, t_ave])

        savename = '/home1/08199/tg874988/sfh_cimf/%s_z6_halo%d.txt'%(savebase,i)
        if all_data:
            savename = savename.replace('halo%d'%i, 'all_data')
        np.savetxt(savename, out)

def smooth_time_series(t, x, tau, kernel='gaussian'):
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)

    if t.shape != x.shape:
        raise ValueError("t and x must have the same shape")

    n = t.size
    x_smooth = np.empty_like(x, dtype=float)

    for i in range(n):
        dt = t - t[i]

        if kernel == 'gaussian':
            w = np.exp(-0.5 * (dt / tau)**2)
        elif kernel == 'boxcar':
            w = (np.abs(dt) <= tau).astype(float)
        else:
            raise ValueError("Unknown kernel: choose 'gaussian' or 'boxcar'")

        # Avoid division by zero if tau is too small
        w_sum = w.sum()
        if w_sum == 0:
            x_smooth[i] = x[i]
        else:
            w /= w_sum
            x_smooth[i] = np.sum(w * x)

    return x_smooth

def find_main_mpb(tree):
    '''
    find the main halo
    '''
    snap = tree['Snap_idx'].astype(int)
    lastsnap = np.max(snap)
    tree_lastsnap = tree[snap==lastsnap]
    mvir_lastsnap = tree_lastsnap['Mvir']

    arg_main = np.argmax(mvir_lastsnap) # main halo is the most massive
    mainleafid = tree_lastsnap['Last_mainleaf_depthfirst_ID'][arg_main]
    mpb_main = tree[tree['Last_mainleaf_depthfirst_ID']==mainleafid]

    return mpb_main[mpb_main['Snap_idx'].argsort()] # sort by snap number

def find_major_merger_branch(tree):
    '''
    Find the secondary progenitor branch with the highest peak virial mass —
    i.e., the most important merger that contributed to the main halo.
    Returns None if no secondary branches exist.
    '''
    mpb = find_main_mpb(tree)
    mpb_leafid = mpb['Last_mainleaf_depthfirst_ID'][0]

    non_mpb = tree[tree['Last_mainleaf_depthfirst_ID'] != mpb_leafid]
    if len(non_mpb) == 0:
        return None

    branch_ids = np.unique(non_mpb['Last_mainleaf_depthfirst_ID'])
    peak_mvir = np.array([
        non_mpb[non_mpb['Last_mainleaf_depthfirst_ID'] == bid]['Mvir'].max()
        for bid in branch_ids
    ])

    best_id = branch_ids[np.argmax(peak_mvir)]
    branch = non_mpb[non_mpb['Last_mainleaf_depthfirst_ID'] == best_id]
    return branch[branch['Snap_idx'].argsort()]

def save_mpb(mpb):
    np.savetxt(mpb, fmt=fmt_tree)

def make_prj_single(
    snapshot, filename, basepath, cmap='magma',
    field="density", field_unit="Msun/pc**3", weight="volume", 
    vmin=1e-4, vmax=1e0, scale="linear"
):

    ds = yt.load(filename)

    x0 = (snapshot['x']*ds.units.Mpccm/ds.units.h).to_value('code_length')
    y0 = (snapshot['y']*ds.units.Mpccm/ds.units.h).to_value('code_length')
    z0 = (snapshot['z']*ds.units.Mpccm/ds.units.h).to_value('code_length')
    size = (10.0*ds.units.kpc).to_value('code_length')

    level = 10
    factor = 0.6

    unit = 'kpc'
    unit_convert = (1.0*ds.units.code_length).to_value(unit)

    ruler = 1.0 # in unit

    # fig, ax0 = plt.subplots(1, 1, figsize=(3,3))
    # ax0.set_position([0.0, 0.0, 1.0, 1.0])
    # axs = [ax0]
    fig, axs = plt.subplots(1, 2,  figsize=(6,3))
    axs[0].set_position([0.01, 0.02, 0.48, 0.96])
    axs[1].set_position([0.51, 0.02, 0.48, 0.96])

    prjs = ["x", "y", "z"]
    centers = [x0, y0, z0]

    for ax0, idx_x, idx_y in zip(axs, [0, 2], [1, 1]):

        # gas
        mesh, region = prj(ds, [x0, y0, z0], 
            size, level=level, prj_x=prjs[idx_x], prj_y=prjs[idx_y], 
            field=field, unit=field_unit, factor=factor, weight=weight, scale=scale
        )
        mesh += 1e-10 # a small offset to avoid zero
        ax0.imshow(
            mesh.T, origin="lower", norm=LogNorm(vmin=vmin, vmax=vmax), cmap=cmap,
            extent=[region[idx_x].to_value(unit), region[idx_x+3].to_value(unit),
                region[idx_y].to_value(unit), region[idx_y+3].to_value(unit)]
        )

        # stars
        d = ds.box(region[:3], region[3:])
        age = ds.current_time.to_value("Myr") - d[("STAR", "creation_time")].to_value("Myr")
        mask = age < 750
        # mask = age < 100000
        rgba_colors = np.ones((len(age[mask]),4))
        rgba_colors[:, 3] = np.exp(-age[mask]/150.0)
        ax0.scatter(
            d["STAR", "POSITION_%s"%prjs[idx_x].upper()][mask].to_value(unit),
            d["STAR", "POSITION_%s"%prjs[idx_y].upper()][mask].to_value(unit), 
            fc=rgba_colors, ec='none', s=d["STAR", "MASS"][mask].to_value("Msun")/5e5, 
            # alpha=0.7
        )

        # ruler
        ax0.plot(
            [
                (centers[idx_x]+0.43*size)*unit_convert-ruler, 
                (centers[idx_x]+0.43*size)*unit_convert
            ], [
                (centers[idx_y]-0.43*size)*unit_convert, 
                (centers[idx_y]-0.43*size)*unit_convert
            ], lw=1.5, c="w"
        )
        ax0.text(
            (centers[idx_x]+0.43*size)*unit_convert-0.5*ruler, 
            (centers[idx_y]-0.42*size)*unit_convert, 
            r"%d %s"%(ruler,unit), ha="center", va="bottom", color="w", fontsize=12
        )
        ax0.text(
            (centers[idx_x]-0.45*size)*unit_convert, 
            (centers[idx_y]+0.45*size)*unit_convert, 
            r"z = %.1f"%((1/ds.scale_factor)-1), ha="left", va="top", color="w", fontsize=15
        )

        ax0.set_xlabel(r"%s (%s)"%(prjs[idx_x], unit))
        ax0.set_ylabel(r"%s (%s)"%(prjs[idx_y], unit))
        ax0.set_axis_off()
        # ax0.set_aspect("equal")
        ax0.set_xlim(
            (centers[idx_x]-0.5*size)*unit_convert, 
            (centers[idx_x]+0.5*size)*unit_convert)
        ax0.set_ylim(
            (centers[idx_y]-0.5*size)*unit_convert, 
            (centers[idx_y]+0.5*size)*unit_convert)

    # axs[0].text(
    #     (centers[idx_x]-0.45*size)*unit_convert, 
    #     (centers[idx_y]+0.45*size)*unit_convert, 
    #     r"$R_{\rm GMC} = %d$ pc"%10, ha="left", va="top", color="w")

    # plt.tight_layout()
    output_path = filename.replace('out/snap_', f'analysis/prj_mpb/prj_{field}_').replace('.art', '.png')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, pad_inches=0.0, dpi=300)
    plt.close()

def make_prj_along_mpb(
    mpb, filename_list_for_tree, basepath, scalefactor=None, cmap='magma',
    field="density", field_unit="Msun/pc**3", weight="volume", 
    vmin=1e-4, vmax=1e0, scale="linear"
):
    a_mpb = mpb['scale']
    da = 0.0025
    x_smooth = smooth_time_series(a_mpb, mpb['x'], da)
    y_smooth = smooth_time_series(a_mpb, mpb['y'], da)
    z_smooth = smooth_time_series(a_mpb, mpb['z'], da)
    if scalefactor is None:
        a_list = 1 / (1+np.array([12, 10, 8, 6, 5]))
    else:
        a_list = np.array([scalefactor])
    for idx in range(len(mpb)):
        snapshot = copy(mpb[idx])
        currentsnap = snapshot['Snap_idx']
        currenta = snapshot['scale']
        if currenta >= a_list[0]:
            a_list = np.delete(a_list, 0)
            filename = os.path.join(basepath, filename_list_for_tree[currentsnap])
            snapshot['x'] = x_smooth[idx]
            snapshot['y'] = y_smooth[idx]
            snapshot['z'] = z_smooth[idx]
            print(idx, currentsnap, currenta, filename)
            # if idx % 100 == 0:
            # if idx == len(mpb) - 1:
            make_prj_single(
                snapshot, filename, basepath, cmap=cmap,
                field=field, field_unit=field_unit, weight=weight, 
                vmin=vmin, vmax=vmax, scale=scale,
            )
            if len(a_list) == 0:
                break

def star_at_scalefactor(mpb, filename_list_for_tree, basepath, scalefactor=None, suffix=''):
    if scalefactor is None:
        idx = -1
    else:
        idx = np.argmin(np.abs(mpb['scale'] - scalefactor))
    snapshot = copy(mpb[idx])
    snap = snapshot['Snap_idx']
    filename = os.path.join(basepath, filename_list_for_tree[snap])

    ds = yt.load(filename)

    center = ds.arr([snapshot['x'], snapshot['y'], snapshot['z']], 'Mpccm/h')
    rvir = ds.arr(snapshot['Rvir'], 'kpccm/h')

    d = ds.sphere(center, rvir)

    # Build output datasets dynamically; skip any that require missing fields.
    col_names = []
    col_arrays = []

    def try_add(name, fn):
        try:
            col_names.append(name)
            col_arrays.append(fn())
        except Exception:
            pass

    try_add('initial_mass', lambda: d[('STAR', 'initial_mass')].to_value('Msun'))
    try_add('mass',         lambda: d[('STAR', 'MASS')].to_value('Msun'))
    try_add('f_bound0',     lambda: get_fbound0(d))          # needs INITIAL_BOUND_FRACTION
    try_add('t_form',       lambda: d[("STAR", "creation_time")].to_value("Myr"))
    try_add('t_ave',        lambda: ave_time(d))              # needs AVERAGE_AGE
    try_add('t_dur',        lambda: duration(d))              # needs TERMINATION_TIME
    try_add('t_spread',     lambda: age_spread(d))            # needs AGE_SPREAD
    try_add('eps_int',      lambda: get_eps_int(d))           # needs INITIAL_BOUND_FRACTION
    try_add('x',            lambda: (d[('STAR', 'POSITION_X')] - center[0]).to_value('kpc'))
    try_add('y',            lambda: (d[('STAR', 'POSITION_Y')] - center[1]).to_value('kpc'))
    try_add('z',            lambda: (d[('STAR', 'POSITION_Z')] - center[2]).to_value('kpc'))
    try_add('pid',          lambda: d[('STAR', 'PID')].astype(np.int64))

    output_path = filename.replace('out/snap_', 'analysis/star_at_').replace('.art', '%s.hdf5' % suffix)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with h5py.File(output_path, 'w') as f:
        for name, arr in zip(col_names, col_arrays):
            f.create_dataset(name, data=arr)


def halo_evolution(mpb, filename_list_for_tree, basepath, suffix=''):
    # Load one snapshot just to get cosmological parameters
    snap = mpb['Snap_idx'][-1]
    filename = os.path.join(basepath, filename_list_for_tree[snap])
    ds = yt.load(filename)
    h = ds.hubble_constant

    cosmo = yt.utilities.cosmology.Cosmology(
        hubble_constant=h,
        omega_matter=ds.omega_matter,
        omega_lambda=ds.omega_lambda,
    )

    scale = mpb['scale']
    time  = np.array([cosmo.t_from_z(1.0/a - 1).to_value('Gyr') for a in scale])
    mvir  = mpb['Mvir'] / h                      # Msun/h  -> Msun
    rvir  = mpb['Rvir'] * scale / h              # kpccm/h -> kpc (physical)
    x     = mpb['x']                             # Mpccm/h
    y     = mpb['y']
    z     = mpb['z']

    output_path = os.path.join(basepath, 'analysis/halo_evolution%s.hdf5' % suffix)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with h5py.File(output_path, 'w') as f:
        f.create_dataset('scale', data=scale)
        f.create_dataset('time',  data=time)   # Gyr
        f.create_dataset('mvir',  data=mvir)   # Msun
        f.create_dataset('rvir',  data=rvir)   # kpc (physical)
        f.create_dataset('x',     data=x)      # Mpccm/h
        f.create_dataset('y',     data=y)
        f.create_dataset('z',     data=z)
    print("Saved: %s" % output_path)


def baryon_fraction_at_scalefactor(mpb, filename_list_for_tree, basepath, scalefactor=None):
    if scalefactor is None:
        idx = -1
    else:
        idx = np.argmin(np.abs(mpb['scale'] - scalefactor))
    snapshot = copy(mpb[idx])
    snap = snapshot['Snap_idx']
    filename = os.path.join(basepath, filename_list_for_tree[snap])

    ds = yt.load(filename)
    fb = 0.04897 / ds.omega_matter

    center = ds.arr([snapshot['x'], snapshot['y'], snapshot['z']], 'Mpccm/h')
    rvir = ds.arr(snapshot['Rvir'], 'kpccm/h')
    mhalo = snapshot['Mvir'] / ds.hubble_constant  # Msun/h -> Msun

    d = ds.sphere(center, rvir)
    mstar = d[('STAR', 'MASS')].to_value('Msun').sum()

    fbar = mstar / (mhalo * fb)
    parts = basepath.rstrip('/').split('/')
    name = f"{parts[-3]}/{parts[-2]}"
    print(f"{name}  Mstar = {mstar:.3e} Msun  Mhalo = {mhalo:.3e} Msun  fbar = {fbar:.4f}")


def gas_at_scalefactor(mpb, filename_list_for_tree, basepath, scalefactor=None, suffix=''):
    if scalefactor is None:
        idx = -1
    else:
        idx = np.argmin(np.abs(mpb['scale'] - scalefactor))
    snapshot = copy(mpb[idx])
    snap = snapshot['Snap_idx']
    filename = os.path.join(basepath, filename_list_for_tree[snap])

    ds = yt.load(filename)

    center = ds.arr([snapshot['x'], snapshot['y'], snapshot['z']], 'Mpccm/h')
    rvir = ds.arr(snapshot['Rvir'], 'kpccm/h')

    d = ds.sphere(center, rvir)

    density = d[('gas', 'density')].to_value('Msun/kpc**3')
    temperature = d[('gas', 'temperature')].to_value('K')
    metallicity = d[('gas', 'metallicity')].to_value('1')
    size = d[('gas', 'dx')].to_value('kpc')
    eturb = d[('artio', 'HVAR_GAS_TURBULENT_ENERGY')].to_value('1')
    eturb *= (ds.units.code_mass*ds.units.code_velocity**2/ds.units.code_length**3)
    eturb = eturb.to_value('Msun*(km/s)**2/kpc**3')
    ether = d[('artio', 'HVAR_INTERNAL_ENERGY')].to_value('Msun*(km/s)**2/kpc**3')
    x = (d[('gas', 'x')] - center[0]).to_value('kpc')
    y = (d[('gas', 'y')] - center[1]).to_value('kpc')
    z = (d[('gas', 'z')] - center[2]).to_value('kpc')

    output_path = filename.replace('out/snap_', 'analysis/gas_at_').replace('.art', '%s.hdf5' % suffix)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with h5py.File(output_path, 'w') as f:
        f.create_dataset('density',     data=density)
        f.create_dataset('temperature', data=temperature)
        f.create_dataset('metallicity', data=metallicity)
        f.create_dataset('size',        data=size)
        f.create_dataset('eturb',       data=eturb)
        f.create_dataset('ether',       data=ether)
        f.create_dataset('x',           data=x)
        f.create_dataset('y',           data=y)
        f.create_dataset('z',           data=z)

def skirt_interface_at_last_snapshot(mpb, filename_list_for_tree, basepath):
    lastsnapshot = copy(mpb[-1])
    lastsnap = lastsnapshot['Snap_idx']
    filename = os.path.join(basepath, filename_list_for_tree[lastsnap])

    ds = yt.load(filename)

    center = ds.arr([lastsnapshot['x'],lastsnapshot['y'],lastsnapshot['z']], 'Mpccm/h')
    rvir = ds.arr(lastsnapshot['Rvir'], 'kpccm/h')

    d = ds.sphere(center, rvir)

    output_path = filename.replace('out/snap_', 'analysis/skirt_at_').replace('.art', '')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    art2skirt(ds, d, center, output_path)

def process_folder(basepath, scalefactor=None, branch='mpb'):
    """Process a single simulation folder.

    branch: 'mpb' for the main progenitor branch, 'merger' for the most
            important secondary progenitor (highest historical peak mass).
    """
    try:
        treepath = os.path.join(basepath, 'rockstar_halos/trees/tree_0_0_0.dat')
        snap_list = np.loadtxt(
            os.path.join(basepath, 'rockstar_halos/datasets.txt'),
            dtype={'names': ('filename', 'snap_original'), 'formats': ('U20', int)}
        )

        tree = np.loadtxt(treepath, skiprows=49, dtype=dtype_tree)
        if branch == 'merger':
            mpb_main = find_major_merger_branch(tree)
            if mpb_main is None:
                print(f"No secondary branch found: {basepath}")
                return
        else:
            mpb_main = find_main_mpb(tree)

        # merger tree snap number can differ
        lastsnap_original = snap_list['snap_original'][-1]
        lastsnap_tree = mpb_main['Snap_idx'][-1]
        dsnap = int(lastsnap_original-lastsnap_tree)

        filename_list_for_tree = snap_list['filename'][dsnap:]

        suffix = '_merger' if branch == 'merger' else ''
        halo_evolution(mpb_main, filename_list_for_tree, basepath, suffix=suffix)
        # star_at_scalefactor(mpb_main, filename_list_for_tree, basepath, scalefactor=scalefactor, suffix=suffix)
        # gas_at_scalefactor(mpb_main, filename_list_for_tree, basepath, scalefactor=scalefactor, suffix=suffix)
        # baryon_fraction_at_scalefactor(mpb_main, filename_list_for_tree, basepath, scalefactor=scalefactor)
        # skirt_interface_at_last_snapshot(mpb_main, filename_list_for_tree, basepath)
        # make_prj_along_mpb(
        #     mpb_main, filename_list_for_tree, basepath, scalefactor=scalefactor, cmap='magma',
        #     field="density", field_unit="Msun/pc**3", weight="volume", vmin=1e-4, vmax=1e0
        # )
        # make_prj_along_mpb(
        #     mpb_main, filename_list_for_tree, basepath, scalefactor=scalefactor, cmap='coolwarm',
        #     field="temperature", field_unit="K", weight="mass", vmin=1e3, vmax=1e6
        # )
        # make_prj_along_mpb(
        #     mpb_main, filename_list_for_tree, basepath, scalefactor=scalefactor, cmap='coolwarm',
        #     field="metallicity", field_unit="1", weight="mass", vmin=1e-5, vmax=1e-2
        # )
        # make_prj_along_mpb(
        #     mpb_main, filename_list_for_tree, basepath, scalefactor=scalefactor, cmap='RdYlBu',
        #     field="M", field_unit="1", weight="mass", vmin=1e-2, vmax=1e2, scale='log',
        # )
        # make_prj_along_mpb(
        #     mpb_main, filename_list_for_tree, basepath, scalefactor=scalefactor, cmap='coolwarm',
        #     field="avir", field_unit="1", weight="mass", vmin=1e1, vmax=1e7, scale='log',
        # )

        print(f"Processed: {basepath}")
    except Exception as e:
        print(f"Error processing {basepath}: {e}")

def scan_subfolders(root_path, root_folder, scalefactor=None, branch='mpb'):
    """Scan and process all subfolders in a root folder."""
    folder_path = os.path.join(root_path, root_folder)
    for entry in sorted(os.listdir(folder_path)):
        subfolder_path = os.path.join(folder_path, entry)
        basepath = os.path.join(subfolder_path, "run")
        if os.path.isdir(basepath):
            process_folder(basepath, scalefactor=scalefactor, branch=branch)

def process_all_folders(root_path, root_folders, scalefactor=None, branch='mpb'):
    """Process all folders."""
    for root_folder in root_folders:
        print(f"Processing folder: {root_folder}")
        scan_subfolders(root_path, root_folder, scalefactor=scalefactor, branch=branch)

if __name__ == '__main__':

    root_path = "/scratch/08199/tg874988/art_simulations/hydro"
    root_folders = ["mh2e12_eps100", "mh2e12_eps10", "mh2e12_eps1", "mh2e12_km", "mh3e12_km", "mh5e12_km", "mh2e12_p12", "mh3e12_p12", "mh5e12_p12"]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'basepath', nargs='?', default=None,
        help='Path to a single simulation run folder (or .art file)'
    )
    parser.add_argument(
        '--scalefactor', '-a', type=float, default=None,
        help='Scale factor to analyse (default: last snapshot)'
    )
    parser.add_argument(
        '--branch', '-b', default='mpb', choices=['mpb', 'merger'],
        help='Branch to analyse: mpb (main progenitor) or merger (highest-peak-mass secondary)'
    )
    args = parser.parse_args()

    if args.basepath is not None:
        basepath = os.path.dirname(args.basepath) if args.basepath.endswith('.art') else args.basepath
        basepath = os.path.join(basepath, "run") if not basepath.endswith("run") else basepath
        process_folder(basepath, scalefactor=args.scalefactor, branch=args.branch)
    else:
        process_all_folders(root_path, root_folders, scalefactor=args.scalefactor, branch=args.branch)