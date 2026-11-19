# Changelog

## 0.2.5 — unpublished charcoal cockpit and local catalog library, 2026-11-19

- Use neutral charcoal/gray chrome and plot annotations, preserving scientific
  RGB calculations. Adopt the selected angular-window logo as an inspectable
  SVG, Windows icon, and real-sky README/social-preview artwork.
- Add a thin viewport bezel, a long synchronized speed slider, and responsive
  side readouts in wide focused views. Retain equal angular scales and 16:9 FOV.
- Ask for demo/local Hipparcos on first launch, optionally remember the choice,
  and store a verified local processed snapshot. Download the complete six-column
  main table once; filter V locally. Preserve prior snapshots and catalog values.
- Add cache-integrity, full-query, offline startup, cockpit, frozen, and installer
  checks. Keep the original 33 named targets plus Sol. No GitHub publication.

## 0.2.4 — unpublished Doppler solar radiometry, 2026-11-19

- Add per-ray uniform 5772 K blackbody spectra and CIE visible surface radiance
  while preserving the finite solar silhouette and occultation geometry.
- Add fixed display exposure, a one-time exposure fit, and an optional geometry
  outline. Keep these separate from physical radiance, camera, and FOV.
- Bundle checksummed original CIE data, attribution, and CC BY-SA 4.0 license;
  extend numeric exports and provenance to spectral and display results.
- Preserve neutral fill and provenance when loading 0.2.3 solar scenes. Keep
  the 33 named targets plus Sol. Add scrolling for compact solar controls.
- Add spectral/bolometric identities, per-ray gradients, LUT accuracy, geometry
  invariance, saved-scene, Qt, frozen, and export checks. No publication.

## 0.2.3 — unpublished fixed-1-AU Sol model, 2026-11-19

- Add Sol after the original 33 targets, with editable teaching direction,
  finite solar silhouette, angular-size/solid-angle/Doppler readouts, independent
  camera tracking, framing, and explicit toward/away/transverse headings.
- Model the aberrated spherical cap and distant-background ray occultation;
  preserve model constants, geometry, limb rays, and masks in scenes/exports.
- Extend zoom to 0.001°; keep point-star marker proxies separate from solar
  geometry. Add analytic, quadrature, GUI, replay, and frozen-rendering checks.

## 0.2.2 — unpublished named-target picker fix, 2026-11-19

- Keep the original 33 named targets in the inspector dropdown when Hipparcos
  or another catalog is loaded; retain click inspection of all plotted sources.
- Preserve reference coordinates/provenance separately from catalog rows and
  embed reference selections in portable scenes/exports. Add a labeled cross
  as a navigation annotation without changing scientific counts or arrays.
- Keep camera-only selection, explicit custom steering, and 16:9 behavior.

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
