# Sol: a finite disk at a fixed 1 AU observer event

Select **Sol**, then **Frame solar disk**. The original 33 named targets remain.
The rest Sun direction defaults to RA=0°, Dec=0° and is editable independently
of spacecraft velocity. Distance stays exactly 1 AU while speed/heading change.
This is a reproducible teaching configuration, not today's Earth position,
an orbit, acceleration history, or a finite voyage.

The model uses the [IAU 2015 B3 nominal radius](https://www.iau.org/common/Uploaded%20files/IAUGA2015-Resolution-B3-recommended-nominal-conversion.pdf)
R=695,700,000 m and the [IAU-defined astronomical unit](https://iau-a3.gitlab.io/res.html)
d=149,597,870,700 m. These are nominal conversion constants, not measurements
with estimated uncertainties. The rest angular radius is alpha=asin(R/d),
giving a diameter of 0.5329062144923112° at 1 AU.

## Boosted silhouette

Let c be the rest direction to the Sun center and h the velocity unit vector.
The rest silhouette is the spherical cap c·s >= cos(alpha). Applying the
existing source-direction aberration to each limb ray preserves a circle on
the celestial sphere. Its apparent cap center is A/|A|, where

```text
mu = c·h
A = (c - mu h)/gamma + (mu + beta cos(alpha)) h
k = cos(alpha) + beta mu
alpha' = atan2(sin(alpha)/gamma, k)
Omega' = 4 pi sin(alpha'/2)^2
```

The atan2 form remains valid when the disk covers more than a hemisphere.
The aberrated central ray can differ from the apparent limb-circle center;
the inspector reports both. Camera tracking and framing use the latter.
The displayed through-disk diameter is 2 alpha', which can exceed 180° for a
large cap. Such a full limb cannot fit the front-hemisphere angular projection.
The existing independent-atan2 map can distort the projected shape of wide
circles; no extra Lorentz contraction is applied to the image.

For motion along the center direction, the independent axial check is
tan(alpha'/2)=sqrt((1-beta)/(1+beta)) tan(alpha/2). For motion directly away,
replace that multiplier by its reciprocal. At beta=0.9, the diameters are
0.1222572790° toward and 2.3228089843° away. Distance is unchanged in both cases.

D=gamma(1+beta s·h) is evaluated for center and limb rays. Solid angle is
independently checked by quadrature of dOmega'=dOmega/D^2 over the rest cap.
No smoothing, empirical angular scaling, or marker-area proxy sets disk size.

## Rendering, occultation, and limits

Small/front-facing disks use a 720-sample transformed limb polygon. When the
boundary crosses the camera horizon or the cap exceeds a hemisphere, rendering
uses a 401×401 angular grid with a linearly contoured analytic-cap mask. That
display sampling does not set the analytic radius, solid angle, or occultation.

Catalog objects are treated as distant background rays. Rays inside the rest
solar cone are hidden from the plotted scene; this membership is invariant
under a common boost. The occultation mask is exported separately. Unmodified
catalog rows are retained, and original Doppler/apparent-direction arrays are
retained; visible masks, visible colors, and marker arrays reflect occultation.
Nearby foreground objects are not modeled; catalog distance labels do not
provide a finite-distance ray tracing model. Named reference crosses remain
navigation annotations, not detected sources.

Sol's color and surface brightness now use a uniform ideal 5772 K blackbody
shifted per ray. See [radiometry and display mapping](SOLAR_RADIOMETRY.md).
The geometry in this document is unchanged by exposure or rendering switches.
Limb darkening, corona, atmospheric effects, and GR deflection are not modeled.
The illustrative RGB/D^3 point-star controls do not affect Sol. The saved
target magnitude remains null, not a fabricated measured V magnitude.

## Controls and reproducibility

- **Track Sol as boost changes** keeps the disk centered without changing
  velocity or FOV. Turning on camera/velocity lock disables solar tracking.
- **Frame solar disk** centers the disk and sets FOV to three times its current
  diameter, limited by the 0.001° minimum and 160° maximum (and 16:9 limits in
  focus mode). Subsequent boost changes do not autozoom away the size effect.
- **Toward / Away / 90°** explicitly set velocity heading relative to Sol and
  enable solar tracking. The three original fixed headings and Custom: Sol
  remain available. Custom: Sol locks the camera to velocity as usual.
- **Show solar disk** controls silhouette display and background occultation.
  Reset disables the optional model. Selecting another target keeps an enabled
  Sun in the sky while leaving ordinary camera navigation available.

Scene JSON includes model ID, nominal radius and observer distance in meters,
direction, visibility/tracking flags, and the separate Sol reference. NPZ
exports include per-panel rest/transformed limb rays, limb Doppler factors,
central ray, cap center, radii in radians, solid angle in steradians, Doppler
limits, and the candidate-aligned occultation mask. The export verifier replays
the solar-aware view. Old scenes without solar settings still load.

Tests verify rest/axial limits, arbitrary directions and poles, transformed-limb
circle membership, independent solid-angle integration, invariant occultation,
saved state, Qt controls, and small/large-cap exports. These validate the ideal
SR model computationally, not observational properties or calibrated images.
