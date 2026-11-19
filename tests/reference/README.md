# Original Orion reference scenes

The four `*_original.npz` files were generated from the original script at
Git commit `0f4d46a7451f71969c3d90b9225703e64b1a691b`, not from the refactored
scene code. `tools/capture_baseline.py` evaluates the original functions and
compares their numerical results to the new scene calculation. The original
source SHA-256 and execution environment are in `baseline_report.json`.

Each NPZ preserves candidate order, apparent vectors, Doppler factors, mu,
projection coordinates, visibility mask, display-magnitude proxy, marker areas,
and RGB. NumPy loads these with `allow_pickle=False`. The catalog and reference
settings are fixed: 33 inherited demo objects, rest V <= 8, heading/camera RA
84 deg and Dec -1 deg, 45 x 45 deg angular-axis view, both illustrative Doppler
display modes enabled. beta_0_87 and gamma_2 are separate cases.

The render metadata record old/new pixel comparisons performed in the same
Matplotlib/font environment, with original text restored in the new drawing.
These do not imply cross-platform pixel identity, calibrated photometry, or
accurate underlying catalog measurements. The original small JPEGs are not used
as numerical reference data.
