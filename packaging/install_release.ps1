param([string]$LocalSetup)
$ErrorActionPreference = 'Stop'
$repo = 'Fisicas/relativistic-spaceship-viewer'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $LocalSetup) {
    $localFolder = Join-Path $projectRoot 'dist\release'
    if (Test-Path -LiteralPath $localFolder) {
        $candidate = Get-ChildItem -LiteralPath $localFolder -Filter '*-windows-x64-setup.exe' |
            Where-Object { $_.Name -match '^relativistic-spaceship-viewer-(\d+\.\d+\.\d+)-windows-x64-setup\.exe$' } |
            Sort-Object { [version]([regex]::Match($_.Name, '\d+\.\d+\.\d+').Value) } -Descending |
            Select-Object -First 1
        if ($candidate) { $LocalSetup = $candidate.FullName }
    }
}
if ($LocalSetup) {
    $setup = Get-Item -LiteralPath $LocalSetup
    if ($setup.Name -notmatch '^relativistic-spaceship-viewer-\d+\.\d+\.\d+-windows-x64-setup\.exe$') {
        throw 'The selected local file is not a viewer setup package.'
    }
    $manifestPath = Join-Path $setup.DirectoryName 'release_manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Local release_manifest.json is required.' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $entry = $manifest.artifacts.PSObject.Properties[$setup.Name].Value
    if (-not $entry -or (Get-FileHash -LiteralPath $setup.FullName -Algorithm SHA256).Hash.ToLower() -ne $entry.sha256) {
        throw 'Local setup hash does not match its prepared release manifest.'
    }
    $setupProcess = Start-Process -FilePath $setup.FullName -WindowStyle Hidden -Wait -PassThru
    exit $setupProcess.ExitCode
}
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" -Headers @{ Accept='application/vnd.github+json'; 'User-Agent'='RelativisticSpaceshipViewer' }
} catch {
    throw 'No downloadable stable Windows release was found. For an unpublished local build, use its prepared setup EXE or pass -LocalSetup.'
}
if ($release.draft -or $release.prerelease -or $release.tag_name -notmatch '^v(\d+\.\d+\.\d+)$') { throw 'A stable release tag is required.' }
$releaseVersion = $Matches[1]
$name = "relativistic-spaceship-viewer-$releaseVersion-windows-x64-setup.exe"
$assets = @($release.assets | Where-Object { $_.name -eq $name })
if ($assets.Count -ne 1) { throw 'This release has no unique Windows setup asset.' }
$asset = $assets[0]
$expectedUrl = "https://github.com/$repo/releases/download/v$releaseVersion/$name"
if ($asset.browser_download_url -ne $expectedUrl -or $asset.digest -notmatch '^sha256:([0-9a-f]{64})$') { throw 'Invalid setup URL or missing GitHub asset digest.' }
$expectedHash = $Matches[1]
if ($asset.size -le 0 -or $asset.size -gt 734003200) { throw 'Invalid setup asset size.' }
$downloadDirectory = Join-Path ([IO.Path]::GetTempPath()) ('rsv-setup-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $downloadDirectory | Out-Null
$downloadPath = Join-Path $downloadDirectory $name
Invoke-WebRequest -Uri $expectedUrl -OutFile $downloadPath -UseBasicParsing
if ((Get-Item -LiteralPath $downloadPath).Length -ne $asset.size -or (Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLower() -ne $expectedHash) {
    throw 'Downloaded setup failed its size or SHA-256 check.'
}
$setupProcess = Start-Process -FilePath $downloadPath -WindowStyle Hidden -Wait -PassThru
exit $setupProcess.ExitCode
