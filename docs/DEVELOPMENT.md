# Development and reproduction

Version **0.2.5** is an unpublished local release candidate with the physics
foundation, Qt UI, scientific exports, and Windows installation/update support.
Use the completion report for the actual checks and final asset hashes. The
version string alone does not indicate a Git tag or published release.

## Modules

The validated `geometry`, `relativity`, `state`, `catalog`, `demo_catalog`,
`display`, and `scene` modules remain independent of GUI initialization.
`qt_app.py` is the current interface. `app.py` preserves the Tk interface.
`rendering.py` preserves the original drawing for baseline checks; `plotting.py`
is the new shared Qt/export presentation. `presentation.py` records presentation
settings; `inspection.py` calculates object readouts; `session.py` handles portable
JSON scenes; `exporting.py` creates versioned figure bundles.
`solar.py` owns the fixed-1-AU finite geometry. `solar_radiometry.py` independently
integrates per-ray Planck spectra with bundled CIE data and maps them to display
RGB. Geometry never depends on exposure. See [radiometry](SOLAR_RADIOMETRY.md).
`entry.py` is shared by source, wheel, and frozen entry points; `runtime_check.py`
performs the short offline activation check. `deployment.py` uses only the
standard library for stable-release discovery, archive integrity, version slots,
running locks, activation, and rollback. `packaging/windows_helper.py` builds the
small stable launcher and installer. Neither helper imports the scientific GUI.

`relativistic_spaceship_viewer.py`, `python -m spaceship_viewer`, and the package
entry point launch Qt. The legacy script's `--legacy-tk` option runs Tk.
Importing the core or compatibility module does not initialize either GUI or
Matplotlib. No module named `pyplot` is needed by the application.

`theme.py` owns neutral chrome colors. `branding.py` and `assets/viewer_mark.svg`
share the selected icon; `tools/generate_branding.py` creates inspectable SVG/PNG
social artwork from actual core coordinates. `catalog_cache.py` stores bounded,
checksummed, versioned processed Hipparcos snapshots and startup preferences.

## Windows verification

From the checkout root:

```powershell
$sciencePython = 'C:\Users\nelso\.venvs\codex-science-v1\Scripts\python.exe'
& $sciencePython -X utf8 -m unittest discover -s tests -v
& $sciencePython -X utf8 .\tools\smoke_qt.py --output .\work\qt_check_v01.json
& $sciencePython -X utf8 .\tools\smoke_gui.py --output .\work\legacy_tk_check_v01.json
& $sciencePython -X utf8 .\tools\capture_baseline.py --output-dir .\work\baseline_v02 --render
```

Choose new output names. Smoke tests simulate dialogs and network outcomes;
they do not contact VizieR. The Tk check requires a Windows graphical session;
Qt smoke checks use the offscreen QPA plugin. Offscreen Windows screenshots
explicitly register installed fonts because that plugin does not populate the
native Windows font database. Normal desktop windows use native Qt font discovery.

The tested runtime is Python 3.12.10, NumPy 2.5.3, Matplotlib 3.11.2,
PySide6 6.11.2, Pillow 12.3.0, Tk 8.6, Windows 11. Do not upgrade the shared
environment to install this project. On other machines use a separate project
environment and resolve the declared dependencies there. Only this runtime was
verified; minimum dependency bounds are not a cross-version test claim.
The Matplotlib floor is 3.8 because horizon textures use ContourSet path access.
No installed shared-environment dependency was upgraded for this change.

Numerical baseline comparisons use absolute/relative tolerance 2e-12. Inverse
tests at |beta|=0.999999 allow 3e-9 absolute error because of conditioning. The
original reference arrays and metadata remain in `tests/reference/`. Original
pixel equality applies to the legacy renderer in the recorded environment;
the Qt presentation intentionally has different typography and label layout.

## Generate and verify figures

```powershell
& $sciencePython -X utf8 .\tools\generate_examples.py --output-dir .\work\examples_v03
& $sciencePython -X utf8 .\tools\verify_export.py .\work\examples_v03\orion_comparison_v01\scene.json `
    --rerender-parent .\work\reproduction_v01
```

Individual examples are 3840 x 3840; comparison is 3840 x 2160. The optional
`--write-docs` flag creates `docs/images/v02` and refuses an existing directory.
The installed project retains original 260-pixel JPEGs and uses the new PNGs in
the README. SVG contains editable text; PDF embeds TrueType fonts. Neither is
expected to have identical file bytes across regeneration because document
timestamps differ. PNG pixels can match within the same renderer/font/runtime;
scientific array reproduction is checked separately.

`tools/capture_qt_examples.py` renders controlled widget screenshots and measures
a reproducible synthetic 10,000-object catalog (seed 2030). It labels those data
as synthetic; the fixture is not observational validation. Performance is a
host-specific measurement, not a general frame-rate guarantee. Full Matplotlib
refreshes can still be noticeable in dense comparison views.

## Catalog import

Preferred headers: `name,ra_deg,dec_deg,vmag,bv,distance_pc`.
Use `ra_hours` for explicit hours. Generic `ra`/`raj2000` require `ra_unit`:
`deg` or `hour`. Generic `dist`/`distance` require `distance_unit='pc'`.
Use `parallax_mas`/`parallax_arcsec`, or declare units for generic `parallax`.
Conflicting or ambiguous columns are rejected; declination columns are degrees.
Required-field failures reject rows, optional missing values remain NaN, and
source order/duplicates are preserved. No uncertainty columns are propagated.

```python
from spaceship_viewer.catalog import load_csv
catalog = load_csv('catalog.csv', ra_unit='hour', distance_unit='pc',
                   coordinate_frame='ICRS', coordinate_epoch='J2000.0')
print(catalog.import_report.summary())
```

Declare frame/epoch only after verifying the source. Declaring them does not
transform the coordinates. The UI keeps them unspecified when absent. The
portable saved scene embeds catalog numbers and import provenance, so reopening
does not require the original CSV or network service.

## Deferred validation

Full Windows DPI/monitor combinations, clean-machine installation/updating,
live catalog retrieval, catalog measurements, synthetic photometry, and finite
voyage models require further validation. The labels, glow, grid, and marker
area scale are presentation choices, not additional physical transforms.

## Build and exercise the Windows package

`targets.py` stores portable named references separately from loaded catalog
rows. `navigation.py` provides camera-only apparent-object targeting
and a 16:9 independent-angular-axis FOV. `catalog_network.py` provides explicit
HTTPS mirror fallback without global Astroquery configuration changes.
`tools/check_hipparcos_live.py --output-dir <new-folder>` deliberately contacts
VizieR and saves a versioned diagnostic and full portable catalog snapshot.
`python -m spaceship_viewer --check-hipparcos <new-report.json>` performs a live
retrieval/serialization diagnostic and is also available in the frozen EXE.
These explicit live checks are separate from `--self-test`, which blocks Python
socket network attempts. The test suite uses controlled response fixtures.

Use a dedicated Windows x64 Python 3.12.10 environment, with
`packaging/requirements-runtime.lock` and `packaging/requirements-build.lock`.
Do not upgrade the shared science environment. See the
[release checklist](RELEASE_CHECKLIST.md) for build commands. The build isolates
native DLL discovery from unrelated tools on PATH. Its Qt hook excludes the
unused Virtual Keyboard plugin before dependency analysis. SVG/PDF backends are
explicit imports, and Astropy's runtime-required `tests.runner` is retained.

After building, use new paths for the actual executable/installer checks:

```powershell
python -X utf8 tools\verify_windows_install.py --assets dist\release `
  --work-dir work\install_check_v01 --report work\install_check_v01.json
```

This fixture uses real frozen executables, an isolated path with spaces,
Windows-only PATH, and a synthetic shortcut directory. It suppresses Installed
apps registration, checks single-instance launching, stages a clearly labeled
same-version repair package while the viewer runs, rejects a bad digest, checks
next-launch activation and rollback, and uninstalls while preserving synthetic
user files. It intentionally terminates only its own viewer process to exercise
lock recovery. It is not a second-machine or published-release test. Network
discovery/version ordering are covered separately by controlled unit fixtures.

The build command creates local assets only. The CI definition is read-only and
has no release-publication job; preparing it does not mean GitHub has run it.
