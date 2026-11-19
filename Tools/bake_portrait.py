#!/usr/bin/env python3
"""Bake Resources/portrait.(png|jpg|jpeg) into the slot pak described by Tools/target.json.

Run from a generated slot mod folder (next to mod.json) via bake_portrait.bat.
Prefers portrait.png, then portrait.jpg / portrait.jpeg.

Layout "CPS_DXT5_512" (shared by the Female / Male / Nonbinary templates):
    512x512 PF_DXT5 UI texture, uexp 262427 bytes (magic 08), DXT payload at offset 255.
    The 20-byte inline bulk-data header just before the payload stores the payload
    offset as (uasset size + 255); bake rewrites it from the real .uasset size so a
    renamed (different-length) .uasset stays consistent.

Expected generated mod layout (Tools/target.json is the contract with generate_slot):
    Tools/cooked/{texture}.uasset/.uexp
    Tools/cooked/{portrait}.uasset/.uexp
    Tools/cooked/{persona}.uasset/.uexp
    Tools/pak_template/MW5Mercs/Plugins/{plugin}/AssetRegistry.bin   (+ any Config/)
    Paks/{pakName or plugin}.pak                                    (output)
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

if getattr(sys, "frozen", False):
    TOOLS = Path(sys.executable).resolve().parent
else:
    TOOLS = Path(__file__).resolve().parent
MOD_ROOT = TOOLS.parent
RESOURCES = MOD_ROOT / "Resources"
TARGET_JSON = TOOLS / "target.json"
REPAK = TOOLS / "repak.exe"
PAK_TEMPLATE = TOOLS / "pak_template"
COOKED_DIR = TOOLS / "cooked"

# MW5 pak settings (see Tools/README of the shared toolkit): never change.
PAK_MOUNT_POINT = "../../../MW5Mercs/"
PAK_VERSION = "V11"
PAK_PATH_HASH_SEED = "375655690"

PORTRAIT_NAMES = ("portrait.png", "portrait.jpg", "portrait.jpeg")

# ---- uexpLayout "CPS_DXT5_512" (measured from the Mod Editor texture CPST_Tex) ----
LAYOUT_NAME = "CPS_DXT5_512"
UI_SIZE = (512, 512)
UEXP_TRAILER_SIZE = 4
UE4_PACKAGE_FILE_TAG = b"\xc1\x83\x2a\x9e"
UEXP_SIZE = 262427
SERIAL_SIZE = UEXP_SIZE - UEXP_TRAILER_SIZE  # 262423
DXT_SIZE = (UI_SIZE[0] // 4) * (UI_SIZE[1] // 4) * 16  # 262144
MIP_FOOTER_SIZE = 24
DXT_OFFSET = SERIAL_SIZE - MIP_FOOTER_SIZE - DXT_SIZE  # 255
DXT_END = DXT_OFFSET + DXT_SIZE  # 262399
ALLOWED_MAGIC = {b"\x08\x00\x00\x00"}
PIXEL_FORMAT_OFFSET = 215
PIXEL_FORMAT = b"PF_DXT5\x00"
# FByteBulkData header: flags(i32) elementCount(i32) sizeOnDisk(i32) offsetInFile(i64)
BULK_HEADER_SIZE = 20
BULK_HEADER_OFFSET = DXT_OFFSET - BULK_HEADER_SIZE  # 235
BULK_FLAGS = 0x48  # ForceInlinePayload | SingleUse

SEXES = ("Male", "Female", "Nonbinary")
REQUIRED_TARGET_KEYS = (
    "id",
    "sex",
    "plugin",
    "texture",
    "portrait",
    "persona",
    "contentPath",
    "gamePath",
    "uexpLayout",
)


def layout_constants() -> dict:
    return {
        "width": UI_SIZE[0],
        "height": UI_SIZE[1],
        "pixelFormat": "PF_DXT5",
        "uexpSize": UEXP_SIZE,
        "uexpMagic": "08000000",
        "dxtOffset": DXT_OFFSET,
        "dxtSize": DXT_SIZE,
        "mipFooterSize": MIP_FOOTER_SIZE,
        "bulkHeaderOffset": BULK_HEADER_OFFSET,
        "bulkOffsetFormula": "len(uasset) + dxtOffset",
    }


# ----------------------------------------------------------------------------------
# cooked-asset checks / patching
# ----------------------------------------------------------------------------------


def uasset_total_header_size(uasset: bytes) -> int:
    """TotalHeaderSize of an unversioned cooked .uasset (== file size when .uexp is split)."""
    if len(uasset) < 28 or uasset[:4] != UE4_PACKAGE_FILE_TAG:
        raise RuntimeError("Not a UE4 .uasset (bad package tag)")
    custom_count = struct.unpack_from("<I", uasset, 20)[0]
    return struct.unpack_from("<i", uasset, 24 + custom_count * 20)[0]


def check_uasset_size(uasset: bytes, label: str) -> None:
    total = uasset_total_header_size(uasset)
    if total != len(uasset):
        raise RuntimeError(
            f"{label}.uasset TotalHeaderSize ({total}) != file size ({len(uasset)}). "
            "Regenerate the slot (cooked .uasset was edited inconsistently)."
        )


def validate_texture_uexp(uexp: bytes) -> None:
    """Structural checks for the CPS_DXT5_512 texture .uexp (independent of .uasset)."""
    if uexp[:4] not in ALLOWED_MAGIC:
        raise RuntimeError(f"Unexpected cooked .uexp magic: {uexp[:4].hex()}")
    if len(uexp) != UEXP_SIZE:
        raise RuntimeError(
            f"Unexpected cooked .uexp size: {len(uexp)} (layout {LAYOUT_NAME} needs {UEXP_SIZE})"
        )
    pf = uexp[PIXEL_FORMAT_OFFSET : PIXEL_FORMAT_OFFSET + len(PIXEL_FORMAT)]
    if pf != PIXEL_FORMAT:
        raise RuntimeError(f"Cooked .uexp is not PF_DXT5: {pf!r}")
    if uexp[-UEXP_TRAILER_SIZE:] != UE4_PACKAGE_FILE_TAG:
        raise RuntimeError(".uexp trailer is wrong")
    if DXT_END + MIP_FOOTER_SIZE != SERIAL_SIZE:
        raise RuntimeError("DXT layout constants are inconsistent")
    flags, count, size_on_disk = struct.unpack_from("<iii", uexp, BULK_HEADER_OFFSET)
    if flags != BULK_FLAGS or count != DXT_SIZE or size_on_disk != DXT_SIZE:
        raise RuntimeError(
            f"Unexpected bulk-data header: flags=0x{flags:x} count={count} size={size_on_disk}"
        )
    mip_x, mip_y, mip_z = struct.unpack_from("<iii", uexp, DXT_END)
    if (mip_x, mip_y, mip_z) != (UI_SIZE[0], UI_SIZE[1], 1):
        raise RuntimeError(f"Mip size is not {UI_SIZE[0]}x{UI_SIZE[1]}x1: {mip_x}x{mip_y}x{mip_z}")


def validate_template_texture(uasset: bytes, uexp: bytes) -> None:
    """Check a frozen template texture, including the bulk offset == uasset size + 255 rule."""
    check_uasset_size(uasset, "template texture")
    validate_texture_uexp(uexp)
    (offset,) = struct.unpack_from("<q", uexp, BULK_HEADER_OFFSET + 12)
    if offset != len(uasset) + DXT_OFFSET:
        raise RuntimeError(
            f"Template bulk offset {offset} != uasset size {len(uasset)} + {DXT_OFFSET}"
        )


def patch_cooked_uexp(template_uexp: bytes, dxt5: bytes, uasset_size: int) -> bytes:
    validate_texture_uexp(template_uexp)
    if len(dxt5) != DXT_SIZE:
        raise ValueError(f"DXT5 data must be {DXT_SIZE} bytes")
    patched = bytearray(template_uexp)
    patched[DXT_OFFSET:DXT_END] = dxt5
    struct.pack_into("<q", patched, BULK_HEADER_OFFSET + 12, uasset_size + DXT_OFFSET)
    patched = bytes(patched)
    validate_texture_uexp(patched)
    return patched


# ----------------------------------------------------------------------------------
# image -> DXT5
# ----------------------------------------------------------------------------------


def resolve_portrait_path() -> Path:
    for name in PORTRAIT_NAMES:
        path = RESOURCES / name
        if path.is_file():
            return path
    if RESOURCES.is_dir():
        by_lower = {
            child.name.lower(): child for child in RESOURCES.iterdir() if child.is_file()
        }
        for name in PORTRAIT_NAMES:
            hit = by_lower.get(name)
            if hit is not None:
                return hit
    raise FileNotFoundError(
        "Resources\\portrait.png / portrait.jpg / portrait.jpeg not found.\n"
        f"Put your image here: {RESOURCES}"
    )


def cover_to_rgba_bytes(image_path: Path, size: tuple[int, int]) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is not installed. Run: pip install pillow etcpak") from exc

    target_w, target_h = size
    with Image.open(image_path) as img:
        oriented = ImageOps.exif_transpose(img)
        prepared = oriented.convert("RGBA")
    # Zero RGB where fully transparent (cleaner DXT blocks), same as CustomPortraitKit.
    mask = prepared.getchannel("A").point(lambda v: 255 if v > 0 else 0)
    prepared = Image.composite(prepared, Image.new("RGBA", prepared.size, (0, 0, 0, 0)), mask)

    width0, height0 = prepared.size
    scale = max(target_w / width0, target_h / height0)
    scaled_w = max(1, round(width0 * scale))
    scaled_h = max(1, round(height0 * scale))
    resized = prepared.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    left = (scaled_w - target_w) // 2
    top = (scaled_h - target_h) // 2
    cropped = resized.crop((left, top, left + target_w, top + target_h))
    return cropped.tobytes()


def encode_dxt5(rgba: bytes, size: tuple[int, int]) -> bytes:
    try:
        import etcpak
    except ImportError as exc:
        raise RuntimeError("etcpak is not installed. Run: pip install pillow etcpak") from exc

    width, height = size
    if len(rgba) != width * height * 4:
        raise ValueError(f"Unexpected RGBA size: {len(rgba)}")
    dxt = etcpak.compress_to_dxt5(rgba, width, height)
    if len(dxt) != DXT_SIZE:
        raise ValueError(f"Unexpected DXT5 size: {len(dxt)}")
    return dxt


# ----------------------------------------------------------------------------------
# target.json / pak
# ----------------------------------------------------------------------------------


def load_target() -> dict:
    if not TARGET_JSON.is_file():
        raise FileNotFoundError(
            f"Tools\\target.json not found: {TARGET_JSON}\n"
            "This bake script belongs inside a generated slot mod (generate_slot)."
        )
    data = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
    for key in REQUIRED_TARGET_KEYS:
        if not data.get(key):
            raise RuntimeError(f"target.json missing '{key}'")
    if data["sex"] not in SEXES:
        raise RuntimeError(f"target.json 'sex' must be one of {SEXES}: {data['sex']!r}")
    if data["uexpLayout"] != LAYOUT_NAME:
        raise RuntimeError(
            f"target.json uexpLayout {data['uexpLayout']!r} is not supported "
            f"(this bake handles {LAYOUT_NAME!r})"
        )
    return data


def _read_cooked(name: str) -> tuple[bytes, bytes]:
    uasset = COOKED_DIR / f"{name}.uasset"
    uexp = COOKED_DIR / f"{name}.uexp"
    if not uasset.is_file() or not uexp.is_file():
        raise FileNotFoundError(
            f"Tools\\cooked\\{name}.uasset / .uexp not found. Regenerate this slot with generate_slot."
        )
    return uasset.read_bytes(), uexp.read_bytes()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack_pak(stage_mw5: Path, pak_path: Path) -> None:
    if not REPAK.is_file():
        raise FileNotFoundError(f"repak.exe not found: {REPAK}")
    pak_path.parent.mkdir(parents=True, exist_ok=True)
    if pak_path.is_file():
        pak_path.unlink()
    result = subprocess.run(
        [
            str(REPAK),
            "pack",
            "--mount-point",
            PAK_MOUNT_POINT,
            "--version",
            PAK_VERSION,
            "--path-hash-seed",
            PAK_PATH_HASH_SEED,
            "-q",
            str(stage_mw5),
            str(pak_path),
        ],
        cwd=str(REPAK.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"repak failed\nstdout: {result.stdout}\nstderr: {result.stderr}")


def verify_pak(stage_mw5: Path, pak_path: Path) -> int:
    """Unpack the pak and compare SHA-256 of every staged file. Returns the file count."""
    with tempfile.TemporaryDirectory(prefix="cps_verify_") as tmp:
        result = subprocess.run(
            [str(REPAK), "unpack", "-o", tmp, str(pak_path)],
            cwd=str(REPAK.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(f"repak unpack failed\nstdout: {result.stdout}\nstderr: {result.stderr}")
        unpacked_root = Path(tmp) / "MW5Mercs"
        staged = [p for p in stage_mw5.rglob("*") if p.is_file()]
        for src in staged:
            rel = src.relative_to(stage_mw5)
            other = unpacked_root / rel
            if not other.is_file() or _sha256(other) != _sha256(src):
                raise RuntimeError(f"Pak verification failed for {rel.as_posix()}")
        extra = sum(1 for p in unpacked_root.rglob("*") if p.is_file()) - len(staged)
        if extra != 0:
            raise RuntimeError(f"Pak contains {extra} unexpected extra file(s)")
        return len(staged)


def bake() -> None:
    target = load_target()
    plugin = target["plugin"]
    texture = target["texture"]
    portrait = target["portrait"]
    persona = target["persona"]
    game_path = target["gamePath"]
    content_path = target["contentPath"].replace("\\", "/").strip("/")
    if "/" not in content_path:
        content_dir_parts: list[str] = []
    else:
        content_dir_parts = content_path.split("/")[:-1]
    if content_path.split("/")[-1] != texture:
        raise RuntimeError(f"contentPath must end with the texture name '{texture}': {content_path}")
    pak_name = target.get("pakName") or plugin
    if not pak_name.endswith(".pak"):
        pak_name = f"{pak_name}.pak"
    pak_path = MOD_ROOT / "Paks" / pak_name

    portrait_path = resolve_portrait_path()

    tex_uasset, tex_uexp = _read_cooked(texture)
    por_uasset, por_uexp = _read_cooked(portrait)
    per_uasset, per_uexp = _read_cooked(persona)
    for label, data in ((texture, tex_uasset), (portrait, por_uasset), (persona, per_uasset)):
        check_uasset_size(data, label)

    marker = f"/{plugin}/{content_path}\x00".encode("ascii")
    if marker not in tex_uasset:
        raise RuntimeError(f"Tools\\cooked\\{texture}.uasset does not contain /{plugin}/{content_path}")
    if game_path.encode("ascii") + b"\x00" not in por_uasset:
        raise RuntimeError(f"Tools\\cooked\\{portrait}.uasset does not reference {game_path}")

    rgba = cover_to_rgba_bytes(portrait_path, UI_SIZE)
    dxt5 = encode_dxt5(rgba, UI_SIZE)
    baked_uexp = patch_cooked_uexp(tex_uexp, dxt5, len(tex_uasset))

    registry = PAK_TEMPLATE / "MW5Mercs" / "Plugins" / plugin / "AssetRegistry.bin"
    if not registry.is_file():
        raise FileNotFoundError(
            f"Tools\\pak_template\\MW5Mercs\\Plugins\\{plugin}\\AssetRegistry.bin not found. "
            "Regenerate this slot with generate_slot."
        )

    with tempfile.TemporaryDirectory(prefix="cps_bake_") as tmp:
        stage = Path(tmp)
        shutil.copytree(PAK_TEMPLATE, stage, dirs_exist_ok=True)
        stage_mw5 = stage / "MW5Mercs"
        out_dir = stage_mw5 / "Plugins" / plugin / "Content"
        for part in content_dir_parts:
            out_dir = out_dir / part
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{texture}.uasset").write_bytes(tex_uasset)
        (out_dir / f"{texture}.uexp").write_bytes(baked_uexp)
        (out_dir / f"{portrait}.uasset").write_bytes(por_uasset)
        (out_dir / f"{portrait}.uexp").write_bytes(por_uexp)
        (out_dir / f"{persona}.uasset").write_bytes(per_uasset)
        (out_dir / f"{persona}.uexp").write_bytes(per_uexp)
        pack_pak(stage_mw5, pak_path)
        file_count = verify_pak(stage_mw5, pak_path)

    print(f"Input:   {portrait_path}")
    print(f"Slot:    {target['id']} ({target['sex']})  plugin {plugin}")
    print(f"Texture: {game_path}  [{LAYOUT_NAME}]")
    print(f"Output:  {pak_path}  ({pak_path.stat().st_size} bytes, {file_count} files verified)")
    print("Done. Restart the game to see the new portrait slot.")


def main() -> None:
    try:
        bake()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
