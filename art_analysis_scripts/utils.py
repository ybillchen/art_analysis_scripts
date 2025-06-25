"""
BSD 3-Clause License
Copyright (c) 2024 Yingtian Chen
All rights reserved.
"""

import numpy as np
from scipy import special

import yt

def f_bound(eps_int):
    # Li et al 2019: https://ui.adsabs.harvard.edu/abs/2019MNRAS.487..364L/abstract
    # equation 17
    alpha_star = 0.48
    f_sat = 0.94
    term_a = special.erf(np.sqrt(3 * eps_int / alpha_star))
    term_b = np.sqrt(12 * eps_int / (np.pi * alpha_star))
    term_c = np.exp(-3 * eps_int / alpha_star)
    return (term_a - (term_b * term_c)) * f_sat

def get_eps_int(region):
    star_initial_mass = region[("STAR", "INITIAL_MASS")].to_value("Msun")
    # the variable named INITIAL_BOUND_FRACTION is not the initial_bound fraction,
    # it's actually the accumulated mass nearby through the course of accretion, in
    # code masses. This is used to calculate the formation efficiency, which is then
    # used to get the bound fraction.
    star_accumulated_mass = region[("STAR", "INITIAL_BOUND_FRACTION")].to_value("1")
    star_accumulated_mass *= region.ds.mass_unit
    star_accumulated_mass = star_accumulated_mass.to_value("Msun")
    eps_int = star_initial_mass / star_accumulated_mass
    return eps_int

def get_fbound0(region):
    return f_bound(get_eps_int(region))

def select_sf_cells(region):
    ds = region.ds
    nh = region[('gas', 'H_density')] / ds.units.proton_mass
    return nh > (1e3 * ds.units.cm**-3)

def get_avir(region):
    ds = region.ds
    density_unit = ds.mass_unit / ds.length_unit**3
    energy_unit = ds.mass_unit * ds.velocity_unit**2
    energy_density_unit = energy_unit / ds.length_unit**3
    avir_factor = 10/np.pi/ds.units.gravitational_constant
    gamma = region[('artio', 'HVAR_GAMMA')]
    eturb = region[('artio', 'HVAR_GAS_TURBULENT_ENERGY')] * energy_density_unit
    ether = region[('artio', 'HVAR_INTERNAL_ENERGY')]
    dens = region[('gas', 'density')]
    cellsize = region[('gas', 'dx')]
    return avir_factor*(eturb+0.5*gamma*(gamma-1.0)*ether) / dens**2 / cellsize**2

def get_M2(region):
    ds = region.ds
    density_unit = ds.mass_unit / ds.length_unit**3
    energy_unit = ds.mass_unit * ds.velocity_unit**2
    energy_density_unit = energy_unit / ds.length_unit**3
    gamma = region[('artio', 'HVAR_GAMMA')]
    eturb = region[('artio', 'HVAR_GAS_TURBULENT_ENERGY')] * energy_density_unit
    ether = region[('artio', 'HVAR_INTERNAL_ENERGY')]
    return 2./(gamma*(gamma-1.0))*eturb/ether

def get_eps_ff_km(region, norm=0.46, phi_x=0.17):
    b = 0.4
    beta_inv = 0
    gamma = 5/3
    C = np.pi**2*phi_x**2 / 5.
    M2 = get_M2(region)
    avir = get_avir(region)
    sigma2 = np.log( 1+b**2*M2/(1+beta_inv) )
    s_crit = np.log( C*avir*(M2+1) )
    return 0.5*norm*(1+special.erf((sigma2-s_crit)/np.sqrt(2*sigma2)))*np.exp(3./8.*sigma2)

def get_eps_ff_p12(region, norm=0.9, slope=1.6):
    avir = get_avir(region)
    return norm*np.exp(-slope*np.sqrt(avir/1.35))

def get_sfr(region, eps_ff):
    ds = region.ds
    dens = region[('gas', 'density')]
    cellsize = region[('gas', 'dx')]
    t_ff = np.sqrt(3.*np.pi/(32.*ds.units.gravitational_constant*dens))
    return eps_ff*dens*cellsize**3/t_ff

if __name__ == '__main__':
    
    a = 0.1135
    ds = yt.load('/scratch/08199/tg874988/art_simulations/hydro/test_epsff/R20_dx1.5_KM_peakonly/run/out/snap_a%.4f.art'%a)
    d = ds.all_data()
    epsff = get_eps_ff_km(d)
    nh = (d[('gas', 'H_density')] / ds.units.proton_mass).to('cm**-3').value
    avir = get_avir(d)
    M2 = get_M2(d)
    sfr = get_sfr(d, epsff).to('Msun/Myr').value
    mask = select_sf_cells(d)
    out = np.column_stack([nh[mask], avir[mask], M2[mask], epsff[mask], sfr[mask]])
    np.savetxt('/home1/08199/tg874988/eff_km_peakonly_%d.txt'%(10000*a), out)

    a = 0.1108
    Rgmc = 10
    suffix = 'KM'
    ds = yt.load('/scratch/08199/tg874988/art_simulations/hydro/test_epsff/R%g_dx1.5_%s/run/out/snap_a%.4f.art'%(Rgmc,suffix,a))
    d = ds.all_data()
    initial_mass = d[('STAR', 'initial_mass')].to('Msun').value
    f_bound0 = get_fbound0(d)
    t_spread = age_spread(d)
    t_dur = duration(d)
    out = np.column_stack([initial_mass, t_spread, f_bound0, t_dur])
    np.savetxt('/home1/08199/tg874988/star_R%g_%s_%d.txt'%(Rgmc, suffix,10000*a), out)
