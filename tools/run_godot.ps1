# Run saboteur-92 in Godot (debug).
# Resolve Godot from GODOT_PATH, then GODOT, then `godot` on PATH.
# Project root is the parent of this script (tools/).
$ErrorActionPreference = "Stop"
$Project = Split-Path $PSScriptRoot -Parent

function Resolve-Godot {
    param([switch]$Console)
    $candidates = @()
    if ($env:GODOT_PATH) { $candidates += $env:GODOT_PATH }
    if ($env:GODOT) { $candidates += $env:GODOT }
    $cmd = Get-Command godot -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    foreach ($path in $candidates) {
        if (-not $path) { continue }
        if (-not (Test-Path $path)) { continue }
        if ($Console) {
            $consolePath = $path -replace '\.exe$', '_console.exe'
            if ($consolePath -ne $path -and (Test-Path $consolePath)) {
                return $consolePath
            }
        }
        return $path
    }
    throw "Godot 4.6 not found. Set GODOT_PATH to the 4.6.stable editor binary, or put godot on PATH."
}

$headless = $args.Count -gt 0 -and $args[0] -eq "headless"
$Godot = Resolve-Godot -Console:$headless
if ($headless) {
    & $Godot --path $Project --headless --quit-after 5
} else {
    & $Godot --path $Project -d
}
