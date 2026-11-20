# Install, update, and restore a Windows build

## Local prepared release

Run the prepared `relativistic-spaceship-viewer-0.2.6-windows-x64-setup.exe`.
It installs for the current Windows user; administrator rights, Python, and Git
are not required. The default location is:

```text
%LOCALAPPDATA%\Programs\RelativisticSpaceshipViewer
```

Keep this default or another short per-user path. Deeply nested custom install
or extraction folders can exceed Windows native-extension path limits and make
PDF/fontTools loading fail. A failed staged self-test leaves the current version
active. This is a path-length limitation; changing system-wide policies is not
required or performed by the installer.

A Start menu shortcut points to the stable `ViewerLauncher.exe`. The launcher
selects the active version, rather than linking a shortcut to a temporary build
folder. Launching again restores the already-running viewer. The installer also
registers an entry in the current user's Installed apps list. Close the viewer
before reinstalling, repairing, or uninstalling it.

The source checkout includes `Install_Viewer.cmd`. It first looks for a prepared
setup in `dist\release`; otherwise it looks for the latest published stable
release on GitHub. The bootstrap verifies the setup against the local manifest
or GitHub's asset SHA-256 digest before running it. It does not pull `main` or
install dependencies into a shared Python environment. PowerShell execution
policy is respected; if that prevents the script, run the prepared setup EXE.
Before a release is published, the online bootstrap has no new release to fetch.

Pushing source commits to GitHub does not distribute an application update.
The repository owner must publish a stable **v0.2.6** release with the exact
setup and Windows ZIP assets. For later updates, use a higher version and a
matching stable tag/asset name. A release marked draft or prerelease is not
offered by this updater. CI checks source pushes and can build downloadable
workflow artifacts on manual dispatch; it does not publish GitHub releases.

## Updates

The installed app checks GitHub stable releases at startup by default, without
blocking the UI. **Application → Check for updates** performs a manual check.
The startup check can be disabled in the same menu. An available release is
shown as a status-bar button; downloading and installation require choosing
the update action. The viewer does not replace itself in mid-session.

Downloaded packages must come from the exact project release URL, use a stable
`vMAJOR.MINOR.PATCH` tag, and include GitHub's SHA-256 asset digest. The package's
file manifest is then verified, and the new executable runs an offline
startup/physics/export test. Only a passing build can be queued. After the viewer
closes and releases its running lock, the stable helper atomically changes the
active pointer. The next launch uses the new version. Offline checks and failed
downloads leave the current installation available.

Managed updates replace the versioned runtime; the small stable launcher stays
in place. A future change to the deployment protocol or launcher requires a new
setup installation. Protocol-mismatched packages are rejected.

Code, settings/cache, and scientific outputs are separate. Settings/cache use
`%LOCALAPPDATA%\RelativisticSpaceshipViewer`; choose a Documents/project folder
for saved scenes and exports. Installation and rollback do not rewrite them.
The launcher starts in the data folder, not inside an immutable version folder.

## Rollback

**Application → Roll back previous installed build** queues the previous healthy
slot. Close the viewer to activate it. The stable launcher also accepts:

```powershell
& "$env:LOCALAPPDATA\Programs\RelativisticSpaceshipViewer\ViewerLauncher.exe" --rollback
```

Rollback requires an earlier installed build. The first installation has none.
Old version folders are retained automatically; no user files are recursively
removed during updates. Uninstall removes files listed as application-owned and
preserves user-added files, scenes, exports, and the separate data folder.

## Portable build

Extract the Windows ZIP into a new folder and launch
`RelativisticSpaceshipViewer.exe`. The ZIP includes Python, Qt, scientific
libraries, optional VizieR dependencies, source fingerprints, and license notices.
Portable/source launches do not enable managed automatic installation. Use setup
for version slots, shortcuts, and rollback.

## Distribution limits

These local binaries are unsigned. A clean second Windows machine, actual
multi-monitor DPI transitions, and a publicly hosted update have not been
verified by local package tests. The updater's HTTP behavior and integrity
failure handling are tested with controlled fixtures; publishing is a separate
action. The inherited catalog and illustrative photometry remain scientifically
uncalibrated; installation checks do not change that scope.
