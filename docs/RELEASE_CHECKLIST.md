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
2. Commit the reviewed source locally. Create a local `v0.2.1` tag only after
   resolving the final source/release provenance.
3. With separate user authorization, push the branch/tag and allow CI to run.
4. Upload the exact named Windows ZIP/setup plus wheel/source/hashes to the
   GitHub release. Stable update discovery expects the documented asset names
   and GitHub-generated SHA-256 digests.
5. Test downloading from the actual published release on another Windows host,
   including offline launch, update, rollback, and independent figure export.

Step 3 and later are outside the current authorization. No pushes, tags on the
remote, release uploads, or release creation are done in this task.
