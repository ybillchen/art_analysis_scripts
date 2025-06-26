"""
BSD 3-Clause License
Copyright (c) 2024-2025 Yingtian Chen
All rights reserved.
"""

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
    if len(halos) == 0:
        return []
    centers = ds.arr(halos[:,8:11], 'Mpccm/h')
    rvirs = ds.arr(halos[:,5], 'kpccm/h')

    cutouts = []
    for i in range(len(halos)):
        center = centers[i]
        rvir = rvirs[i]
        cutouts.append(ds.sphere(center, rvir))
    return cutouts

def analyse(simpath, halocatpath, savebase, all_data=False):

    ds = yt.load(simpath)
    halocat = np.loadtxt(halocatpath)

    if all_data:
        cutouts = [ds.all_data()]
    else:
        cutouts = get_cutouts(ds, halocat)

    for i, d in enumerate(cutouts):

        initial_mass = d[('STAR', 'initial_mass')].to_value('Msun')
        f_bound0 = get_fbound0(d)
        t_form = d[("STAR", "creation_time")].to_value("Myr")
        t_ave = ave_time(d)
        out = np.column_stack([initial_mass, f_bound0, t_form, t_ave])

        savename = '/home1/08199/tg874988/sfh_cimf/%s_z6.5_halo%d.txt'%(savebase,i)
        if all_data:
            savename = savename.replace('halo%d'%i, 'all_data')
        np.savetxt(savename, out)

if __name__ == '__main__':

    simgroup = 'mh2e12_km'
    simname = '1117028'
    simeff = simgroup.split('_')[-1]
    savebase = simname + '_' + simeff

    halocatpath = '/scratch/08199/tg874988/art_simulations/hydro/%s/%s/run/rockstar_halos_at_z/out_0.list'%(simgroup,simname)

    # simgroup = 'test_epsff'
    # simname = 'R20_dx1.5_KM'
    # simeff = 'km'
    # savebase = '1117028_km_old'
    
    simpath = '/scratch/08199/tg874988/art_simulations/hydro/%s/%s/run/out/snap_a0.1335.art'%(simgroup,simname)

    args = sys.argv[1:]

    if len(args) > 2:
        raise ValueError("Too many arguments")

    if len(args) > 0:
        simpath = args[0]
    if len(args) > 1:
        halocatpath = args[1]

    analyse(simpath, halocatpath, savebase, True)
