# Relativistic Spaceship Viewer 0.2.6

This release brings the desktop refurbishment together while keeping the
instantaneous special-relativistic model visible and inspectable.

- A charcoal Qt interface, angular-window icon, viewport bezel, wide synchronized
  speed slider, and responsive γ/β and catalog readouts.
- Camera-only centering from the object inspector, explicit Custom: [object]
  velocity headings, and a 16:9 focused sky with equal angular scales.
- The original 33 named targets remain accessible with the full Hipparcos sky.
  Hipparcos downloads once into a verified, versioned local library; the startup
  chooser can remember demo or offline-library use. Refresh is explicit.
- Sol is a finite disk at a fixed 1 AU observer event, with editable teaching
  direction, exact aberrated cap geometry, background occultation, and per-ray
  Doppler-shifted ideal 5772 K blackbody radiance. Exposure and framing remain
  independent of physical angular size.
- High-resolution PNG/SVG/PDF exports, portable scenes, numeric arrays, hashes,
  model/processing provenance, and regenerated README examples.
- A per-user Windows setup, stable launcher, single-instance behavior, verified
  version slots, deferred update activation, and rollback. Selected checkboxes
  now show an actual check mark throughout the app.

The Windows setup is for initial installation; the matching Windows ZIP is the
managed-update payload. Source pushes alone do not distribute updates. Stable
releases require matching vMAJOR.MINOR.PATCH tags, exact asset names, and valid
GitHub SHA-256 asset digests. Drafts and prereleases are not offered by the updater.

Scientific scope: instantaneous directions, not a voyage or evolving distance.
Point-star RGB and D³ marker areas are illustrative; Sol uses a uniform ideal
blackbody without limb darkening or absorption lines. Catalog uncertainties,
proper motions, and new distance inference are not modeled. Computational checks
do not establish observational accuracy or calibrated human visual appearance.

Code is MIT; bundled CIE observer data and derived color data retain their separate
CC BY-SA 4.0 attribution. Binaries are unsigned. A clean second Windows host,
native multi-monitor DPI, and a publicly hosted update remain outside the local
verification evidence. See the installation guide and release checklist.
