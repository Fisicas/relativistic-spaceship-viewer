"""Object inspection uses the same source-direction convention as the scene."""
import math
import numpy as np
from .display import display_mag
from .geometry import unit_to_radec
from .relativity import aberrate


def inspect_object(catalog, state, row, wavelength_nm=550.):
    if type(row) is not int or not 0 <= row < catalog.n:
        raise ValueError('Object index is outside the catalog.')
    if not math.isfinite(wavelength_nm) or wavelength_nm <= 0:
        raise ValueError('Reference wavelength must be positive nanometers.')
    vector = catalog.vectors[row:row+1]
    apparent, d, mu = aberrate(vector, state.velocity_direction, state.beta)
    ra, dec = unit_to_radec(apparent[0])
    apparent_mu = float(apparent[0] @ state.velocity_direction)
    optional = lambda x: float(x) if np.isfinite(x) else None
    return {'row': row, 'name': str(catalog.name[row]), 'kind': str(catalog.object_kind[row]),
            'rest_ra_deg': float(catalog.ra_deg[row]), 'rest_dec_deg': float(catalog.dec_deg[row]),
            'apparent_ra_deg': ra, 'apparent_dec_deg': dec,
            'rest_heading_angle_deg': math.degrees(math.acos(float(np.clip(mu[0], -1, 1)))),
            'apparent_heading_angle_deg': math.degrees(math.acos(float(np.clip(apparent_mu, -1, 1)))),
            'doppler_factor': float(d[0]), 'reference_wavelength_nm': wavelength_nm,
            'shifted_wavelength_nm': wavelength_nm / float(d[0]),
            'rest_vmag': float(catalog.vmag[row]),
            'display_magnitude_proxy': float(display_mag(catalog.vmag[row:row+1], d, state.illustrative_brightness)[0]),
            'bv': optional(catalog.bv[row]), 'distance_pc': optional(catalog.distance_pc[row])}
