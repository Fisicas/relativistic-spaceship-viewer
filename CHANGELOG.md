# Changelog

## 0.2.1 — unpublished local interaction/service patch, 2026-11-19

- Center inspector selections on their apparent direction without changing
  velocity; name the custom heading after the selected object and steer only
  when that heading is chosen. Preserve the three fixed heading presets.
- Add a 16:9 focus viewport with recomputed visibility, equal angular scales,
  ratio-preserving zoom, and restoration of the previous field of view.
- Recover Hipparcos retrieval through CDS-listed HTTPS mirrors with bounded
  timeouts and endpoint provenance; preserve catalog values and import rules.
- Make rejected-row indices JSON serializable when real Hipparcos rows have
  invalid required coordinates or magnitudes.
- Add regression, Qt, frozen, and explicit live-service verification tools.

## 0.2.0 — unpublished local release candidate, 2026-11-19

- Add an unsigned, self-contained per-user Windows setup and portable package,
  a stable Start menu launcher, current-user Installed apps registration, and
  removal that preserves user-added files and separate app data.
- Add stable GitHub release discovery, explicit download/install actions,
  SHA-256 and file-manifest checks, offline staged-runtime tests, activation
  after app closure, and previous-build rollback.
- Add deployment failure tests, actual frozen-runtime and isolated installer
  verification tools, pinned private build dependencies, bundled dependency
  notices, and read-only CI with local artifact builds on manual dispatch.
- Keep the physics core and scientific conventions from the preceding stages.
  No GitHub push, remote tag, release creation, or upload is performed.

## 0.2.0.dev2 — local UI and export milestone, 2026-11-19

- Make the Qt desktop interface the default; preserve the Tk launch option.
- Add precise beta/gamma entry, rapidity control, adjustable FOV, synchronized
  rest/moving comparison, focus mode, keyboard navigation, and object inspection.
- Add deterministic label collision avoidance with a bounded candidate budget.
- Add portable JSON sessions containing full catalog and exact camera snapshots.
- Add versioned PNG/SVG/PDF exports, derived NPZ arrays, artifact/catalog hashes,
  runtime/source fingerprints, and a reproduction verifier.
- Regenerate square 4K Orion examples and a landscape 4K comparison from the
  numerical model. Preserve original JPEGs and add controlled Qt screenshots.
- Keep late catalog fetches from replacing a newer scene/catalog selection.
- Leave installation, automatic updates, and publication for later work.

## 0.2.0.dev1 — local physics foundation, 2026-11-19

- Split catalog, geometry, relativity, application state, scene calculation,
  illustrative display, rendering, and Tk UI into modules.
- Retain the original launch command and inherited numerical demo values.
- Add explicit input validation, independent camera/velocity state, continuous
  camera triads through poles, import reports, explicit CSV units, and geometric
  parallax conversion. Keep unknown optional catalog values as NaN.
- Preserve masked Hipparcos values and record frame/epoch/query metadata.
- Keep fetch callbacks on the Tk main thread and preserve the catalog on errors.
- Clarify Doppler signs, projection, magnitude filtering, missing-value display
  defaults, M42's placeholder, and the uncalibrated RGB/D^3 marker mapping.
- Add fixed legacy scene references and analytic/independent numerical tests.
- Original JPEGs, public main, releases, installation, and update workflows are
  unchanged by this local milestone.
