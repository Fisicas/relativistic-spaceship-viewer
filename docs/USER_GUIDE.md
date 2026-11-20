# Using the viewer

Start with Orion at rest. Set gamma to 2, then choose **Compare rest / moving**
to see what the boost does. The two panels share camera orientation, angular
field of view, and catalog selection. The rest panel has beta=0.

## Speed and pointing

Enter either beta or gamma; changing one updates the other. The gamma=2 preset
uses beta=sqrt(3)/2 internally, rather than rounding beta to 0.87. Displayed
numbers are rounded; portable scenes retain the underlying double-precision
values. The speed slider uses rapidity to give useful control near c. The Qt
range is 0 <= beta <= 0.999999, the tested core domain.

Heading RA/Dec are degrees in the catalog rest-frame axes. **Apply velocity
heading** applies typed entries. A preset also changes that heading. With camera
lock on, the view follows it. Unlock to look around while keeping velocity fixed.
**Recenter camera** points back along the heading. Heading changes do not move
an unlocked camera. Continuous drags preserve camera roll through coordinate poles.

Drag with the left button to grab the sky or the right button for yaw/pitch in
the opposite sense. The wheel adjusts both angular FOV axes. To use keyboard
navigation, click the sky first: arrows turn, R resets, C toggles comparison,
I toggles the inspector, and F expands the sky. Ctrl+O opens a scene, Ctrl+S
saves one, and Ctrl+E exports. Numeric-entry arrows keep their normal editor role.
Reset returns view/presentation defaults and keeps the current catalog.

## Interpreting the view

Right is camera west; up is camera north. Axes are angular coordinates in
degrees, not a planar gnomonic camera sensor. Horizontal and vertical FOV can
be adjusted independently. The central half-angle readout applies to a
velocity-centered view and is omitted when the camera is unlocked.

**Rest V limit** filters catalog objects before the boost; it is not an observed
detection threshold. The sparse demo cannot reveal objects that were not
included. Doppler RGB, illustrative D³ marker brightness, glow, grid, marker area
scale, and label limit can be changed independently. Labels are suppressed when
they overlap; every selected visible object is still drawn.

## Inspecting an object

The dropdown contains the original **33 named stars and locations** in
their original order, plus **Sol** as entry 34, even with Hipparcos loaded. Click any plotted catalog
star to inspect its actual measurement row without adding HIP identifiers to
the dropdown. The three fixed heading presets remain unchanged.

With an external catalog, original named selections are explicitly labeled
navigation references using the inherited demo coordinates and approximate
values (frame/epoch unspecified). They are not cross-identifications with the
background catalog. A neutral reference cross marks their location and is not
included in the source count. Saved scenes embed the selected reference values
and provenance separately from the loaded catalog.

Selecting an object centers its **apparent** direction in the moving view and
unlocks the camera; the velocity heading and all Doppler factors stay unchanged.
Selecting it again recenters after panning. The fourth heading choice becomes
**Custom: [object name]**. Choose that entry to explicitly steer toward its rest
catalog RA/Dec and lock the camera along the new velocity heading. Orion,
Galactic Center, and Tau Ceti remain available. Manual RA/Dec entries remain
independent; they are not mislabeled as the current inspector target.

Click a star or use the named-target dropdown. The inspector gives rest and
apparent directions, angles to the velocity heading, D, and an example wavelength
shift. It reports the moving-observer values even when selected from the rest
panel. A target excluded by the rest V limit stays excluded even after camera
centering; selection never changes that scientific filter. Distance is a catalog label only.
Unknown optional values remain unknown; a missing B−V uses 0.65 only for display.

## Catalogs and saved scenes

CSV imports ask for ambiguous units and show an acceptance/rejection report.
Canceling the preview leaves the current catalog intact. **Catalog provenance**
shows frame/epoch, source identification, and import notes. Hipparcos retrieval
is optional and runs without blocking the UI; failures keep the previous catalog.
The client tries the CDS-listed Harvard, IDIA, and main HTTPS servers with
15-second timeouts per attempt. Provenance records the successful mirror and
prior errors. No global Astroquery configuration is changed. The mirror used
does not change the catalog epoch or propagate proper motion.
If a newer scene is opened while a request is pending, the old result is discarded.

On first launch the catalog chooser offers the demo or a local Hipparcos library.
It can remember the choice. **Load local Hipparcos** reads a verified snapshot;
**Download / refresh Hipparcos** requests all main-table rows in six columns and
saves a versioned local copy. Speed, pointing, and rest V changes then use that
library without downloading it again. A missing or invalid cache asks before a
download; failed loads preserve the current view. **Application → Catalog
startup** changes the startup choice. See [CATALOG_LIBRARY.md](CATALOG_LIBRARY.md).

**Save scene** writes a new JSON file and refuses an existing filename. **Open
scene** loads its embedded catalog and settings without reading the original
source path. **Export** creates a new versioned folder with figures, arrays, and
a portable scene. See [EXPORTS.md](EXPORTS.md) for formats and verification.

## Widescreen focus

For Sol, use **Frame solar disk** and the optional tracking and heading controls
in its inspector. The fixed teaching geometry defaults to Sun RA=0°, Dec=0° at
1 AU; it does not change distance as speed changes. Zoom reaches 0.001° to show
small high-speed solar disks. See [SOLAR_MODEL.md](SOLAR_MODEL.md) for constants,
ray geometry, occultation, and sampling. Sol's color and surface brightness use
a uniform ideal 5772 K blackbody shifted separately along each apparent ray.
**Display exposure** and **Fit exposure once** alter display mapping without
resizing the disk or changing physical radiance. Very redshifted visible light
can be nearly black. See [SOLAR_RADIOMETRY.md](SOLAR_RADIOMETRY.md) for the spectrum,
tone mapping, and scientific limits. Older neutral-fill scenes retain that fill
until **Doppler spectrum** is enabled.

**Focus sky** hides the panels and sets each sky viewport to 16:9, keeping equal
pixels per angular degree. The existing projection has independent atan2 axes,
so horizontal FOV = (16/9) × vertical FOV. At 45° vertical, this is 80° × 45°.
The Lorentz transform is unchanged; source visibility is recalculated for the
new angular limits. Objects are not stretched to fill the wider screen.

Vertical FOV is preserved unless the 160° horizontal cap requires reducing it
to 90°. Zoom keeps the ratio. Leaving focus restores the prior FOV; opening a
scene or resetting exits focus before applying that scene's settings. Comparison
uses the same angular limits and camera in both panels, each at 16:9. Exports
and saved scenes retain the actual horizontal/vertical FOV.

The thin window surround is outside the sky projection. The long speed slider
uses the same rapidity mapping as the sidebar, and both stay synchronized.
Wide focused single-panel windows show γ/β and catalog readouts beside the sky;
smaller windows retain the top cards. These controls do not stretch the map.
