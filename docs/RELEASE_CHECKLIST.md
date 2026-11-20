# Local release preparation and publication boundary

The release build script creates local assets only. CI has read-only repository
permissions, tests pushes/PRs, and builds artifacts only on manual dispatch.
There is no release-publication job. None of the following publication actions
is performed by local preparation.

## Local evidence

The completion report records the actual results for unit/Qt checks, frozen
runtime startup and export tests, isolated install/launch/update/rollback,
shortcuts, integrity failures, package contents, license inventory, hashes, and
source state. Use that report rather than treating this checklist as proof.
Build logs retain any warnings and failed candidate evidence. The final asset
directory is identified in the report; earlier candidates are not release-ready.

Build with a separate Python 3.12.10 environment on Windows x64:

```powershell
python -m pip install -r packaging\requirements-runtime.lock -r packaging\requirements-build.lock
python -X utf8 packaging\build_release.py --output-dir dist\release --work-dir build\release
```

Both output/work directories must be new. The build pins the runtime, isolates
native DLL discovery from unrelated PATH tools, and supplies dependency notices.
The package manifest and SHA256SUMS identify the actual bytes. The source ZIP
must match the source fingerprint in the completion report. A locally prepared
version string does not mean that a Git tag or public release exists.

## Before a future publication

1. Review the complete local diff, scientific limitations, license notices,
   unsigned-binary status, clean-machine results, and release notes.
2. Commit the reviewed source locally. Create a local `v0.2.6` tag only after
   resolving the final source/release provenance.
3. The user pushes the reviewed source and tag. Wait for CI to pass on the
   actual pushed commit; local checks do not establish a GitHub Actions result.
4. Upload the exact named Windows ZIP/setup plus wheel/source/hashes to the
   GitHub release. Stable update discovery expects the documented asset names
   and GitHub-generated SHA-256 digests.
5. Test downloading from the actual published release on another Windows host,
   including offline launch, update, rollback, and independent figure export.

The user performs steps 3 and later. No branch push, tag creation/push, release
upload, release creation, or repository-setting change is done by the agent.

For **v0.2.6**, the required published Windows assets are:

- `relativistic-spaceship-viewer-0.2.6-windows-x64-setup.exe` for initial installs.
- `relativistic-spaceship-viewer-0.2.6-windows-x64.zip` for installed-app updates.

Also attach the reviewed wheel, exact source ZIP, release/source manifests,
runtime lock, release notes, and SHA256SUMS. Use the single final asset directory
identified in the handoff; do not mix older candidate folders. GitHub-generated
source archives alone are not the installer or managed-update package.
`dist/release` is intentionally ignored by Git, so pushing source does not upload
these files. Publish a stable release after attaching them; the updater ignores
drafts and prereleases. The user's existing local 0.2.6 will correctly offer no
update to the same version; later public updates require a higher version.

Upload `docs/branding/social-preview.png` separately in repository Settings →
Social preview. Its README reference does not set that repository setting.
