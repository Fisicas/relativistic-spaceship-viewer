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

Click a star or use the catalog-object dropdown. The inspector gives rest and
apparent directions, angles to the velocity heading, D, and an example wavelength
shift. It reports the moving-observer values even when selected from the rest
panel. An object chosen from the dropdown may be outside the FOV or magnitude
selection; that status is stated explicitly. Distance is a catalog label only.
Unknown optional values remain unknown; a missing B−V uses 0.65 only for display.

## Catalogs and saved scenes

CSV imports ask for ambiguous units and show an acceptance/rejection report.
Canceling the preview leaves the current catalog intact. **Catalog provenance**
shows frame/epoch, source identification, and import notes. Hipparcos retrieval
is optional and runs without blocking the UI; failures keep the previous catalog.
If a newer scene is opened while a request is pending, the old result is discarded.

**Save scene** writes a new JSON file and refuses an existing filename. **Open
scene** loads its embedded catalog and settings without reading the original
source path. **Export** creates a new versioned folder with figures, arrays, and
a portable scene. See [EXPORTS.md](EXPORTS.md) for formats and verification.
