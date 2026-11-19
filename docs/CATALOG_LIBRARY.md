# Hipparcos as a local library

The startup chooser offers the built-in demo or Hipparcos. **Remember my choice**
can select either for later launches; otherwise it asks again. A remembered
Hipparcos choice loads a verified local snapshot. If no usable copy exists,
the app asks before downloading. It never downloads a catalog merely because
the program opened. Saved-scene catalog data remain self-contained.

**Load local Hipparcos** uses the snapshot without a network call. **Download /
refresh Hipparcos** is an explicit network action. The first download requests
all main-table rows, selecting HIP, RAICRS, DEICRS, Vmag, B−V, and Plx. The display
uses its existing local rest-frame V cut. This avoids another query when that
cut changes. The whole historical distribution and Tycho are not requested.

## Storage and integrity

Snapshots live under `%LOCALAPPDATA%\RelativisticSpaceshipViewer\catalogs\hipparcos`.
`latest.json` identifies a versioned `hipparcos-<sha256>.json.gz` file. The outer
hash checks compressed bytes; the existing scene codec also checks the embedded
catalog payload. Files are bounded to 64 MiB compressed and 128 MiB decoded;
unsafe filenames, unsupported schemas, altered bytes, and invalid catalog
values are rejected. JSON is used rather than executable/pickle serialization.
The pointer changes only after the new snapshot is written and verified.
Previous snapshot files remain intact. Installer updates do not replace this
separate user-data folder. Startup preferences are in `catalog-settings.json`.

This is a **processed app catalog snapshot**, not the original VOTable. It
retains accepted rows, optional nulls, coordinate frame/epoch, source/retrieval
metadata, and the row-rejection report. The adapter preserves its existing
positive-parallax inversion from mas to pc and maps missing/invalid optional
values to unknown. No sorting, smoothing, resampling, uncertainty propagation,
proper-motion correction, or new distance inference is introduced.

The local measurement archive retains an original VOTable and its SHA-256 for
verification; routine app downloads do not claim to archive their raw response.
Loading a portable scene does not populate or silently replace the library.
The original named inspector references remain separate from catalog rows.

## Measured sizes, November 19, 2026

| Selection | Rows received | Rows accepted | Decoded VOTable | Compressed local representation |
|---|---:|---:|---:|---:|
| Previous default V &lt; 8 query | 41,074 | 41,057 | 4,374,560 bytes | 1,002,210-byte NPZ demonstration, plus 630-byte metadata |
| Complete six-column main table | 118,218 | 117,955 | 12,573,101 bytes | 2,763,294-byte verified app snapshot |

These are measurements from the recorded query/serialization, not promises of
identical future byte counts. The compressed representations use different
formats; the full-library row uses the actual app's gzip/JSON cache. HTTP gzip
was enabled and no Content-Length was provided, so decoded response bytes
are not claimed as wire-transfer bytes. The raw full catalog has 263 rejected
rows because required coordinates or magnitudes are invalid; their row numbers
and reasons are retained. Optional B−V/distance nulls do not reject a row.

The Harvard mirror returned an XML database-connection error during the size
study; the South African mirror succeeded. The existing explicit HTTPS mirror
fallback remains available. A bad local snapshot or failed refresh leaves the
current scene usable; no automatic replacement with demo or partial data occurs.

Sources: [CDS I/239 description](https://cdsarc.cds.unistra.fr/viz-bin/ReadMe/I/239?format=html&tex=true)
and [Astroquery VizieR documentation](https://astroquery.readthedocs.io/en/stable/vizier/vizier.html).
