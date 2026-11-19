# Relativistic Spaceship Viewer 0.2.5

Unpublished local update. Control surfaces, plot backgrounds, grids, and annotations
now use neutral charcoal, black, and gray. The selected angular-window logo has
an inspectable flat SVG source and Windows icon; cyan and amber are restrained
brand accents. Scientific star/Sol color and radiance calculations are unchanged.
The README/social banner uses actual γ=2 demo coordinates rather than generated
galaxy artwork. The prepared social image is 1280×640 and under 1 MB.

A thin viewport bezel and long speed slider remain available while focusing
the sky. Both speed sliders use the same rapidity mapping. Wide focused windows
place γ, β, catalog Doppler range, and counts beside the viewport; smaller
windows retain top readouts. The active map keeps equal angular scales and the
existing 16:9 focused FOV. No background stretching or projection changes occur.

The catalog chooser asks on first launch and can remember demo or local
Hipparcos. A requested download retrieves the complete main catalog's six
required columns once, then saves a versioned, hash-verified processed snapshot
under the current user's application data. Future loads are offline. Rest V
filtering is local, so changing speed, heading, or magnitude cutoff does not
download another table. Refresh is an explicit action; failed retrieval/load
preserves the current catalog. Earlier snapshots are retained. The original
33 named targets plus Sol remain in the inspector.

The measured complete query returned 118,218 rows, accepting 117,955 and
recording 263 rejected rows with invalid required coordinates or magnitude.
Decoded VOTable size: 12,573,101 bytes. Verified compressed snapshot:
2,763,294 bytes for this retrieval. HTTP gzip was enabled; decoded response size
is not a measurement of TCP/TLS transfer bytes. This is a processed application
snapshot, not the full historical Hipparcos distribution or raw VOTable archive.
ICRS J1991.25 coordinates, missing optional values, existing positive-parallax
distance inversion, row order, and rejection metadata are preserved. No proper
motion propagation, uncertainty model, or scientific-validation claim is added.

No GitHub push, tag, release, or upload is performed. The user will handle all
pushing and the repository's separate Social preview setting. Windows binaries
remain unsigned; native multi-monitor DPI and a clean second host remain open.
