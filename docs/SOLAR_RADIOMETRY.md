# Sol: Doppler spectrum, surface radiance, and display mapping

Sol is a **uniform ideal 5772 K blackbody** at the fixed 1 AU observer event
defined in [the geometry model](SOLAR_MODEL.md). The temperature is the
[IAU 2015 B3 nominal effective solar temperature](https://www.iau.org/common/Uploaded%20files/IAUGA2015-Resolution-B3-recommended-nominal-conversion.pdf),
not a fitted or measured spectrum. The model has no limb darkening, absorption
lines, corona, atmospheric transmission, GR effects, orbit, or evolving distance.
It does not invent a measured solar V magnitude; the target magnitude stays null.

## Physical transformation

Source unit vectors point from observer to source; photons propagate oppositely.
For rest-frame ray s and velocity direction h:

```text
D = nu_observer / nu_rest = gamma (1 + beta s.h)
D = 1 / [gamma (1 - beta s'.h)]       (using apparent direction s')
lambda' = lambda / D
I_nu'(nu') = D^3 I_nu(nu'/D)
I_lambda'(lambda') = D^5 I_lambda(D lambda')
```

The [specific-intensity invariant Iν/ν³](https://www.astro.princeton.edu/~jeremy/heap.pdf)
therefore turns a blackbody into another blackbody along each ray:
Iλ'(λ') = Bλ(λ', D T). The implementation evaluates this shifted Planck
spectrum directly. **Multiplying it by another D⁴ would double count beaming.**
Bolometric surface radiance integrates to sigma (DT)^4 / pi, with ratio D⁴.
This is radiance per unit solid angle, not the disk-integrated irradiance or
flux. The latter also requires integrating over the aberrated disk and, for a
detector, its orientation and spectral response. The disk can have a Doppler
gradient; its center value is not assigned to all pixels.

Planck constants h=6.62607015e-34 J s, c=299792458 m/s, and
k=1.380649e-23 J/K are exact SI values. The code derives the Stefan–Boltzmann
constant from these. Wavelengths enter Planck's law in meters; Bλ is in
W m^-2 sr^-1 m^-1. Its exponential is evaluated without overflow. Visible tails
can underflow float64 to zero for extreme redshifts; no artificial brightness
floor is inserted, and the photosphere remains opaque.

## Visible integration and provenance

XYZ are trapezoidal integrals of Bλ times the official **CIE 1931 2° standard
observer**, at its original 471 nodes, 360–830 nm in 1 nm steps. Functions are
zero outside this interval. XYZ integrals have radiance units W m^-2 sr^-1;
683 times Y is model photopic luminance in cd/m². This is ideal standard-observer
photometry, not a calibrated image or a prediction for a particular observer.

[CIE 2019 data, DOI 10.25039/CIE.DS.xvudnb9b](https://cie.co.at/datatable/cie-1931-colour-matching-functions-2-degree-observer)
are bundled as an unmodified CSV and original metadata under **CC BY-SA 4.0**.
The CSV SHA-256 is
`fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1`;
loading validates it. Attribution and license accompany builds and exports.
Derived lookup/color data are attributed to CIE and distributed under the same
data license; application code remains MIT. No CIE endorsement is implied.

Inspector values use direct 1 nm quadrature. Pixel rendering interpolates XYZ
linearly in log(D) from 8193 nodes spanning the supported beta domain
0..0.999999. The checked 301-point geometric D grid from 0.08 to 1414 has maximum
relative XYZ error about 3.20e-4 where Y/rest Y > 1e-12, using rest Y × 1e-12
as the channel denominator floor. This bound concerns interpolation, not the
blackbody approximation or observer-model uncertainty. No stellar data are
smoothed, resampled, or modified.

## Display exposure and color

The [ICC sRGB definition](https://registry.color.org/rgb-registry/files/sRGB.pdf)
supplies the D65 XYZ-to-linear-RGB matrix and sRGB transfer curve. A real monitor
cannot emit solar luminance or all possible chromaticities. The display maps
relative Y as follows:

```text
r = Y / Y_rest
E = 0.5 × 2^(exposure_EV)
Y_display = E r / (1 + E r)
```

Exposure defaults to 0 EV and remains fixed through speed/heading changes.
Each +1 EV doubles linear exposure. Negative RGB components are clipped and Y
is restored; colors outside the output gamut are mixed toward a neutral gray
at fixed mapped Y. Bright cases approach white. The sRGB transfer curve is then
applied. These are documented display operations, not extra physical factors.
No chromatic adaptation, retinal adaptation, eye exposure, HDR monitor
calibration, or detector model is implied.

**Fit exposure once** chooses a fixed EV mapping the brightest model ray on the
whole disk to Y_display=0.3, limited to -40..+80 EV. A later boost keeps that EV.
It is an explicit viewing adjustment, not automatic brightness normalization.
At very low visible radiance the finite exposure range cannot reveal the disk.
The optional orange outline, central cross, and labels are annotations, not
emission. Uncheck **Doppler spectrum** for the legacy neutral geometry fill.
The point-star RGB and illustrative D³ marker controls do not affect Sol.

## Geometry, numerical images, and saved scenes

Neither exposure nor radiometry switches enter solar geometry, ray occultation,
camera, or FOV. The existing 720-ray polygon clips a 257×257 angular texture for
small front-facing caps. Horizon/large caps use the existing 401×401 angular
mask and contoured boundary; an RGB texture is clipped to it. Texture display
uses bilinear sampling. These display approximations do not set the analytic
radius or solid angle. Even a dark disk is opaque black inside its boundary.

Saved scenes include the model ID `planck-cie1931-srgb/1`, rest temperature,
fixed exposure, radiometry switch, and outline switch separately from geometry.
Opening 0.2.3 solar scenes preserves their neutral fill until explicitly enabled;
their original reference metadata are retained as provenance. Older viewers
may reject new settings. No new network request is needed for Sol rendering.

NPZ exports contain `solar_image_x_deg`, `y_deg`, `inside`, `doppler`,
`xyz_w_m2_sr`, and `rgb`, with the usual moving/rest panel prefixes. Array Y
increases with camera north, X with camera west, matching the view. Only cells
inside the membership mask represent solar rays; outside values are texture
padding. The analytic geometry and occultation arrays are also retained.
JSON records source/data hashes, units, model, EV, processing, and central
radiometric readouts. The verifier recomputes both physical and display arrays.

Tests cover the independent spectral identity Bλ(DT)=D⁵Bλ(Dλ,T), bolometric
integration, inverse-ray Doppler factors, disk gradients, CIE checksums,
interpolation error, fixed-exposure dimming, explicit exposure fitting,
unchanged geometry/occultation, legacy scenes, GUI controls, and export replay.
These establish computational consistency within the stated model; they do
not validate a measured solar spectrum or calibrated human visual appearance.
