# Relativistic Spaceship Viewer 0.2.2

Unpublished local inspector usability patch. The object picker always retains
the original 33 named stars/locations in their original order. Loading Hipparcos
does not add its thousands of HIP identifiers to this dropdown. Clicking stars
in the sky still inspects individual rows in the loaded catalog.

Original named targets are independent navigation references when a different
catalog is loaded. Their original coordinates, approximate values, and provenance
are retained; they are not silently matched to, appended to, or substituted for
Hipparcos measurements. A labeled reference cross marks the selected location.
Sky counts and scientific arrays remain those of the loaded catalog.

Selection still centers the apparent direction without steering. Choosing
Custom: [object] still explicitly changes velocity heading. Named selections
survive catalog loading and portable scene/export round trips, with the full
reference values embedded. Existing scenes without a reference field still load.

The physics, 16:9 focus behavior, Hipparcos query, and row-validation rules are
unchanged. New reference/picker regressions and frozen checks cover the fix.
The Windows binaries are unsigned; no GitHub publication occurs in this task.
