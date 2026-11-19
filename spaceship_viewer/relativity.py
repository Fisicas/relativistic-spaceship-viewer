"""Lorentz transformation of source directions for one instantaneous observer.

    s: observer-to-source unit vector (photon propagates along -s)
    h: unit vector of observer velocity in the catalog rest frame
    mu = s.h; D = nu_ship/nu_rest = gamma*(1 + beta*mu)

The boost uses axes related by a standard rotation-free Lorentz boost. Camera
orientation is a separate spatial rotation in those aligned axes. Negative beta
is accepted for inverse checks; the application uses nonnegative speed.
"""
from __future__ import annotations
import math
import numpy as np
from .geometry import finite_scalar, unit_vectors

MAX_BETA = 0.999999  # explicit tested numerical domain, inherited upper core limit


def validate_beta(beta):
    beta = finite_scalar(beta, "beta")
    if abs(beta) > MAX_BETA:
        raise ValueError(f"This core supports |beta| <= {MAX_BETA}; no silent clipping.")
    return beta


def lorentz_factor(beta):
    beta = validate_beta(beta)
    return 1. / math.sqrt((1. - beta) * (1. + beta))


def aberrate(vectors, forward, beta):
    """Return apparent source vectors, Doppler factors, and rest-frame mu.

    No catalog cuts or radiometry here. Dot products are clipped to [-1,1]
    only for unit-vector floating-point roundoff; directions are renormalized
    after the boost to remove accumulated floating-point norm error.
    """
    beta = validate_beta(beta)
    vectors = unit_vectors(vectors)
    forward = unit_vectors(np.asarray(forward).reshape(1, 3), "velocity direction")[0]
    gamma = lorentz_factor(beta)
    mu = np.clip(vectors @ forward, -1., 1.)
    denom = 1. + beta * mu
    parallel_prime = ((mu + beta) / denom)[:, None] * forward
    perpendicular = vectors - mu[:, None] * forward
    apparent = parallel_prime + perpendicular / (gamma * denom)[:, None]
    apparent /= np.linalg.norm(apparent, axis=1)[:, None]
    return apparent, gamma * denom, mu


def rest_frame_half_angle(ship_half_angle_deg, beta):
    """Inverse circular-cone half-angle, applicable to a velocity-centered view.

    This describes a central axial slice, not the full rectangular windshield.
    """
    angle = finite_scalar(ship_half_angle_deg, "ship half-angle")
    beta = validate_beta(beta)
    if not 0 <= angle <= 180:
        raise ValueError("Half-angle must be in [0, 180] degrees.")
    mu_prime = math.cos(math.radians(angle))
    mu = (mu_prime - beta) / (1. - beta * mu_prime)
    return math.degrees(math.acos(float(np.clip(mu, -1., 1.))))
