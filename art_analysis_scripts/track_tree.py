"""
BSD 3-Clause License
Copyright (c) 2025-2025 Yingtian Chen
All rights reserved.
"""


import os
import sys
sys.path.append('.')

import numpy as np
import matplotlib
matplotlib.use("agg")
from matplotlib.colors import LogNorm
import matplotlib.pyplot as plt
import yt

from prj import prj
from age_spreads import *
from utils import *

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

def find_main_mpb(tree):
    '''
    find the main halo
    '''
    snap = tree[:,31].astype(int)
    lastsnap = np.max(snap)
    tree_lastsnap = tree[snap==lastsnap]
    mvir_lastsnap = tree_lastsnap[:,10]

    arg_main = np.argmax(mvir_lastsnap) # main halo is the most massive
    mainleafid = int(tree_lastsnap[arg_main,34])
    mpb_main = tree[tree[:,34].astype(int)==mainleafid]

    return mpb_main[mpb_main[:,31].argsort()] # sort by snap number

def make_prj_single(snapshot, filename, basepath):

    ds = yt.load(filename)
    center = (snapshot[17:20]*ds.units.Mpccm/ds.units.h).to_value('code_length')

    d = ds.all_data()

    x0 = center[0]
    y0 = center[1]
    z0 = center[2]
    size = (10.0*ds.units.kpc).to_value('code_length')

    level = 9
    factor = 0.6

    unit = 'kpc'
    unit_convert = (1.0*ds.units.code_length).to_value(unit)

    ruler = 1.0 # in kpc
    ruler_convert = (ruler*ds.units.kpc).to_value(unit)

    fig, ax0 = plt.subplots(1, 1, figsize=(3,3))
    axs = [ax0]
    # fig, axs = plt.subplots(1, 2, figsize=(6,3))

    prjs = ["x", "y", "z"]
    centers = [x0, y0, z0]

    for ax0, idx_x, idx_y in zip(axs, [0, 0], [1, 2]):

        # gas
        mesh, region = prj(ds, [x0, y0, z0], 
            size, level=level, prj_x=prjs[idx_x], prj_y=prjs[idx_y], 
            field="density", unit="Msun/pc**3", factor=factor)
        ax0.imshow(
            mesh.T, origin="lower", norm=LogNorm(vmin=1e-6, vmax=1e-2),
            extent=[region[idx_x].to_value(unit), region[idx_x+3].to_value(unit),
                region[idx_y].to_value(unit), region[idx_y+3].to_value(unit)])

        # stars
        d = ds.box(region[:3], region[3:])
        ax0.scatter(
            d["STAR", "POSITION_%s"%prjs[idx_x].upper()].to_value(unit),
            d["STAR", "POSITION_%s"%prjs[idx_y].upper()].to_value(unit), 
            fc='w', ec='none', s=d["STAR", "MASS"].to_value("Msun")/5e5, alpha=0.7)

        # ruler
        ax0.plot(
            [
                (centers[idx_x]+0.45*size)*unit_convert-ruler_convert, 
                (centers[idx_x]+0.45*size)*unit_convert
            ], [
                (centers[idx_y]-0.45*size)*unit_convert, 
                (centers[idx_y]-0.45*size)*unit_convert
            ], lw=1.5, c="w")
        ax0.text(
            (centers[idx_x]+0.45*size)*unit_convert-0.5*ruler_convert, 
            (centers[idx_y]-0.44*size)*unit_convert, 
            r"%d kpc"%ruler, ha="center", va="bottom", color="w")

        ax0.set_xlabel(r"%s (%s)"%(prjs[idx_x], unit))
        ax0.set_ylabel(r"%s (%s)"%(prjs[idx_y], unit))
        ax0.set_axis_off()
        ax0.set_aspect("equal")
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

    plt.tight_layout()
    plt.savefig(
        filename.replace('out/snap_', 'analysis/prj_').replace('.art', '.png'), 
        bbox_inches ="tight", pad_inches=0.05, dpi=300
    )
    plt.close()

    print('Done a = %.4f'%a)

def make_prj_along_mpb(mpb, filename_list_for_tree, basepath):
    for idx in range(len(mpb)):
        snapshot = mpb[idx]
        currentsnap = int(snapshot[31])
        filename = os.path.join(basepath, filename_list_for_tree[currentsnap])
        print(idx, currentsnap, snapshot[0], snapshot[17:20], filename)
        if idx == len(mpb) - 1:
            make_prj_single(snapshot, filename, basepath)

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

    tree = np.loadtxt(treepath, skiprows=49)
    mpb_main = find_main_mpb(tree)

    # merger tree snap number can differ
    lastsnap_original = snap_list['snap_original'][-1]
    lastsnap_tree = mpb_main[-1,31]
    dsnap = int(lastsnap_original-lastsnap_tree)

    filename_list_for_tree = snap_list['filename'][dsnap:]

    make_prj_along_mpb(mpb_main, filename_list_for_tree, basepath)