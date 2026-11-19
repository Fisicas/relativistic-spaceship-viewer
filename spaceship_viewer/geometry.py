"""Equatorial directions and the inherited two-angular-axis windshield projection.

Vectors point FROM the observer TO a source. Coordinates are in degrees. No
precession, epoch propagation, translation, or proper motion is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


def finite_scalar(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    return value


def unit_vectors(value, name="vectors") -> np.ndarray:
    value = np.asarray(value, dtype=float)
    if value.ndim != 2 or value.shape[1] != 3 or not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must be a finite (N, 3) array.")
    if not np.allclose(np.linalg.norm(value, axis=1), 1., rtol=0., atol=2e-12):
        raise ValueError(f"{name} must contain unit vectors.")
    return value


def radec_to_unit(ra_deg, dec_deg) -> np.ndarray:
    ra, dec = np.broadcast_arrays(np.atleast_1d(np.asarray(ra_deg, dtype=float)),
                                   np.atleast_1d(np.asarray(dec_deg, dtype=float)))
    if ra.ndim != 1 or not np.all(np.isfinite(ra)) or not np.all(np.isfinite(dec)):
        raise ValueError("RA and Dec must be finite scalar or one-dimensional values.")
    if np.any(np.abs(dec) > 90.):
        raise ValueError("Declination must be in [-90, 90] degrees.")
    ra, dec = np.deg2rad(ra % 360.), np.deg2rad(dec)
    cd = np.cos(dec)
    return np.column_stack((cd * np.cos(ra), cd * np.sin(ra), np.sin(dec)))


def unit_to_radec(v) -> tuple[float, float]:
    v = unit_vectors(np.asarray(v, dtype=float).reshape(1, 3))[0]
    # At a pole RA defines a meridian convention, not a unique sky direction.
    return (math.degrees(math.atan2(v[1], v[0])) % 360.,
            math.degrees(math.atan2(v[2], math.hypot(v[0], v[1]))))


def basis_from_radec(ra_deg, dec_deg):
    ra_deg = finite_scalar(ra_deg, "RA")
    dec_deg = finite_scalar(dec_deg, "Dec")
    fwd = radec_to_unit(ra_deg, dec_deg)[0]
    ra = math.radians(ra_deg % 360.)
    east = np.array([-math.sin(ra), math.cos(ra), 0.])
    north = np.cross(fwd, east)
    return fwd, east, north / np.linalg.norm(north)


@dataclass(frozen=True)
class CameraPose:
    """Orthonormal camera triad in rest-frame-aligned spatial axes.

    Keep the whole triad while dragging: rebuilding from RA/Dec at every step
    would discard roll and cause a discontinuity on crossing a pole.
    """
    forward: tuple[float, float, float]
    east: tuple[float, float, float]
    north: tuple[float, float, float]

    def __post_init__(self):
        basis = unit_vectors([self.forward, self.east, self.north], "camera basis")
        if not np.allclose(basis @ basis.T, np.eye(3), atol=2e-12, rtol=0.):
            raise ValueError("Camera basis must be orthonormal.")
        if not np.allclose(np.cross(basis[0], basis[1]), basis[2], atol=2e-12, rtol=0.):
            raise ValueError("Camera basis must satisfy forward cross east = north.")
        for field, vector in zip(("forward", "east", "north"), basis):
            object.__setattr__(self, field, tuple(float(x) for x in vector))

    @classmethod
    def from_radec(cls, ra_deg, dec_deg):
        return cls(*basis_from_radec(ra_deg, dec_deg))

    @property
    def radec(self):
        return unit_to_radec(self.forward)

    def rotated(self, yaw_deg, pitch_deg):
        yaw = math.radians(finite_scalar(yaw_deg, "yaw"))
        pitch = math.radians(finite_scalar(pitch_deg, "pitch"))
        fwd, east, north = map(np.asarray, (self.forward, self.east, self.north))
        yaw_fwd = math.cos(yaw) * fwd + math.sin(yaw) * east
        new_east = math.cos(yaw) * east - math.sin(yaw) * fwd
        new_fwd = math.cos(pitch) * yaw_fwd + math.sin(pitch) * north
        new_fwd /= np.linalg.norm(new_fwd)
        new_east /= np.linalg.norm(new_east)
        new_north = np.cross(new_fwd, new_east)
        return CameraPose(new_fwd, new_east, new_north / np.linalg.norm(new_north))


def rotate_forward(fwd, east, north, yaw_deg, pitch_deg):
    """Compatibility helper; CameraPose.rotated also preserves orientation."""
    return np.asarray(CameraPose(fwd, east, north).rotated(yaw_deg, pitch_deg).forward)


def project_directions(vectors, camera: CameraPose, hfov_deg=45., vfov_deg=45.):
    """Return x degrees, y degrees, visibility; x positive is camera west.

    x=-atan2(s.east,s.forward), y=atan2(s.north,s.forward). These are
    independent angular axes, NOT a planar gnomonic or equal-area map.
    Rectangular limits apply to these axes; corners are farther from center
    than either half-FOV. Preserve input order, including invisible entries.
    """
    vectors = unit_vectors(vectors)
    hfov_deg, vfov_deg = (finite_scalar(hfov_deg, "horizontal FOV"),
                          finite_scalar(vfov_deg, "vertical FOV"))
    if not (0 < hfov_deg < 180 and 0 < vfov_deg < 180):
        raise ValueError("Each angular-axis FOV must be in (0, 180) degrees.")
    z = vectors @ camera.forward
    x = -np.rad2deg(np.arctan2(vectors @ camera.east, z))
    y = np.rad2deg(np.arctan2(vectors @ camera.north, z))
    visible = (z > 0) & (np.abs(x) <= hfov_deg / 2) & (np.abs(y) <= vfov_deg / 2)
    return x, y, visible
