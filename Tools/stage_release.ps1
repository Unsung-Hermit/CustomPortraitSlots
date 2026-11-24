# Stage a Nexus/distribution tree under dist\CustomPortraitSlots\
# (normal end-user files only: Guide.html, bats, exes, .py sources, templates, repak).
# Excludes: root README, Tools\README, freeze_exes.ps1, tests, make_placeholder, _pyi_build, out, MergeInbox packs.
# Requires: freeze exes already built in Tools\.
$ErrorActionPreference = "Stop"
$Tools = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Tools
$DistRoot = Join-Path $Root "dist"
$Stage = Join-Path $DistRoot "CustomPortraitSlots"

function Copy-FileTo([string]$Src, [string]$DestDir) {
    if (-not (Test-Path -LiteralPath $Src)) {
        throw "Missing required file: $Src"
    }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    Copy-Item -LiteralPath $Src -Destination (Join-Path $DestDir (Split-Path -Leaf $Src)) -Force
}

Write-Host "Staging -> $Stage"
if (Test-Path -LiteralPath $DistRoot) {
    Remove-Item -LiteralPath $DistRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

# Root (no README.md)
Copy-FileTo (Join-Path $Root "Guide.html") $Stage
Copy-FileTo (Join-Path $Root "generate_slot.bat") $Stage
Copy-FileTo (Join-Path $Root "merge_slots.bat") $Stage

# MergeInbox instructions only
$MergeDest = Join-Path $Stage "MergeInbox"
New-Item -ItemType Directory -Force -Path $MergeDest | Out-Null
Copy-FileTo (Join-Path $Root "MergeInbox\README.md") $MergeDest

# Tools — runtime + quarantine sources
$ToolsDest = Join-Path $Stage "Tools"
$toolFiles = @(
    "bake_portrait.exe",
    "bake_portrait.py",
    "generate_slot.exe",
    "generate_slot.py",
    "merge_slots.exe",
    "merge_slots.py",
    "registry_writer.py",
    "uasset_rename.py",
    "repak.exe",
    "repak_LICENSE-MIT.txt",
    "repak_LICENSE-APACHE.txt",
    "THIRD_PARTY_NOTICES.md"
)
foreach ($name in $toolFiles) {
    Copy-FileTo (Join-Path $Tools $name) $ToolsDest
}

# Icon
$AssetsSrc = Join-Path $Tools "assets\Icon128.png"
$AssetsDest = Join-Path $ToolsDest "assets"
Copy-FileTo $AssetsSrc $AssetsDest

# Templates
$TemplatesSrc = Join-Path $Tools "templates"
$TemplatesDest = Join-Path $ToolsDest "templates"
if (-not (Test-Path -LiteralPath $TemplatesSrc)) {
    throw "Missing templates: $TemplatesSrc"
}
New-Item -ItemType Directory -Force -Path $TemplatesDest | Out-Null
Copy-Item -Path (Join-Path $TemplatesSrc "*") -Destination $TemplatesDest -Recurse -Force
Get-ChildItem -LiteralPath $TemplatesDest -Directory -Filter "_*" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
Get-ChildItem -LiteralPath $TemplatesDest -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
Write-Host "Done. Tree:"
Get-ChildItem -LiteralPath $Stage -Recurse -File |
    ForEach-Object { $_.FullName.Substring($Stage.Length + 1) } |
    Sort-Object
Write-Host ""
Write-Host "Zip this folder for Nexus: $Stage"
Write-Host "(Tracked in git for quarantine parity; *.zip stays gitignored.)"
Write-Host "(Example) Compress-Archive -Path `"$Stage`" -DestinationPath (Join-Path $DistRoot 'CustomPortraitSlots.zip')"
Write-Host "(ZIP top-level folder: CustomPortraitSlots\ — same layout as CustomPortraitKit.zip)"
