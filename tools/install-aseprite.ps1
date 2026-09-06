# Build Aseprite from source (GPL).
# Requires: Visual Studio 2022 with "Desktop development with C++", git, network.
#
# Optional env:
#   ASEPRITE_PREFIX  build/install root (default: %LOCALAPPDATA%\aseprite-build)
# Git, cmake and ninja come from PATH when present; otherwise cmake/ninja are
# downloaded under the prefix. vswhere is the standard VS installer copy.

$ErrorActionPreference = "Stop"
$Prefix = if ($env:ASEPRITE_PREFIX) { $env:ASEPRITE_PREFIX } else { Join-Path $env:LOCALAPPDATA "aseprite-build" }
$AsepriteRoot = Join-Path $Prefix "aseprite"
$Deps = Join-Path $Prefix "deps"
$SkiaDir = Join-Path $Deps "skia-m124"
$CmakeDir = Join-Path $Prefix "cmake"
$NinjaDir = Join-Path $Prefix "ninja"
$Ninja = Join-Path $NinjaDir "ninja.exe"

function Ensure-Dir($p) { if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null } }

function Resolve-Git {
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "git not found on PATH"
}

Ensure-Dir $Prefix
Ensure-Dir $Deps

$Git = Resolve-Git

# Portable CMake
if (-not (Test-Path (Join-Path $CmakeDir "bin\cmake.exe"))) {
    Write-Host "Downloading CMake..."
    $cmakeZip = Join-Path $env:TEMP "cmake-portable.zip"
    Invoke-WebRequest -Uri "https://github.com/Kitware/CMake/releases/download/v3.31.6/cmake-3.31.6-windows-x86_64.zip" -OutFile $cmakeZip
    Expand-Archive -Path $cmakeZip -DestinationPath $Prefix -Force
    $extracted = Get-ChildItem $Prefix -Directory | Where-Object { $_.Name -like "cmake-*-windows-x86_64" } | Select-Object -First 1
    if ($extracted -and -not (Test-Path $CmakeDir)) { Rename-Item $extracted.FullName $CmakeDir }
}

# Portable Ninja
if (-not (Test-Path $Ninja)) {
    Write-Host "Downloading Ninja..."
    Ensure-Dir $NinjaDir
    $ninjaZip = Join-Path $env:TEMP "ninja-win.zip"
    Invoke-WebRequest -Uri "https://github.com/ninja-build/ninja/releases/download/v1.12.1/ninja-win.zip" -OutFile $ninjaZip
    Expand-Archive -Path $ninjaZip -DestinationPath $NinjaDir -Force
}

$env:PATH = "$(Join-Path $CmakeDir 'bin');$NinjaDir;$env:PATH"

# Skia prebuilt
if (-not (Test-Path (Join-Path $SkiaDir "out\Release-x64\skia.lib"))) {
    Write-Host "Downloading Skia (Release x64)..."
    Ensure-Dir $SkiaDir
    $skiaZip = Join-Path $env:TEMP "Skia-Windows-Release-x64.zip"
    Invoke-WebRequest -Uri "https://github.com/aseprite/skia/releases/download/m124-08a5439a6b/Skia-Windows-Release-x64.zip" -OutFile $skiaZip
    Expand-Archive -Path $skiaZip -DestinationPath $SkiaDir -Force
}

# Aseprite source
if (-not (Test-Path (Join-Path $AsepriteRoot ".git"))) {
    Write-Host "Cloning Aseprite..."
    & $Git clone --recursive --depth 1 https://github.com/aseprite/aseprite.git $AsepriteRoot
} else {
    Push-Location $AsepriteRoot
    & $Git pull
    & $Git submodule update --init --recursive
    Pop-Location
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath = & $vswhere -latest -property installationPath
$vsDevCmd = Join-Path $vsPath "Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path $vsDevCmd)) { throw "VsDevCmd.bat not found" }

$buildDir = Join-Path $AsepriteRoot "build"
Ensure-Dir $buildDir

Write-Host "Configuring CMake..."
$cmakeArgs = @(
    "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
    "-DLAF_BACKEND=skia",
    "-DSKIA_DIR=$SkiaDir",
    "-DSKIA_LIBRARY_DIR=$(Join-Path $SkiaDir 'out\Release-x64')",
    "-DSKIA_LIBRARY=$(Join-Path $SkiaDir 'out\Release-x64\skia.lib')",
    "-G", "Ninja",
    ".."
)
cmd /c "`"$vsDevCmd`" -arch=x64 && cd /d `"$buildDir`" && cmake $($cmakeArgs -join ' ')"
if ($LASTEXITCODE -ne 0) { throw "cmake failed" }

Write-Host "Building Aseprite (this may take 15-30 min)..."
cmd /c "`"$vsDevCmd`" -arch=x64 && cd /d `"$buildDir`" && ninja aseprite"
if ($LASTEXITCODE -ne 0) { throw "ninja failed" }

$built = Join-Path $buildDir "bin\aseprite.exe"
$installDir = Join-Path $Prefix "Aseprite"
Ensure-Dir $installDir
Copy-Item $built $installDir -Force
Write-Host "Installed: $(Join-Path $installDir 'aseprite.exe')"
& (Join-Path $installDir "aseprite.exe") --version
