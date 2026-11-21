#!/usr/bin/env python3
"""Generate a single CustomPortraitSlots mod folder from cooked sex templates.

Usage:
  generate_slot.bat <Id> -Sex Female|Male|Nonbinary [-Force] [-OutDir path]
  python generate_slot.py <Id> --sex Female [--force] [--outdir path]

Writes out/CPS_<Id>/ with renamed cooked assets, AssetRegistry.bin, Tags ini,
target.json, and bake tools. No pak is created until bake_portrait runs.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import registry_writer as rw
import uasset_rename as ua

if getattr(sys, "frozen", False):
    TOOLS = Path(sys.executable).resolve().parent
else:
    TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
TEMPLATES = TOOLS / "templates"
TEMPLATES_JSON = TEMPLATES / "templates.json"
DEFAULT_OUT = ROOT / "out"
ICON_SRC = TOOLS / "assets" / "Icon128.png"

SEXES = ("Female", "Male", "Nonbinary")
GAME_VERSION = "1.15.399"
DEFAULT_LOAD_ORDER = 20
LAYOUT_NAME = "CPS_DXT5_512"
CONTENT_TEX_DIR = "UI/Textures/Pilots"

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
RESERVED_IDS = {"cps", "cpspack"}
WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

BAKE_BAT = """@echo off
setlocal
cd /d "%~dp0"
set "RC=1"

if exist "Resources\\portrait.png" goto find_baker
if exist "Resources\\portrait.jpg" goto find_baker
if exist "Resources\\portrait.jpeg" goto find_baker
echo ERROR: Resources\\portrait.png / portrait.jpg / portrait.jpeg not found.
echo Put your image in the Resources folder as portrait.png, portrait.jpg, or portrait.jpeg, then run this again.
goto end

:find_baker
if not exist "Tools\\bake_portrait.exe" goto try_py
"Tools\\bake_portrait.exe"
set "RC=%ERRORLEVEL%"
goto end

:try_py
if not exist "Tools\\bake_portrait.py" goto no_baker
python "Tools\\bake_portrait.py"
set "RC=%ERRORLEVEL%"
goto end

:no_baker
echo ERROR: Tools\\bake_portrait.exe / bake_portrait.py not found. Regenerate this slot.

:end
echo.
pause
exit /b %RC%
"""

INPUT_INI = """; Placeholder input config for MW5 mod pak layout
[/Script/Engine.InputSettings]
"""

TAGS_INI = """[/Script/GameplayTags.GameplayTagsList]
GameplayTagList=(Tag="Portrait.CPS",DevComment="")
"""


def validate_id(slot_id: str) -> None:
    if not ID_RE.match(slot_id):
        raise ValueError(
            f"Invalid Id {slot_id!r}: must be 1-32 chars, start with A-Z/a-z, "
            "and contain only A-Za-z0-9_ (no hyphens)."
        )
    lower = slot_id.lower()
    if lower in RESERVED_IDS:
        raise ValueError(f"Id {slot_id!r} is reserved")
    if lower.startswith("cpst_"):
        raise ValueError(f"Id {slot_id!r} collides with template asset prefix CPST_")
    if lower in WINDOWS_RESERVED:
        raise ValueError(f"Id {slot_id!r} is a reserved Windows device name")


def template_display_name(sex: str) -> str:
    return f"CPS Template {sex}"


def build_name_replacements(
    sex: str, plugin: str, texture: str, portrait: str, persona: str
) -> dict[str, str]:
    tpl_plugin = f"CPSTemplate_{sex}"
    tpl_tex = "CPST_Tex"
    tpl_portrait = f"CPST_Portrait_{sex}"
    tpl_persona = f"CPST_Persona_{sex}"
    return {
        f"/{tpl_plugin}/UI/Textures/Pilots/{tpl_tex}.{tpl_tex}": (
            f"/{plugin}/{CONTENT_TEX_DIR}/{texture}.{texture}"
        ),
        f"/{tpl_plugin}/UI/Textures/Pilots/{tpl_tex}": (
            f"/{plugin}/{CONTENT_TEX_DIR}/{texture}"
        ),
        f"/{tpl_plugin}/{tpl_portrait}": f"/{plugin}/{portrait}",
        f"/{tpl_plugin}/{tpl_persona}": f"/{plugin}/{persona}",
        tpl_portrait: portrait,
        tpl_persona: persona,
        tpl_tex: texture,
    }


def rewrite_registry(
    model: dict[str, Any],
    *,
    plugin: str,
    texture: str,
    portrait: str,
    persona: str,
) -> dict[str, Any]:
    out = {
        "Header": model["Header"],
        "Unknown": model["Unknown"],
        "fAssetDatas": [],
        "keyValuePairs": {},
    }
    for entry in model["fAssetDatas"]:
        asset_class = entry["AssetClass"]
        new_entry = {
            "TagAndValue": [dict(t) for t in entry["TagAndValue"]],
            "ChunkIDs": list(entry["ChunkIDs"]),
            "PackageTags": entry["PackageTags"],
            "AssetClass": asset_class,
        }
        if asset_class == "MWPersonaAsset":
            new_entry["AssetName"] = persona
            new_entry["PackagePath"] = f"/{plugin}"
            new_entry["PackageName"] = f"/{plugin}/{persona}"
            new_entry["ObjectPath"] = f"/{plugin}/{persona}.{persona}"
            for tag in new_entry["TagAndValue"]:
                if tag["Item1"] == "PrimaryAssetName":
                    tag["Item2"] = persona
        elif asset_class == "MWPortraitAsset":
            new_entry["AssetName"] = portrait
            new_entry["PackagePath"] = f"/{plugin}"
            new_entry["PackageName"] = f"/{plugin}/{portrait}"
            new_entry["ObjectPath"] = f"/{plugin}/{portrait}.{portrait}"
            for tag in new_entry["TagAndValue"]:
                if tag["Item1"] == "PrimaryAssetName":
                    tag["Item2"] = portrait
        elif asset_class == "Texture2D":
            new_entry["AssetName"] = texture
            new_entry["PackagePath"] = f"/{plugin}/{CONTENT_TEX_DIR}"
            new_entry["PackageName"] = f"/{plugin}/{CONTENT_TEX_DIR}/{texture}"
            new_entry["ObjectPath"] = (
                f"/{plugin}/{CONTENT_TEX_DIR}/{texture}.{texture}"
            )
        else:
            raise ValueError(f"Unexpected AssetClass in template registry: {asset_class}")
        out["fAssetDatas"].append(new_entry)
    out["keyValuePairs"] = rw.renumber_names(out)
    return out


def copy_bake_sources(dest_tools: Path) -> None:
    for name in (
        "bake_portrait.py",
        "repak.exe",
        "repak_LICENSE-MIT.txt",
        "repak_LICENSE-APACHE.txt",
    ):
        src = TOOLS / name
        if not src.is_file():
            raise FileNotFoundError(f"Missing toolkit file: {src}")
        shutil.copy2(src, dest_tools / name)
    bake_exe = TOOLS / "bake_portrait.exe"
    if bake_exe.is_file():
        shutil.copy2(bake_exe, dest_tools / "bake_portrait.exe")


def generate(slot_id: str, sex: str, out_parent: Path, force: bool) -> Path:
    validate_id(slot_id)
    if sex not in SEXES:
        raise ValueError(f"Sex must be one of {SEXES}: {sex!r}")

    meta = json.loads(TEMPLATES_JSON.read_text(encoding="utf-8"))
    set_meta = meta["sets"][sex]
    tpl_dir = TEMPLATES / set_meta["dir"]
    tpl_tex = set_meta["texture"]
    tpl_portrait = set_meta["portrait"]
    tpl_persona = set_meta["persona"]

    plugin = f"CPS_{slot_id}"
    texture = slot_id
    portrait = f"PO_{slot_id}"
    persona = f"{slot_id}_Template"
    content_path = f"{CONTENT_TEX_DIR}/{texture}"
    game_path = f"/{plugin}/{content_path}.{texture}"

    dest = out_parent / plugin
    if dest.exists():
        if not force:
            raise FileExistsError(
                f"Output already exists (will not overwrite): {dest}\n"
                "Delete it or pass -Force."
            )
        shutil.rmtree(dest)

    replacements = build_name_replacements(sex, plugin, texture, portrait, persona)
    display_old = template_display_name(sex)
    uexp_strings = {display_old: slot_id}

    tex_uasset = (tpl_dir / f"{tpl_tex}.uasset").read_bytes()
    tex_uexp = (tpl_dir / f"{tpl_tex}.uexp").read_bytes()
    por_uasset = (tpl_dir / f"{tpl_portrait}.uasset").read_bytes()
    por_uexp = (tpl_dir / f"{tpl_portrait}.uexp").read_bytes()
    per_uasset = (tpl_dir / f"{tpl_persona}.uasset").read_bytes()
    per_uexp = (tpl_dir / f"{tpl_persona}.uexp").read_bytes()

    tex_uasset, tex_uexp = ua.rename_cooked_asset(
        tex_uasset,
        tex_uexp,
        replacements,
        patch_bulk_offset=True,
    )
    por_uasset, por_uexp = ua.rename_cooked_asset(
        por_uasset,
        por_uexp,
        replacements,
    )
    per_uasset, per_uexp = ua.rename_cooked_asset(
        per_uasset,
        per_uexp,
        replacements,
        uexp_string_replacements=uexp_strings,
    )

    # Structural checks shared with bake
    from bake_portrait import check_uasset_size, validate_texture_uexp

    check_uasset_size(tex_uasset, texture)
    check_uasset_size(por_uasset, portrait)
    check_uasset_size(per_uasset, persona)
    validate_texture_uexp(tex_uexp)
    marker = f"/{plugin}/{content_path}\x00".encode("ascii")
    if marker not in tex_uasset:
        raise RuntimeError("Renamed texture .uasset is missing the expected package path")
    if game_path.encode("ascii") + b"\x00" not in por_uasset:
        raise RuntimeError("Renamed portrait .uasset is missing SoftObject gamePath")
    if portrait.encode("ascii") + b"\x00" not in per_uasset:
        raise RuntimeError("Renamed persona .uasset is missing PortraitAssetId name")
    if slot_id.encode("ascii") not in per_uexp:
        raise RuntimeError("Renamed persona .uexp is missing display Name/Callsign")

    registry_model = rewrite_registry(
        rw.load_model(tpl_dir / "AssetRegistry.json"),
        plugin=plugin,
        texture=texture,
        portrait=portrait,
        persona=persona,
    )
    registry_bin = rw.build_registry_bin(registry_model)
    parsed = rw.parse_registry_bin(registry_bin)
    if parsed["fAssetDatas"] != registry_model["fAssetDatas"]:
        raise RuntimeError("AssetRegistry round-trip mismatch")
    if len(parsed["fAssetDatas"]) != 3:
        raise RuntimeError("AssetRegistry must contain 3 assets")

    dest.mkdir(parents=True)
    (dest / "Resources").mkdir()
    (dest / "Paks").mkdir()
    tools_dir = dest / "Tools"
    cooked_dir = tools_dir / "cooked"
    cooked_dir.mkdir(parents=True)
    copy_bake_sources(tools_dir)

    (cooked_dir / f"{texture}.uasset").write_bytes(tex_uasset)
    (cooked_dir / f"{texture}.uexp").write_bytes(tex_uexp)
    (cooked_dir / f"{portrait}.uasset").write_bytes(por_uasset)
    (cooked_dir / f"{portrait}.uexp").write_bytes(por_uexp)
    (cooked_dir / f"{persona}.uasset").write_bytes(per_uasset)
    (cooked_dir / f"{persona}.uexp").write_bytes(per_uexp)

    pak_mw5 = tools_dir / "pak_template" / "MW5Mercs"
    tags_dir = pak_mw5 / "Config" / "Tags"
    input_dir = pak_mw5 / "Config" / "Input"
    plugin_dir = pak_mw5 / "Plugins" / plugin
    tags_dir.mkdir(parents=True)
    input_dir.mkdir(parents=True)
    plugin_dir.mkdir(parents=True)
    (tags_dir / f"{plugin}Tags.ini").write_text(TAGS_INI, encoding="utf-8", newline="\n")
    (input_dir / f"{plugin}Input.ini").write_text(INPUT_INI, encoding="utf-8", newline="\n")
    (plugin_dir / "AssetRegistry.bin").write_bytes(registry_bin)

    if not ICON_SRC.is_file():
        raise FileNotFoundError(f"Missing icon: {ICON_SRC}")
    shutil.copy2(ICON_SRC, dest / "Resources" / "Icon128.png")

    target = {
        "id": slot_id,
        "sex": sex,
        "plugin": plugin,
        "texture": texture,
        "portrait": portrait,
        "persona": persona,
        "contentPath": content_path,
        "gamePath": game_path,
        "uexpLayout": LAYOUT_NAME,
        "pakName": f"{plugin}.pak",
    }
    (tools_dir / "target.json").write_text(
        json.dumps(target, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    mod_json = {
        "displayName": f"Custom Portrait ({slot_id})",
        "version": "1.0",
        "buildNumber": 1,
        "description": (
            f"Custom portrait slot {slot_id} ({sex}). "
            "Put portrait.png in Resources and run bake_portrait.bat."
        ),
        "author": "",
        "authorURL": "",
        "defaultLoadOrder": DEFAULT_LOAD_ORDER,
        "gameVersion": GAME_VERSION,
        "manifest": [],
        "steamPublishedFileId": 0,
        "steamLastSubmittedBuildNumber": 0,
        "steamModVisibility": "Private",
    }
    (dest / "mod.json").write_text(
        json.dumps(mod_json, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (dest / "bake_portrait.bat").write_text(BAKE_BAT, encoding="utf-8")
    return dest


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a CPS_<Id> slot mod from CustomPortraitSlots templates."
    )
    parser.add_argument("id", help="Slot Id (A-Za-z0-9_, 1-32, start with a letter)")
    parser.add_argument(
        "-Sex",
        "--sex",
        dest="sex",
        choices=SEXES,
        default=None,
        help="Template sex (Female / Male / Nonbinary). Default: Nonbinary with a warning.",
    )
    parser.add_argument(
        "-Force",
        "--force",
        dest="force",
        action="store_true",
        help="Overwrite an existing out/CPS_<Id> folder.",
    )
    parser.add_argument(
        "-OutDir",
        "--outdir",
        dest="outdir",
        default=None,
        help=f"Parent folder for the new mod (default: {DEFAULT_OUT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    sex = args.sex
    if sex is None:
        sex = "Nonbinary"
        print(
            "WARNING: -Sex omitted; using Nonbinary. "
            "Pass -Sex Female|Male|Nonbinary to choose explicitly.",
            file=sys.stderr,
        )
    try:
        out_parent = Path(args.outdir) if args.outdir else DEFAULT_OUT
        out_parent.mkdir(parents=True, exist_ok=True)
        dest = generate(args.id, sex, out_parent.resolve(), args.force)
        print(f"Created: {dest}")
        print("Next: put portrait.png in Resources\\, run bake_portrait.bat, restart the game.")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
