# Physical conventions and numerical scope

The optional [Sol model](SOLAR_MODEL.md) adds a static finite photosphere one AU
from this same observer event. Its editable direction is a teaching reference,
not a dated ephemeris. Solar limb directions use the same Lorentz boost; an
analytic spherical-cap calculation supplies angular radius/solid angle, and
rest-cone membership supplies distant-background occultation. The stellar
Lorentz transform and input catalog values are unchanged.

This development version models one instantaneous special-relativistic observer
at the catalog origin. Numerical verification of the directional transform does
not validate the stellar catalog, photometry, RGB appearance, or a finite voyage.

## Directions, frames, and units

- The catalog frame is the frame in which the stored source directions and V
  magnitudes are taken as input. Its origin is held fixed. No source velocity,
  time evolution, observer translation, proper motion, or retarded-time solution
  is calculated. Neither stellar nor observer acceleration is modeled.
- RA and declination are equatorial angles in **degrees** internally. RA is
  reduced modulo 360 degrees, with imported wrap counts reported; declination is
  validated in [-90, 90] degrees. Catalog distances are **parsecs** and are
  labels only. Sol uses a separate physical radius and fixed 1 AU distance.
- The inherited 33-object demo has unspecified coordinate frame, epoch, and
  original measurement provenance. Its approximate values are preserved, not
  promoted to an accurate astrometric reference. It is not magnitude-complete.
- VizieR `I/239/hip_main` RAICRS/DEICRS are ICRS at **J1991.25 (TT)**, not
  coordinates propagated to the present. See the [ESA catalog documentation,
  section 2.1](https://cdsarc.cds.unistra.fr/ftp/pub/aliases/H/HIP_1_/version_cd/docs/vol1/sect2_01.pdf).
  A CSV's frame/epoch stay unspecified unless supplied explicitly to `load_csv`.

Let **s** be a unit vector **from observer to source**, **h** the observer's
velocity heading in catalog-frame axes, and beta = v/c. Incoming photon
propagation is **-s**, so confusing source direction with photon momentum would
reverse the boost signs. The ship-frame spatial axes are aligned by a standard
rotation-free boost; the camera triad is specified separately in these axes.
This is a sequence of independent instantaneous views, not a dynamical model
for attitude transport or accumulated Wigner rotation.

## Aberration and Doppler factor

With mu = s dot h, gamma = 1/sqrt(1-beta^2):

```math
D = \frac{\nu_{\rm ship}}{\nu_{\rm rest}} = \gamma(1+\beta\mu),
\qquad \mu' = \frac{\mu+\beta}{1+\beta\mu},
\qquad \mathbf{s}'_\perp = \frac{\mathbf{s}-\mu\mathbf{h}}{\gamma(1+\beta\mu)}.
```

The apparent vector is mu' h + s'_perp. Wavelength ratios are
lambda_ship/lambda_rest = 1/D. D > 1 is blueshift; D < 1 is redshift.
For beta > 0 the transition is

```math
\mu_{D=1} = \frac{1/\gamma-1}{\beta}.
```

Some sources with mu < 0 are therefore blueshifted. Exactly transverse sources
have D = gamma. Forward/backward sources have D = gamma(1 +/- beta).

The core accepts signed beta for inverse-transform tests and explicitly supports
|beta| <= **0.999999**. The Qt application uses nonnegative beta through **0.999999** and a rapidity
slider. The preserved Tk interface retains its original **0 to 0.999** slider. Values outside these domains raise errors;
they are not silently clipped. Unit-vector input is validated with an absolute
norm tolerance of 2e-12. Dot products are clipped to [-1,1] only for roundoff,
and output directions are renormalized to remove floating-point norm drift.
This does not represent a physical correction or uncertainty estimate.

Tests construct a separate Lorentz matrix for photon four-momenta p=(1,-s)
in units c=1, transform p, and compare E'=D and -p'/E'=s'. They also check
inverse boosts, half-angle identities, rotational covariance, and
dOmega'/dOmega = 1/D^2. These checks do not establish calibrated radiometry.

## Camera and projection

Camera pointing and velocity heading are independent state variables. The
default lock makes the camera point along the heading. With lock enabled,
dragging steers both; without it, dragging changes only camera orientation.
Changing camera orientation alone leaves apparent vectors and D unchanged.
Applying a heading or re-enabling lock selects the equatorial east/north
orientation; continuous dragging preserves the full camera triad, including
roll, across coordinate poles. At a pole RA is a meridian convention.

For camera forward f, east e, and north n (f cross e = n), the inherited map is

```math
x = -\operatorname{atan2}(\mathbf{s}'\cdot\mathbf{e},\mathbf{s}'\cdot\mathbf{f}),
\qquad y = \operatorname{atan2}(\mathbf{s}'\cdot\mathbf{n},\mathbf{s}'\cdot\mathbf{f}).
```

Axes are displayed in degrees: **right is camera west** and **up is camera
north**. The default square view spans +/-22.5 degrees on each axis. Qt's
**Focus sky** changes that to a 16:9 viewport, initially 80 by 45 degrees
from the default view, and restores the previous FOV on exit. Its axes have
equal angular scale; resizing the panel does not stretch the map. The forward
hemisphere condition s' dot f > 0 is also required. This is an independent
two-angular-axis map, not a gnomonic plane, equal-area map, or calibrated
camera sensor. Rectangular corners have a larger angular separation from the
center than either half-FOV. The inverse half-angle readout describes a central
axial slice of a velocity-centered cone, not the full rectangle; it is omitted
when the camera is unlocked.

## Catalog selection, missing values, and uncertainty

The V magnitude limit selects **rest-frame catalog objects before boosting**.
It is not an apparent detection threshold. A brightened object absent from the
input catalog cannot appear. Import and magnitude filtering preserve row order
and duplicate objects; no source matching or deduplication is performed.

Required RA, Dec, or V magnitude failures reject rows and record CSV line
numbers/reasons. Missing or invalid optional B-V/distance values remain NaN.
CSV source bytes are SHA-256 identified. Unit declarations, wrapped RA counts,
rejected rows, and unknown optional values are recorded in `ImportReport`.
No smoothing, baseline correction, normalization, interpolation, resampling,
or stochastic noise is applied. No uncertainty propagation is performed.
Extra columns, including uncertainty columns, are not used by this schema.

Positive parallax can be converted geometrically as d_pc = 1000/parallax_mas
or 1/parallax_arcsec. Nonpositive, missing, or invalid parallax yields unknown
distance. This is not a statistically inferred distance: parallax uncertainty,
selection, covariance, and distance priors are not modeled. The Qt application
caches accepted Hipparcos values, metadata, and the import report as a
hash-verified local snapshot. This is not an archive of the original VOTable;
archival use requires saving that source table independently. Offline tests
use controlled masked tables and do not verify the network service.

## Illustrative catalog display model, retained for baseline parity

The following marker model applies to catalog objects. Sol instead uses a
5772 K blackbody with per-ray Doppler transformation and CIE color integration;
its exposure and tone mapping are separate from angular geometry. See
[SOLAR_RADIOMETRY.md](SOLAR_RADIOMETRY.md) for its numerical approximations and
display limits. Neither display provides calibrated screen brightness.

The B-V-to-temperature formula is the inherited Ballesteros approximation
([Ballesteros 2012](https://arxiv.org/abs/1201.1809)). Before display only,
unknown B-V is replaced by 0.65 and B-V is clipped to [-0.40, 2.20]. The catalog
itself retains NaN. For shifted colors the temperature proxy is multiplied by
D; the inherited empirical temperature-to-RGB map clips to 1000--40000 K.
No response curves, extinction correction, color calibration, spectral lines,
or cone-response integration is performed.

Optional brightness uses m_display = m_V - 7.5 log10(D). Before clipping, marker
**area** is 28 * 10^[-0.4(m_display-1)] square points; the actual area is clipped
to [0.35, 260] square points. This is an illustrative marker-area mapping, not
an observed V magnitude, specific intensity, energy flux, or photon rate.
Glow adds translucent, larger markers, and is presentation only. A D^3 factor
does not by itself define a complete spectral or band-integrated observable.

M42 is tagged `extended_demo`: the preserved point marker and stellar-style
color proxy do not represent its resolved morphology or nebular spectrum.
Approximate distances, including M42's, remain labels and do not enter the boost.

## Baseline and intentional changes

All inherited catalog numbers, the boost convention, projection, and display
mapping are preserved for reference scenes at beta 0, 0.30, 0.87 and exactly
gamma=2 (beta=sqrt(3)/2). Beta 0.87 actually has gamma=2.0281847858.
`tests/reference/` holds numerical arrays captured from commit
`0f4d46a7451f71969c3d90b9225703e64b1a691b` with the recorded environment.
Reproduction is described in `docs/DEVELOPMENT.md`.

Intentional changes: explicit CSV units replace value-based inference;
parallax is converted instead of mislabeled as pc; invalid core input is
rejected; masked catalog values stay unknown; camera and heading are separate;
continuous camera rotation retains its triad; drag scaling now uses the actual
axes rectangle rather than the full widget; UI text identifies approximations.
Tk worker threads now pass fetch results/errors through a main-thread queue.
The original documentation JPEGs are retained as historical artifacts; the
README uses regenerated high-resolution figures with portable source scenes.

## Qt presentation and portable exports (0.2.0.dev2)

The validated scene calculation is unchanged. Qt and scientific exports use
`plotting.py`, with a dark palette, optional grid, and a separate marker-area
scale (default 0.85, applied after the core area clipping). Glow uses translucent
larger markers. These are presentation changes only. Labels use deterministic
screen-space collision avoidance, prioritizing the brightest display proxies
and selected object, with a candidate budget max(24,min(64,2*max_labels)). Some
labels may be omitted; no plotted catalog objects are removed by label layout.

The comparison's rest panel uses beta=0 with the same camera triad, FOV, rest V
cut, and catalog as the moving panel. The inspector always reports the selected
object's moving-observer values, even if the object was selected in the rest
panel. Its 550 nm wavelength shift is an example, not a measured spectral line.

Scene JSON preserves the full camera triad and catalog snapshot, including NaN
as JSON null, row order, metadata, and display choices. Derived NPZ arrays,
artifact hashes, runtime versions, and source hashes accompany figure exports.
No source CSV or live service is needed to reopen the embedded catalog. See
[EXPORTS.md](EXPORTS.md) for verification and reproducibility limits.
