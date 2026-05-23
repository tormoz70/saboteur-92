# Run saboteur-92 in Godot (debug)
$Godot = "C:\data\apps\Godot_v4.6.2-stable_win64\Godot_v4.6.2-stable_win64.exe"
$Project = Split-Path $PSScriptRoot -Parent
if ($args.Count -gt 0 -and $args[0] -eq "headless") {
    & "C:\data\apps\Godot_v4.6.2-stable_win64\Godot_v4.6.2-stable_win64_console.exe" --path $Project --headless --quit-after 5
} else {
    & $Godot --path $Project -d
}
