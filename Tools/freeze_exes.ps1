# Build bake_portrait.exe, generate_slot.exe, and merge_slots.exe with PyInstaller.
# Requires: pip install pyinstaller pillow etcpak
$ErrorActionPreference = "Stop"
$Tools = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Tools

$PyiBuild = Join-Path $Tools "_pyi_build"

Write-Host "=== bake_portrait.exe ==="
python -m PyInstaller --noconfirm --clean --onefile `
    --name bake_portrait `
    --distpath $Tools `
    --workpath (Join-Path $PyiBuild "work_bake") `
    --specpath $PyiBuild `
    --collect-all etcpak `
    --collect-all archspec `
    --hidden-import PIL `
    --hidden-import PIL.Image `
    --hidden-import PIL.ImageOps `
    --hidden-import PIL.ImageFile `
    ".\bake_portrait.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== generate_slot.exe ==="
python -m PyInstaller --noconfirm --clean --onefile `
    --name generate_slot `
    --distpath $Tools `
    --workpath (Join-Path $PyiBuild "work_gen") `
    --specpath $PyiBuild `
    --hidden-import registry_writer `
    --hidden-import uasset_rename `
    ".\generate_slot.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== merge_slots.exe ==="
python -m PyInstaller --noconfirm --clean --onefile `
    --name merge_slots `
    --distpath $Tools `
    --workpath (Join-Path $PyiBuild "work_merge") `
    --specpath $PyiBuild `
    --collect-all etcpak `
    --collect-all archspec `
    --hidden-import PIL `
    --hidden-import PIL.Image `
    --hidden-import PIL.ImageOps `
    --hidden-import PIL.ImageFile `
    --hidden-import bake_portrait `
    --hidden-import generate_slot `
    --hidden-import registry_writer `
    --hidden-import uasset_rename `
    ".\merge_slots.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Done."
Get-Item -LiteralPath ".\bake_portrait.exe", ".\generate_slot.exe", ".\merge_slots.exe" |
    Select-Object Name, Length, LastWriteTime
