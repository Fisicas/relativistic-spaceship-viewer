# Relativistic Spaceship Viewer 0.2.4

Unpublished local update: Sol now changes color and surface brightness with
speed and velocity heading. Its finite angular silhouette, aberration, and
background-ray occultation retain the 0.2.3 geometry.

Sol is a uniform ideal blackbody at the IAU nominal effective temperature
5772 K. Each apparent ray uses its own Doppler factor and spectrum Bλ(DT).
The invariant Iν/ν³ supplies the amplitude transformation; no additional D⁴
multiplier is applied to that spectrum. Bolometric surface radiance scales
as D⁴. Visible luminance is integrated separately against the official CIE
1931 2° observer and can differ greatly from the bolometric scaling.

The display uses fixed exposure, a luminance tone curve, and sRGB gamut mapping.
It cannot reproduce the Sun's physical brightness. **Display exposure** and
**Fit exposure once** help inspect dark redshifted cases without altering
angular size, physical radiance, camera, or FOV. The outline is an optional
geometry annotation. The point-star RGB and marker controls remain separate.

Portable scenes preserve model/version, temperature, exposure, and rendering
switches. Numeric exports include angular sampling, disk membership, per-ray
Doppler factors, physical XYZ integrals, display RGB, and CIE source hashes.
Old 0.2.3 solar scenes retain their neutral fill until Doppler rendering is
enabled. Original catalog data and the 33 named targets plus Sol are preserved.

The CIE CSV and metadata are bundled unmodified under CC BY-SA 4.0 with
attribution and license; code remains MIT. No live data download is needed to
render Sol. No measured solar spectrum, limb darkening, atmosphere, corona,
trajectory, distance evolution, or GR effects are introduced.
The declared Matplotlib minimum is now 3.8 for contour-path clipping. The pinned
build already uses 3.11.2; the shared science environment was not upgraded.

This update is local only. No GitHub push, tag, release, or upload is authorized
or performed. Windows binaries remain unsigned; a clean second Windows host
and a publicly hosted update remain unverified.
