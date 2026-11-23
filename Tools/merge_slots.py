#!/usr/bin/env python3
"""Merge baked CPS_* slot mods under MergeInbox/<PackName>/ into pack mods.

Double-click merge_slots.bat (no args). Each MergeInbox subfolder is one pack:
  - Pack folder name = out folder / pak name / mod.json displayName
  - Each slot keeps Plugins/CPS_{Id}/ (registries side-by-side; paths unchanged)
  - Unbaked slots (no Paks/CPS_{Id}.pak) are skipped and listed
  - ID / PrimaryAssetName collisions fail that pack only
  - Tags ini must match across slots; written as {PackName}Tags.ini
  - PackCatalog.html is generated on success (copy-paste matches target.json)
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

import bake_portrait as bake
import generate_slot as gen

if getattr(sys, "frozen", False):
    TOOLS = Path(sys.executable).resolve().parent
else:
    TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
MERGE_INBOX = ROOT / "MergeInbox"
OUT_ROOT = ROOT / "out"
ICON_SRC = TOOLS / "assets" / "Icon128.png"
REPAK = TOOLS / "repak.exe"

GAME_VERSION = gen.GAME_VERSION
DEFAULT_LOAD_ORDER = gen.DEFAULT_LOAD_ORDER
REQUIRED_TARGET_KEYS = bake.REQUIRED_TARGET_KEYS
SEXES = bake.SEXES

THUMB = 96
PERSONA_TAGS_COMMON = (
    "Persona.Role.Pilot",
    "Persona.Use.Template",
    "Persona.Use.Employable",
)
PORTRAIT_TAG = "Portrait.CPS"

TAGS_INI = gen.TAGS_INI
INPUT_INI = gen.INPUT_INI


@dataclass
class SlotInfo:
    folder: Path
    target: dict[str, Any]
    pak_path: Path
    tags_text: str


@dataclass
class PackResult:
    name: str
    ok: bool
    message: str
    out_dir: Path | None = None
    slots: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def validate_pack_name(name: str) -> None:
    """Pack names use the same character rules as slot Ids."""
    gen.validate_id(name)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def load_target(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in REQUIRED_TARGET_KEYS:
        if not data.get(key):
            raise RuntimeError(f"target.json missing '{key}' ({path})")
    if data["sex"] not in SEXES:
        raise RuntimeError(f"target.json 'sex' must be one of {SEXES}: {data['sex']!r}")
    return data


def find_slot_pak(slot_dir: Path, plugin: str, target: dict[str, Any]) -> Path | None:
    paks = slot_dir / "Paks"
    if not paks.is_dir():
        return None
    pak_name = target.get("pakName") or f"{plugin}.pak"
    if not str(pak_name).endswith(".pak"):
        pak_name = f"{pak_name}.pak"
    candidate = paks / pak_name
    if candidate.is_file():
        return candidate
    fallback = paks / f"{plugin}.pak"
    if fallback.is_file():
        return fallback
    return None


def read_slot_tags(slot_dir: Path, plugin: str) -> str:
    tags_path = (
        slot_dir
        / "Tools"
        / "pak_template"
        / "MW5Mercs"
        / "Config"
        / "Tags"
        / f"{plugin}Tags.ini"
    )
    if tags_path.is_file():
        return normalize_newlines(tags_path.read_text(encoding="utf-8"))
    # Fall back to Portrait.CPS definition (same as generate_slot).
    return normalize_newlines(TAGS_INI)


def persona_tags_for_sex(sex: str) -> list[str]:
    return [PORTRAIT_TAG, f"Persona.Sex.{sex}", *PERSONA_TAGS_COMMON]


def dxt5_to_png_b64(dxt: bytes, width: int, height: int) -> str:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is not installed. Run: pip install pillow") from exc

    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x1 | 0x2 | 0x4 | 0x1000)
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 20, len(dxt))
    struct.pack_into("<I", header, 28, 1)
    struct.pack_into("<I", header, 76, 32)
    struct.pack_into("<I", header, 80, 0x4)
    header[84:88] = b"DXT5"
    struct.pack_into("<I", header, 108, 0x1000)
    img = Image.open(io.BytesIO(bytes(header) + dxt)).convert("RGBA")
    img = img.resize((THUMB, THUMB), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def thumb_from_texture_uexp(uexp: bytes) -> str:
    bake.validate_texture_uexp(uexp)
    dxt = uexp[bake.DXT_OFFSET : bake.DXT_END]
    return dxt5_to_png_b64(dxt, bake.UI_SIZE[0], bake.UI_SIZE[1])


def unpack_pak(pak_path: Path, dest_dir: Path) -> Path:
    if not REPAK.is_file():
        raise FileNotFoundError(f"repak.exe not found: {REPAK}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(REPAK), "unpack", "-o", str(dest_dir), str(pak_path)],
        cwd=str(REPAK.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"repak unpack failed for {pak_path.name}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    mw5 = dest_dir / "MW5Mercs"
    if not mw5.is_dir():
        raise RuntimeError(f"Unpacked pak missing MW5Mercs/: {pak_path}")
    return mw5


def copy_tree_into(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)


def build_pack_catalog_html(pack_name: str, slots: list[SlotInfo], stage_mw5: Path) -> str:
    cards: list[str] = []
    for slot in slots:
        target = slot.target
        slot_id = target["id"]
        sex = target["sex"]
        plugin = target["plugin"]
        texture = target["texture"]
        content_path = target["contentPath"].replace("\\", "/").strip("/")
        uexp_path = stage_mw5 / "Plugins" / plugin / "Content" / Path(content_path + ".uexp")
        if not uexp_path.is_file():
            raise FileNotFoundError(f"Baked texture missing in stage: {uexp_path}")
        b64 = thumb_from_texture_uexp(uexp_path.read_bytes())
        cmd = f".\\generate_slot.bat {slot_id} -Sex {sex}"
        # Guard: command args must match target.json exactly.
        if slot_id != target["id"] or sex != target["sex"]:
            raise RuntimeError("PackCatalog command does not match target.json")
        tags = persona_tags_for_sex(sex)
        tag_html = " ".join(f'<span class="tag">{escape(t)}</span>' for t in tags)
        cards.append(
            "\n".join(
                [
                    '<div class="card">',
                    f'  <img src="data:image/png;base64,{b64}" width="{THUMB}" height="{THUMB}" alt="">',
                    f'  <div class="meta"><strong>{escape(slot_id)}</strong> · {escape(sex)}</div>',
                    f'  <div class="tags">{tag_html}</div>',
                    f'  <code class="cmd" tabindex="0">{escape(cmd)}</code>',
                    f'  <button type="button" data-cmd="{escape(cmd, quote=True)}">Copy</button>',
                    "</div>",
                ]
            )
        )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(pack_name)} — PackCatalog</title>
<style>
  :root {{ font-family: Consolas, "Segoe UI", Meiryo, sans-serif; }}
  body {{ margin: 16px; background: #f4f4f4; color: #111; }}
  h1 {{ font-size: 1.1rem; margin: 0 0 4px; }}
  .note {{ font-size: 0.85rem; color: #444; margin: 0 0 16px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }}
  .card {{
    background: #fff; border: 1px solid #ddd; border-radius: 6px;
    padding: 10px; display: flex; flex-direction: column; gap: 8px; align-items: stretch;
  }}
  .card img {{
    width: {THUMB}px; height: {THUMB}px; object-fit: contain; align-self: center;
    background:
      linear-gradient(45deg, #ddd 25%, transparent 25%),
      linear-gradient(-45deg, #ddd 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #ddd 75%),
      linear-gradient(-45deg, transparent 75%, #ddd 75%);
    background-size: 12px 12px;
    background-position: 0 0, 0 6px, 6px -6px, -6px 0;
  }}
  .meta {{ font-size: 0.9rem; }}
  .tags {{ font-size: 0.72rem; color: #333; display: flex; flex-wrap: wrap; gap: 4px; }}
  .tag {{ background: #eee; padding: 2px 6px; border-radius: 3px; }}
  .cmd {{
    font-size: 0.72rem; word-break: break-all; user-select: all;
    background: #f0f0f0; padding: 6px; border-radius: 4px; border: 1px solid #e0e0e0;
  }}
  button {{ cursor: pointer; font: inherit; font-size: 0.8rem; padding: 4px 8px; }}
  button.ok {{ background: #cfc; }}
</style>
</head>
<body>
<h1>{escape(pack_name)} ({len(slots)} slots)</h1>
<p class="note">Thumbnails are decoded from the baked pak textures. Copy the command into the CustomPortraitSlots folder console.</p>
<div class="grid">
{chr(10).join(cards)}
</div>
<script>
document.querySelectorAll("button[data-cmd]").forEach((btn) => {{
  btn.addEventListener("click", async () => {{
    const text = btn.getAttribute("data-cmd") || "";
    try {{
      await navigator.clipboard.writeText(text);
      btn.textContent = "Copied";
      btn.classList.add("ok");
      setTimeout(() => {{ btn.textContent = "Copy"; btn.classList.remove("ok"); }}, 1000);
    }} catch (e) {{
      const code = btn.parentElement.querySelector(".cmd");
      const range = document.createRange();
      range.selectNodeContents(code);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      btn.textContent = "Select";
    }}
  }});
}});
</script>
</body>
</html>
"""


def collect_pack_slots(pack_dir: Path) -> tuple[list[SlotInfo], list[str]]:
    """Return (valid baked slots, skip messages). Raises on malformed baked slots."""
    valid: list[SlotInfo] = []
    skipped: list[str] = []

    children = sorted(
        [p for p in pack_dir.iterdir() if p.is_dir()],
        key=lambda p: p.name.lower(),
    )
    for child in children:
        target_path = child / "Tools" / "target.json"
        if not target_path.is_file():
            skipped.append(f"{child.name}: skip (no Tools/target.json)")
            continue
        try:
            target = load_target(target_path)
        except Exception as exc:
            raise RuntimeError(f"{child.name}: {exc}") from exc

        slot_id = target["id"]
        plugin = target["plugin"]
        if plugin != f"CPS_{slot_id}":
            raise RuntimeError(
                f"{child.name}: plugin {plugin!r} must equal CPS_{slot_id}"
            )
        if child.name != plugin:
            raise RuntimeError(
                f"{child.name}: folder name must match plugin {plugin!r}"
            )
        try:
            gen.validate_id(slot_id)
        except ValueError as exc:
            raise RuntimeError(f"{child.name}: {exc}") from exc

        pak = find_slot_pak(child, plugin, target)
        if pak is None:
            skipped.append(
                f"{child.name}: skip (unbaked — missing Paks/{plugin}.pak)"
            )
            continue

        tags_text = read_slot_tags(child, plugin)
        valid.append(
            SlotInfo(folder=child, target=target, pak_path=pak, tags_text=tags_text)
        )
    return valid, skipped


def detect_collisions(slots: list[SlotInfo]) -> None:
    id_map: dict[str, str] = {}
    primary_map: dict[str, str] = {}

    for slot in slots:
        t = slot.target
        slot_id = t["id"]
        key = slot_id.lower()
        if key in id_map:
            raise RuntimeError(
                f"Slot Id collision (case-insensitive): {id_map[key]!r} vs {slot_id!r}"
            )
        id_map[key] = slot_id

        for label, name in (
            ("texture", t["texture"]),
            ("portrait", t["portrait"]),
            ("persona", t["persona"]),
            ("plugin", t["plugin"]),
        ):
            pkey = str(name).lower()
            if pkey in primary_map:
                raise RuntimeError(
                    f"PrimaryAssetName / asset name collision (case-insensitive): "
                    f"{primary_map[pkey]!r} vs {name!r} ({label} of {slot_id})"
                )
            primary_map[pkey] = str(name)


def ensure_identical_tags(slots: list[SlotInfo]) -> str:
    texts = {s.tags_text for s in slots}
    if len(texts) != 1:
        names = ", ".join(s.target["id"] for s in slots)
        raise RuntimeError(
            f"Tags ini content differs across slots ({names}). "
            "All slots in a pack must share the same Portrait.CPS Tags ini."
        )
    return next(iter(texts))


def write_pack_mod_json(dest: Path, pack_name: str, slot_ids: list[str]) -> None:
    mod_json = {
        "displayName": pack_name,
        "version": "1.0",
        "buildNumber": 1,
        "description": (
            f"CustomPortraitSlots pack with {len(slot_ids)} slot(s): "
            + ", ".join(slot_ids)
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


def merge_one_pack(pack_dir: Path) -> PackResult:
    pack_name = pack_dir.name
    try:
        validate_pack_name(pack_name)
    except ValueError as exc:
        return PackResult(pack_name, False, f"Invalid pack name: {exc}")

    try:
        slots, skipped = collect_pack_slots(pack_dir)
    except Exception as exc:
        return PackResult(pack_name, False, str(exc), skipped=[])

    if not slots:
        msg = "No baked slots — pack skipped"
        if skipped:
            msg += "\n  " + "\n  ".join(skipped)
        return PackResult(pack_name, True, msg, skipped=skipped)

    try:
        detect_collisions(slots)
        tags_text = ensure_identical_tags(slots)
    except Exception as exc:
        return PackResult(
            pack_name,
            False,
            str(exc),
            slots=[s.target["id"] for s in slots],
            skipped=skipped,
        )

    out_dir = OUT_ROOT / pack_name
    overwritten = out_dir.exists()

    with tempfile.TemporaryDirectory(prefix="cps_merge_") as tmp:
        tmp_path = Path(tmp)
        stage_mw5 = tmp_path / "stage" / "MW5Mercs"
        plugins_root = stage_mw5 / "Plugins"
        tags_dir = stage_mw5 / "Config" / "Tags"
        input_dir = stage_mw5 / "Config" / "Input"
        tags_dir.mkdir(parents=True)
        input_dir.mkdir(parents=True)
        plugins_root.mkdir(parents=True)

        for slot in slots:
            unpack_root = tmp_path / "unpack" / slot.target["plugin"]
            mw5 = unpack_pak(slot.pak_path, unpack_root)
            plugin = slot.target["plugin"]
            src_plugin = mw5 / "Plugins" / plugin
            if not src_plugin.is_dir():
                return PackResult(
                    pack_name,
                    False,
                    f"{plugin}: pak missing Plugins/{plugin}/",
                    skipped=skipped,
                )
            dest_plugin = plugins_root / plugin
            if dest_plugin.exists():
                return PackResult(
                    pack_name,
                    False,
                    f"Duplicate plugin path while staging: {plugin}",
                    skipped=skipped,
                )
            copy_tree_into(src_plugin, dest_plugin)

        (tags_dir / f"{pack_name}Tags.ini").write_text(
            tags_text, encoding="utf-8", newline="\n"
        )
        (input_dir / f"{pack_name}Input.ini").write_text(
            INPUT_INI, encoding="utf-8", newline="\n"
        )

        try:
            catalog_html = build_pack_catalog_html(pack_name, slots, stage_mw5)
        except Exception as exc:
            return PackResult(
                pack_name,
                False,
                f"PackCatalog.html failed: {exc}",
                slots=[s.target["id"] for s in slots],
                skipped=skipped,
            )

        OUT_ROOT.mkdir(parents=True, exist_ok=True)
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True)
        (out_dir / "Paks").mkdir()
        (out_dir / "Resources").mkdir()

        pak_path = out_dir / "Paks" / f"{pack_name}.pak"
        try:
            bake.pack_pak(stage_mw5, pak_path)
            file_count = bake.verify_pak(stage_mw5, pak_path)
        except Exception as exc:
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
            return PackResult(
                pack_name,
                False,
                f"Pack failed: {exc}",
                slots=[s.target["id"] for s in slots],
                skipped=skipped,
            )

        if not ICON_SRC.is_file():
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
            return PackResult(pack_name, False, f"Missing icon: {ICON_SRC}")
        shutil.copy2(ICON_SRC, out_dir / "Resources" / "Icon128.png")
        write_pack_mod_json(out_dir, pack_name, [s.target["id"] for s in slots])
        (out_dir / "PackCatalog.html").write_text(catalog_html, encoding="utf-8")

    slot_ids = [s.target["id"] for s in slots]
    msg = (
        f"OK → {out_dir} ({len(slot_ids)} slots, pak {pak_path.stat().st_size} bytes, "
        f"{file_count} files verified)"
    )
    if overwritten:
        msg = f"Overwrote existing output. {msg}"
    if skipped:
        msg += "\n  Skipped:\n  " + "\n  ".join(skipped)
    return PackResult(
        pack_name,
        True,
        msg,
        out_dir=out_dir,
        slots=slot_ids,
        skipped=skipped,
    )


def list_pack_dirs() -> list[Path]:
    if not MERGE_INBOX.is_dir():
        return []
    return sorted(
        [p for p in MERGE_INBOX.iterdir() if p.is_dir()],
        key=lambda p: p.name.lower(),
    )


def run() -> int:
    packs = list_pack_dirs()
    if not packs:
        print("MergeInbox is empty.")
        print(f"Create MergeInbox\\<PackName>\\ and put baked CPS_* mods inside.")
        print(f"Path: {MERGE_INBOX}")
        return 1

    print(f"MergeInbox: {len(packs)} pack folder(s)")
    results: list[PackResult] = []
    for pack_dir in packs:
        print(f"\n=== {pack_dir.name} ===")
        result = merge_one_pack(pack_dir)
        results.append(result)
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.message}")
        if result.slots:
            print(f"  Slots: {', '.join(result.slots)}")

    failed = [r for r in results if not r.ok]
    succeeded = [r for r in results if r.ok and r.out_dir is not None]
    print("\n----")
    print(f"Succeeded: {len(succeeded)}  Failed: {len(failed)}  Packs seen: {len(results)}")
    return 1 if failed else 0


def main() -> None:
    try:
        code = run()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
