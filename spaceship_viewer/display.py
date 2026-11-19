"""Inherited illustrative display mapping, NOT calibrated radiometry.

Unknown B-V is replaced by 0.65 ONLY for display. Color index is clipped to
[-0.40, 2.20]. Temperature-to-RGB uses the inherited empirical approximation
clipped to 1000--40000 K. Marker area is a clipped visual encoding in pt^2.
The optional D^3 multiplier is a teaching convention, not a Johnson-V flux
prediction, detector model, or statement that every flux scales as D^3.
"""
import numpy as np


def bv_to_temperature(bv):
    bv = np.nan_to_num(np.asarray(bv, dtype=float), nan=0.65, posinf=0.65, neginf=0.65)
    bv = np.clip(bv, -0.40, 2.20)
    return 4600.0 * (1.0 / (0.92 * bv + 1.7) + 1.0 / (0.92 * bv + 0.62))


def temperature_to_rgb(temp_k):
    t = np.atleast_1d(np.asarray(temp_k, dtype=float))
    t = np.clip(np.nan_to_num(t, nan=5800.0, posinf=40000.0, neginf=1000.0), 1000.0, 40000.0) / 100.0
    r = np.empty_like(t); g = np.empty_like(t); b = np.empty_like(t)
    low = t <= 66.0; high = ~low
    r[low] = 255.0
    g[low] = 99.4708025861 * np.log(np.maximum(t[low], 1.0)) - 161.1195681661
    b[low] = np.where(t[low] <= 19.0, 0.0,
                      138.5177312231 * np.log(np.maximum(t[low] - 10.0, 1.0)) - 305.0447927307)
    r[high] = 329.698727446 * np.power(t[high] - 60.0, -0.1332047592)
    g[high] = 288.1221695283 * np.power(t[high] - 60.0, -0.0755148492)
    b[high] = 255.0
    return np.clip(np.column_stack((r, g, b)) / 255.0, 0.0, 1.0)


def display_mag(vmag: np.ndarray, doppler: np.ndarray, enabled: bool) -> np.ndarray:
    if not enabled:
        return vmag.copy()
    return vmag - 2.5 * 3.0 * np.log10(np.maximum(doppler, 1e-9))


def marker_sizes(mag_eff: np.ndarray) -> np.ndarray:
    sizes = 28.0 * 10.0 ** (-0.4 * (mag_eff - 1.0))
    return np.clip(sizes, 0.35, 260.0)
