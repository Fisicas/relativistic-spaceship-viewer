"""Camera-only object targeting and angular-axis widescreen field of view."""
from dataclasses import replace
import numpy as np
from .geometry import CameraPose, finite_scalar, unit_to_radec
from .relativity import aberrate

WIDESCREEN_RATIO = 16. / 9.
MIN_FOV = .001


def center_object(catalog, state, row):
    """Center the moving observer's apparent direction, preserving the boost.

    Camera lock is released explicitly: panning a locked camera would steer the
    velocity and change every source's Doppler factor instead of just looking.
    The rest-frame magnitude cut is retained, even for an excluded target.
    """
    if type(row) is not int or not 0 <= row < catalog.n:
        raise ValueError('Object index is outside the catalog.')
    apparent, _, _ = aberrate(catalog.vectors[row:row+1], state.velocity_direction, state.beta)
    ra, dec = unit_to_radec(apparent[0])
    return replace(state, camera_locked=False, camera=CameraPose.from_radec(ra, dec))


def widescreen_fov(vertical_deg):
    """Equal degrees per pixel in the existing independent angular-axis map.

    This is not a gnomonic pinhole projection, so the ratio is H/V, not the
    ratio of tangent half-angles. Limit H to the UI's 160-degree maximum.
    """
    vertical = float(np.clip(finite_scalar(vertical_deg, 'vertical FOV'), MIN_FOV, 160./WIDESCREEN_RATIO))
    return vertical * WIDESCREEN_RATIO, vertical
