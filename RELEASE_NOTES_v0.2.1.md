# Relativistic Spaceship Viewer 0.2.1

Unpublished local patch. Selecting an inspector object now centers its apparent
direction in the moving view and unlocks the camera while preserving velocity.
The Orion, Galactic Center, and Tau Ceti heading presets remain. The fourth
entry becomes **Custom: [selected object]**; choosing it explicitly steers toward
that object's rest catalog direction and locks/recenters the camera. A manual
heading that differs from the selected object is labeled separately.

Focus sky now uses a 16:9 angular viewport. It preserves vertical FOV where
possible, expands horizontal FOV to 16/9 of it, recalculates visibility, and
keeps equal angular scales. The 160-degree horizontal limit caps vertical FOV
at 90 degrees. Zoom preserves this ratio; leaving focus restores the prior FOV.
The existing independent-atan2 angular projection and Lorentz equations remain.

Hipparcos retrieval uses the CDS-listed Harvard, IDIA, and main HTTPS servers
with bounded timeouts and fallback, recording the successful server and prior
failures. Global Astroquery settings are unchanged. CDS reported its main
service as degraded in November 2026: https://vizier.cds.unistra.fr/.
Failures retain the current catalog; missing values and scientific conventions
remain unchanged. Rejected-row indices now use native Python integers so real
Hipparcos rejection reports can be saved in portable JSON scenes. The row
validation rules and numerical values are unchanged. Added navigation,
mirror-fallback, Qt, and frozen checks.

The installer is unsigned. No GitHub push or publication occurs during this
local preparation. Live service checks establish retrieval, not scientific
validation of the catalog or calibrated photometry.
