# Build Aseprite from source (GPL) and install to C:\data\apps\Aseprite
# Requires: Visual Studio 2022 with "Desktop development with C++", git, network

$ErrorActionPreference = "Stop"
$Apps = "C:\data\apps"
$AsepriteRoot = "$Apps\aseprite"
$Deps = "$Apps\deps"
$SkiaDir = "$Deps\skia-m124"
$CmakeDir = "$Apps\cmake"
$Ninja = "$Apps\ninja\ninja.exe"

function Ensure-Dir($p) { if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null } }

Ensure-Dir $Apps
Ensure-Dir $Deps

# Portable CMake
if (-not (Test-Path "$CmakeDir\bin\cmake.exe")) {
    Write-Host "Downloading CMake..."
    $cmakeZip = "$env:TEMP\cmake-portable.zip"
    Invoke-WebRequest -Uri "https://github.com/Kitware/CMake/releases/download/v3.31.6/cmake-3.31.6-windows-x86_64.zip" -OutFile $cmakeZip
    Expand-Archive -Path $cmakeZip -DestinationPath $Apps -Force
    $extracted = Get-ChildItem "$Apps" -Directory | Where-Object { $_.Name -like "cmake-*-windows-x86_64" } | Select-Object -First 1
    if ($extracted -and -not (Test-Path $CmakeDir)) { Rename-Item $extracted.FullName $CmakeDir }
}

# Portable Ninja
if (-not (Test-Path $Ninja)) {
    Write-Host "Downloading Ninja..."
    Ensure-Dir "$Apps\ninja"
    $ninjaZip = "$env:TEMP\ninja-win.zip"
    Invoke-WebRequest -Uri "https://github.com/ninja-build/ninja/releases/download/v1.12.1/ninja-win.zip" -OutFile $ninjaZip
    Expand-Archive -Path $ninjaZip -DestinationPath "$Apps\ninja" -Force
}

$env:PATH = "$CmakeDir\bin;$Apps\ninja;$env:PATH"

# Skia prebuilt
if (-not (Test-Path "$SkiaDir\out\Release-x64\skia.lib")) {
    Write-Host "Downloading Skia (Release x64)..."
    Ensure-Dir $SkiaDir
    $skiaZip = "$env:TEMP\Skia-Windows-Release-x64.zip"
    Invoke-WebRequest -Uri "https://github.com/aseprite/skia/releases/download/m124-08a5439a6b/Skia-Windows-Release-x64.zip" -OutFile $skiaZip
    Expand-Archive -Path $skiaZip -DestinationPath $SkiaDir -Force
}

# Aseprite source
if (-not (Test-Path "$AsepriteRoot\.git")) {
    Write-Host "Cloning Aseprite..."
    & "C:\data\apps\git\bin\git.exe" clone --recursive --depth 1 https://github.com/aseprite/aseprite.git $AsepriteRoot
} else {
    Push-Location $AsepriteRoot
    & "C:\data\apps\git\bin\git.exe" pull
    & "C:\data\apps\git\bin\git.exe" submodule update --init --recursive
    Pop-Location
}

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath = & $vswhere -latest -property installationPath
$vsDevCmd = Join-Path $vsPath "Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path $vsDevCmd)) { throw "VsDevCmd.bat not found" }

$buildDir = "$AsepriteRoot\build"
Ensure-Dir $buildDir

Write-Host "Configuring CMake..."
$cmakeArgs = @(
    "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
    "-DLAF_BACKEND=skia",
    "-DSKIA_DIR=$SkiaDir",
    "-DSKIA_LIBRARY_DIR=$SkiaDir\out\Release-x64",
    "-DSKIA_LIBRARY=$SkiaDir\out\Release-x64\skia.lib",
    "-G", "Ninja",
    ".."
)
cmd /c "`"$vsDevCmd`" -arch=x64 && cd /d `"$buildDir`" && cmake $($cmakeArgs -join ' ')"
if ($LASTEXITCODE -ne 0) { throw "cmake failed" }

Write-Host "Building Aseprite (this may take 15-30 min)..."
cmd /c "`"$vsDevCmd`" -arch=x64 && cd /d `"$buildDir`" && ninja aseprite"
if ($LASTEXITCODE -ne 0) { throw "ninja failed" }

$built = "$buildDir\bin\aseprite.exe"
$installDir = "$Apps\Aseprite"
Ensure-Dir $installDir
Copy-Item $built $installDir -Force
Write-Host "Installed: $installDir\aseprite.exe"
& "$installDir\aseprite.exe" --version
