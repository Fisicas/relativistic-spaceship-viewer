@echo off
setlocal
rem Uses a locally prepared setup when present, otherwise the latest published
rem stable Windows release. It does not pull main or change a Python environment.
powershell.exe -NoLogo -NoProfile -File "%~dp0packaging\install_release.ps1" %*
if errorlevel 1 pause
