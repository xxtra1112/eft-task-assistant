param(
    [ValidatePattern('^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')]
    [string]$Version = "1.3.0",
    [string]$SourceCommit,
    [string]$Tag,
    [switch]$DiagnosticOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildRoot = Join-Path $projectRoot "build\pyinstaller"
$distRoot = Join-Path $projectRoot "dist\v$Version"
$packager = Join-Path $projectRoot "pack_release.py"

Push-Location $projectRoot
try {
    if (-not $SourceCommit) {
        $SourceCommit = & git rev-parse HEAD
        if ($LASTEXITCODE -ne 0) { throw "Cannot determine checkout HEAD." }
    }
    $validation = @("-B", $packager, "--root", $projectRoot, "--version", $Version, "--source-commit", $SourceCommit)
    if ($Tag) { $validation += @("--tag", $Tag) }
    & python @validation --check-only
    if ($LASTEXITCODE -ne 0) { throw "Release input validation failed. Commit the final source and use the locked Python environment." }
    & python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Installed dependencies failed pip check." }
    if ($DiagnosticOnly) { return }
    if (Test-Path -LiteralPath $distRoot) { throw "Output directory already exists: $distRoot. Use a fresh checkout or remove only its previous build outputs." }

    New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
    $licensesFile = Join-Path $buildRoot "THIRD_PARTY_LICENSES.txt"
    & python @validation --licenses-output $licensesFile
    if ($LASTEXITCODE -ne 0) { throw "Required third-party license texts could not be collected from the locked environment." }
    $versionFile = Join-Path $buildRoot "windows-version.txt"
    $versionTuple = ($Version.Split('.') + @('0')) -join ', '
    @"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($versionTuple), prodvers=($versionTuple), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [StringStruct('FileVersion', '$Version'), StringStruct('ProductVersion', '$Version'), StringStruct('ProductName', 'EFT Task Assistant')])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"@ | Set-Content -LiteralPath $versionFile -Encoding utf8
    $arguments = @(
        "-B", "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "EFTTaskAssistant",
        "--distpath", (Join-Path $buildRoot "dist"),
        "--workpath", (Join-Path $buildRoot "work"),
        "--specpath", $buildRoot,
        "--version-file", $versionFile,
        "--add-data", "$(Join-Path $projectRoot 'release_version.json');.",
        "--add-data", "$(Join-Path $projectRoot 'LICENSE');.",
        "--add-data", "$(Join-Path $projectRoot 'THIRD_PARTY_NOTICES.md');.",
        "--add-data", "$licensesFile;.",
        "--collect-all", "rapidocr_onnxruntime",
        "--collect-all", "cv2"
    )
    $webFiles = & python -B -c "from pack_release import WEB_FILES; print('\n'.join(WEB_FILES))"
    if ($LASTEXITCODE -ne 0) { throw "Cannot load the web asset allowlist." }
    foreach ($file in $webFiles) {
        $arguments += @("--add-data", "$(Join-Path $projectRoot "web\$file");web")
    }
    $arguments += (Join-Path $projectRoot "main.py")
    & python @arguments
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
    $builtExecutable = Join-Path $buildRoot "dist\EFTTaskAssistant.exe"
    & python @validation --exe $builtExecutable --output-dir $distRoot --licenses-output $licensesFile
    if ($LASTEXITCODE -ne 0) { throw "Portable release packaging failed." }
    Get-Content -LiteralPath (Join-Path $distRoot "SHA256SUMS.txt")
}
finally {
    Pop-Location
}
