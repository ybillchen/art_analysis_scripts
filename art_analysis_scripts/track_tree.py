"""
BSD 3-Clause License
Copyright (c) 2025-2025 Yingtian Chen
All rights reserved.
"""


import os
import sys
sys.path.append('.')

import yt
import numpy as np

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
    mainrootid = tree_lastsnap[arg_main,29]
    mpb_main = tree[tree[:,29]==mainrootid]

    return mpb_main[mpb_main[:,31].argsort()] # sort by snap number

def make_prj_along_mpb(mpb, filename_list_for_tree):
    for idx in range(len(mpb)):
        snapshot = mpb[idx]
        currentsnap = snapshot[31]
        filename = filename_list_for_tree[currentsnap]
        print(currentsnap, snapshot[0], snapshot[17:20], filename)

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
        dtype={'names': ('filename', 'snap_original'), 'formats': (str, int)}
    )

    tree = np.loadtxt(treepath, skiprows=49)
    mpb_main = find_main_mpb(tree)

    # merger tree snap number can differ
    lastsnap_original = snap_list['snap_original'][-1]
    lastsnap_tree = mpb_main[-1,31]
    dsnap = int(lastsnap_original-lastsnap_tree)

    filename_list_for_tree = snap_list['filename'][dsnap:]

    make_prj_along_mpb(mpb_main, filename_list_for_tree)