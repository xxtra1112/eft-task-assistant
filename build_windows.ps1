param(
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version = "1.1.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildRoot = Join-Path $projectRoot "build\pyinstaller"
$distRoot = Join-Path $projectRoot "dist"
$pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"

if ($LASTEXITCODE -ne 0) {
    throw "Python was not found. Activate the eft-task-assistant Conda environment first."
}
if ($pythonVersion -ne "3.11") {
    throw "Python 3.11 is required; the active interpreter is Python $pythonVersion."
}
if (-not (Test-Path (Join-Path $projectRoot "web\index.html"))) {
    throw "The web UI files are missing from the project."
}

New-Item -ItemType Directory -Force -Path $buildRoot, $distRoot | Out-Null
$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--console",
    "--name", "EFTTaskAssistant",
    "--distpath", $distRoot,
    "--workpath", (Join-Path $buildRoot "work"),
    "--specpath", $buildRoot,
    "--add-data", "$(Join-Path $projectRoot 'web');web",
    "--add-data", "$(Join-Path $projectRoot 'LICENSE');.",
    "--add-data", "$(Join-Path $projectRoot 'THIRD_PARTY_NOTICES.md');.",
    "--collect-all", "rapidocr_onnxruntime",
    "--collect-all", "cv2",
    (Join-Path $projectRoot "main.py")
)

Push-Location $projectRoot
try {
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $builtExecutable = Join-Path $distRoot "EFTTaskAssistant.exe"
    if (-not (Test-Path $builtExecutable)) {
        throw "PyInstaller completed without producing EFTTaskAssistant.exe."
    }
    $releaseExecutable = Join-Path $distRoot "EFTTaskAssistant-v$Version-Windows-x64.exe"
    Copy-Item -LiteralPath $builtExecutable -Destination $releaseExecutable -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination (Join-Path $distRoot "LICENSE.txt") -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") -Destination $distRoot -Force
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseExecutable).Hash
    $size = (Get-Item -LiteralPath $releaseExecutable).Length
    Write-Output "Built: $releaseExecutable"
    Write-Output "Size: $size bytes"
    Write-Output "SHA256: $hash"
}
finally {
    Pop-Location
}
