"""
This file is adopted from Gillen Brown
"""

import yt
import numpy as np

def time_units(ds, array):
    return ds._handle.tphys_from_tcode_array(array) * yt.units.year


def duration(region):
    end_time = time_units(region.ds, region[("STAR", "TERMINATION_TIME")])
    return end_time - region[("STAR", "creation_time")]


def ave_time(region):
    art_units_ave_age = region[("STAR", "AVERAGE_AGE")]
    art_units_birth = region[("STAR", "BIRTH_TIME")]

    ave_time = time_units(region.ds, art_units_birth + art_units_ave_age)
    return ave_time - region[("STAR", "creation_time")]


def age_spread(region):
    initial_mass = region[("STAR", "initial_mass")]
    age_spread = region[("STAR", "AGE_SPREAD")] * region.ds.arr(1, "code_mass**2")
    birth_time = region[("STAR", "BIRTH_TIME")]
    creation_time = region[("STAR", "creation_time")]

    # some clusters have bad values, for whatever reason. Set a placeholder
    # value for the vectorized calculation, then replace them with nans later.
    # Negative age spreads or values very close to zero break the age calculation
    bad_idxs = np.where(age_spread.value <= 1e-20)
    age_spread[bad_idxs] = max(age_spread)

    time = time_units(region.ds, (initial_mass ** 2 / age_spread) + birth_time)

    time[bad_idxs] = np.nan

    return time - creation_time