"""
BSD 3-Clause License
Copyright (c) 2025-2025 Yingtian Chen
All rights reserved.
"""


import os
import sys
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

def save_mpb(mpb):
    np.savetxt(mpb, fmt=fmt_tree)

def make_prj_single(snapshot, filename, basepath):

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

    fig, ax0 = plt.subplots(1, 1, figsize=(3,3))
    ax0.set_position([0.0, 0.0, 1.0, 1.0])
    axs = [ax0]
    # fig, axs = plt.subplots(1, 2, figsize=(6,3))

    prjs = ["x", "y", "z"]
    centers = [x0, y0, z0]

    for ax0, idx_x, idx_y in zip(axs, [2, 0], [1, 1]):

        # gas
        mesh, region = prj(ds, [x0, y0, z0], 
            size, level=level, prj_x=prjs[idx_x], prj_y=prjs[idx_y], 
            field="density", unit="Msun/pc**3", factor=factor
        )
        ax0.imshow(
            # mesh.T, origin="lower", norm=LogNorm(vmin=1e-5, vmax=1e-1), # default
            mesh.T, origin="lower", norm=LogNorm(vmin=1e-4, vmax=1e0),
            cmap='magma',
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
    plt.savefig(
        filename.replace('out/snap_', 'analysis/prj_zy_10kpc_').replace('.art', '.png'), 
        pad_inches=0.0, dpi=300
    )
    plt.close()

def make_prj_along_mpb(mpb, filename_list_for_tree, basepath):
    a_mpb = mpb['scale']
    da = 0.0025
    x_smooth = smooth_time_series(a_mpb, mpb['x'], da)
    y_smooth = smooth_time_series(a_mpb, mpb['y'], da)
    z_smooth = smooth_time_series(a_mpb, mpb['z'], da)
    for idx in range(len(mpb)):
        snapshot = copy(mpb[idx])
        currentsnap = snapshot['Snap_idx']
        filename = os.path.join(basepath, filename_list_for_tree[currentsnap])
        snapshot['x'] = x_smooth[idx]
        snapshot['y'] = y_smooth[idx]
        snapshot['z'] = z_smooth[idx]
        print(idx, currentsnap, snapshot['scale'], filename)
        # if idx % 100 == 0:
        # if idx == len(mpb) - 1:
        make_prj_single(snapshot, filename, basepath)

def star_at_last_snapshot(mpb, filename_list_for_tree, basepath):
    lastsnapshot = copy(mpb[-1])
    lastsnap = lastsnapshot['Snap_idx']
    filename = os.path.join(basepath, filename_list_for_tree[lastsnap])

    ds = yt.load(filename)

    center = ds.arr([lastsnapshot['x'],lastsnapshot['y'],lastsnapshot['z']], 'Mpccm/h')
    rvir = ds.arr(lastsnapshot['Rvir'], 'kpccm/h')

    d = ds.sphere(center, rvir)

    initial_mass = d[('STAR', 'initial_mass')].to_value('Msun')
    f_bound0 = get_fbound0(d)
    t_form = d[("STAR", "creation_time")].to_value("Myr")
    t_ave = ave_time(d)
    t_dur = duration(d)
    t_spread = age_spread(d)
    eps_int = get_eps_int(d)
    out = np.column_stack([initial_mass, f_bound0, t_form, t_ave, t_dur, t_spread, eps_int])

    savename = filename.replace('out/snap_', 'analysis/star_at_').replace('.art', '.txt')
    np.savetxt(savename, out)

def skirt_interface_at_last_snapshot(mpb, filename_list_for_tree, basepath):
    lastsnapshot = copy(mpb[-1])
    lastsnap = lastsnapshot['Snap_idx']
    filename = os.path.join(basepath, filename_list_for_tree[lastsnap])

    ds = yt.load(filename)

    center = ds.arr([lastsnapshot['x'],lastsnapshot['y'],lastsnapshot['z']], 'Mpccm/h')
    rvir = ds.arr(lastsnapshot['Rvir'], 'kpccm/h')

    d = ds.sphere(center, rvir)

    savenamebase = filename.replace('out/snap_', 'analysis/skirt_at_').replace('.art', '')
    art2skirt(ds, d, center, savenamebase)

if __name__ == '__main__':

    simgroup = 'mh5e12_km'
    simname = '1112809'
    simeff = simgroup.split('_')[-1]
    savebase = simname + '_' + simeff

    basepath = '/scratch/08199/tg874988/art_simulations/hydro/%s/%s/run/'%(simgroup,simname)

    args = sys.argv[1:]

    if len(args) > 0:
        basepath = os.path(args[0])
    if len(args) > 1:
        raise ValueError('Too many arguments')

    treepath = os.path.join(basepath, 'rockstar_halos/trees/tree_0_0_0.dat')
    snap_list = np.loadtxt(
        os.path.join(basepath, 'rockstar_halos/datasets.txt'),
        dtype={'names': ('filename', 'snap_original'), 'formats': ('U20', int)}
    )

    tree = np.loadtxt(treepath, skiprows=49, dtype=dtype_tree)
    mpb_main = find_main_mpb(tree)

    # merger tree snap number can differ
    lastsnap_original = snap_list['snap_original'][-1]
    lastsnap_tree = mpb_main['Snap_idx'][-1]
    dsnap = int(lastsnap_original-lastsnap_tree)

    filename_list_for_tree = snap_list['filename'][dsnap:]

    star_at_last_snapshot(mpb_main, filename_list_for_tree, basepath)
    # skirt_interface_at_last_snapshot(mpb_main, filename_list_for_tree, basepath)

    # make_prj_along_mpb(mpb_main, filename_list_for_tree, basepath)