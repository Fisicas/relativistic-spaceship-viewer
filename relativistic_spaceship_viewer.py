"""Compatibility launch command and numerical API for existing users.

Run this file, or use ``python -m spaceship_viewer``. Importing numerical
helpers here does not initialize Tk, select a Matplotlib backend, or open a GUI.
"""
from spaceship_viewer import __version__ as APP_VERSION
from spaceship_viewer.catalog import StarCatalog, load_csv, fetch_hipparcos
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.geometry import radec_to_unit, unit_to_radec, basis_from_radec, rotate_forward
from spaceship_viewer.relativity import aberrate
from spaceship_viewer.display import bv_to_temperature, temperature_to_rgb, display_mag, marker_sizes

APP_NAME = "Relativistic Spaceship Viewer"
HFOV_DEG = VFOV_DEG = 45.
ORION_RA_DEG, ORION_DEC_DEG = 84., -1.
EPS = 1e-12  # retained for compatibility; numerical core no longer clips denominators


def __getattr__(name):
    if name == "Viewer":
        from spaceship_viewer.qt_app import Viewer
        return Viewer
    raise AttributeError(name)


def main():
    import sys
    if '--legacy-tk' in sys.argv:
        from spaceship_viewer.app import main as run
    else:
        from spaceship_viewer.entry import main as run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
