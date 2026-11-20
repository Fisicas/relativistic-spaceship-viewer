# Scientific exports and portable scenes

Optional Sol scenes preserve a fixed 1 AU model, nominal radius in meters,
editable direction, visibility/tracking flags, and separate target data. Per
panel, NPZ includes solar rest/apparent limb rays, central ray, cap center,
angular radius in radians, solid angle in steradians, Doppler values, and a
candidate-aligned occultation mask. Stellar visible arrays reflect that mask;
original catalog data and pre-visibility directions/Doppler arrays are retained.
The verifier replays the solar-aware view. [Solar model](SOLAR_MODEL.md) describes
the 720 limb samples and 401×401 display-mask fallback. With solar radiometry
enabled, NPZ also stores per-ray Doppler, color, and radiance arrays with their
inside-disk mask. The texture uses numerical lookup interpolation and display
sampling described in [SOLAR_RADIOMETRY.md](SOLAR_RADIOMETRY.md); this is an
idealized blackbody model, not calibrated screen photometry.

Version 0.2.2 embeds a selected named reference separately from the sky catalog,
including its full values and provenance. Reference crosses are annotations and
are excluded from the measured-source counts and NPZ catalog arrays. Older
scenes without this optional field still load; older application versions may
reject scenes containing the new presentation field.

The Export dialog creates a new `name_v01`, `name_v02`, etc. folder under the
chosen parent. Existing exports are never overwritten. Choose 4K landscape
(3840 x 2160), Full HD (1920 x 1080), or square (2400 x 2400). The Python API can
also request other sizes within the documented 7680-pixel limits.

| File | Contents |
|---|---|
| `scene.png` | Exact requested pixel dimensions; no tight cropping |
| `scene.svg` | Vector figures with editable text; local font substitution may alter appearance |
| `scene.pdf` | Vector figure with embedded TrueType fonts |
| `scene.json` | Full portable catalog, camera triad, view/presentation settings, and provenance |
| `scene_data.npz` | Candidate directions, D, mu, projection, visibility, display proxy, core marker areas, RGB, and visible original row IDs |

All figures state heading, camera, FOV, speed, selection, and display
approximations. Source/catalog order is preserved. Stellar arrays undergo no
numerical smoothing, interpolation, resampling, or uncertainty propagation. Raster
antialiasing and glow are presentation effects.

JSON encodes unknown B−V and distance values as `null`; reopening restores NaN.
The catalog checksum identifies the embedded columns, metadata, and import
report. A source CSV hash, when available, is distinct from this snapshot hash.
The saved camera includes all three basis vectors, preserving roll. The default
app version, runtime/library versions, source-file hashes, figure dimensions,
font, label policy, actual drawn label counts, and artifact hashes are recorded.
The source path is provenance only; loading never reads it or contacts a server.

`scene_data.npz` is loaded with `allow_pickle=False`. Candidate-sized arrays
refer to objects retained by the rest V cut; `visible` indexes those candidates.
Display-magnitude/core-marker-area/RGB arrays are visible-object-sized. Visible
catalog row IDs refer to the original embedded catalog, including duplicate
names. The presentation marker scale is stored separately and applied after
the core marker-area calculation. Prefixes are `moving_` and, in comparison
mode, `rest_`.

Reopen an exported `scene.json` with **Open scene**. For a reproducibility check
from the checkout root:

```powershell
.\.venv\Scripts\python.exe -X utf8 .\tools\verify_export.py 'C:\path\to\scene.json' `
    --rerender-parent 'C:\path\to\new_reproduction_folder'
```

The verifier checks artifact hashes and recomputes arrays within 2e-12
absolute/relative tolerance. Optional re-rendering compares PNG pixels in the
current environment and writes a new versioned result. A pixel mismatch is
reported instead of silently claiming identical output. Different library/font
versions can alter pixels or label placement while the numerical model agrees.
SVG/PDF file hashes may change with document timestamps; file-byte identity is
not the scientific reproducibility criterion.

Exporting is a local operation. It does not publish, upload, or validate the
catalog's measurements or calibrated photometry. If an export fails, an
`INCOMPLETE.txt` marker remains in its new directory; the next attempt gets a
new version rather than overwriting that result.
