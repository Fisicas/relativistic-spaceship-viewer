# Relativistic Spaceship Viewer 0.2.3

Unpublished local Sol feature. The inspector retains the original 33 named
objects and adds **Sol** as entry 34. Sol is a finite angular disk at a fixed
observer event one AU from a static spherical photosphere, using the IAU nominal
radius 695,700 km. The default teaching direction is RA=0°, Dec=0°; both are
editable. This is not a dated ephemeris or a trajectory calculation.

The disk's limb is aberrated ray by ray. Inspector readouts include rest and
apparent angular size, limb-cone half-angle, solid angle, central/limb Doppler
factors, and a 550 nm wavelength example. Neutral disk fill shows geometry;
solar colors, radiometry, spectra, and limb darkening are not modeled. Point-star
marker-area settings do not resize the Sun. Distant catalog rays through the
photosphere are occulted and recorded in exported masks.

Frame solar disk sets a useful angular zoom without steering velocity. Optional
tracking follows the apparent limb-circle center while boost controls change,
keeping the FOV fixed so size changes remain visible. Toward, Away, and 90°
buttons set boost heading explicitly. Independent Sun direction controls do
not steer velocity. Zoom now reaches 0.001° for high-speed small disks.

Solar constants, fixed-distance model identifier, direction, display/tracking
settings, limb rays, Doppler values, cap geometry, and occultation masks are
preserved in portable scenes and numeric exports. New tests cover analytic
limits, independent solid-angle integration, full-hemisphere cases, GUI use,
saved state, and frozen export. Existing stellar Lorentz calculations and
catalog values remain unchanged. No GitHub push or release occurs in this task.
