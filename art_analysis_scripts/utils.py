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