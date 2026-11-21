"""Cooked UE4.26 .uasset / .uexp の名前テーブル書換とオフセット再計算。

MW5 のクック済み（unversioned、.uexp 分離）アセット向け。
名前ハッシュは registry_writer.generate_hash（UAssetAPI と同じ式）を使う。
"""

from __future__ import annotations

import struct
from typing import Mapping

import registry_writer as rw

UE4_PACKAGE_FILE_TAG = b"\xc1\x83\x2a\x9e"


def _read_fstring(data: bytes, off: int) -> tuple[str, int]:
    n = struct.unpack_from("<i", data, off)[0]
    if n == 0:
        return "", off + 4
    if n < 0:
        raise ValueError("UTF-16 FString is not supported")
    text = data[off + 4 : off + 4 + n - 1].decode("ascii")
    return text, off + 4 + n


def _write_fstring(text: str) -> bytes:
    raw = text.encode("ascii") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def _write_name_entry(name: str) -> bytes:
    return _write_fstring(name) + struct.pack("<I", rw.generate_hash(name))


class _Summary:
    __slots__ = (
        "total_header_size_off",
        "name_count",
        "name_offset",
        "name_count_off",
        "name_offset_off",
        "import_count",
        "import_offset",
        "import_offset_off",
        "export_count",
        "export_offset",
        "export_offset_off",
        "depends_offset",
        "depends_offset_off",
        "soft_count",
        "soft_offset",
        "soft_offset_off",
        "search_offset",
        "search_offset_off",
        "thumb_offset",
        "thumb_offset_off",
        "gather_count",
        "gather_offset",
        "gather_offset_off",
        "asset_registry_offset",
        "asset_registry_offset_off",
        "bulk_data_offset",
        "bulk_data_offset_off",
        "preload_count",
        "preload_offset",
        "preload_offset_off",
        "export_serial_size_off",
        "export_serial_offset_off",
        "names",
        "name_map_end",
    )


def _parse_summary(data: bytes) -> _Summary:
    if data[:4] != UE4_PACKAGE_FILE_TAG:
        raise ValueError("Not a UE4 .uasset")
    legacy = struct.unpack_from("<i", data, 4)[0]
    off = 8
    if legacy != -4:
        off += 4  # LegacyUE3Version
    off += 8  # FileVersionUE4 + Licensee
    custom_count = struct.unpack_from("<I", data, off)[0]
    off += 4 + custom_count * 20

    s = _Summary()
    s.total_header_size_off = off
    off += 4  # TotalHeaderSize
    _folder, off = _read_fstring(data, off)
    off += 4  # PackageFlags

    s.name_count_off = off
    s.name_count = struct.unpack_from("<i", data, off)[0]
    off += 4
    s.name_offset_off = off
    s.name_offset = struct.unpack_from("<i", data, off)[0]
    off += 4

    s.gather_count = struct.unpack_from("<i", data, off)[0]
    off += 4
    s.gather_offset_off = off
    s.gather_offset = struct.unpack_from("<i", data, off)[0]
    off += 4

    s.export_count = struct.unpack_from("<i", data, off)[0]
    off += 4
    s.export_offset_off = off
    s.export_offset = struct.unpack_from("<i", data, off)[0]
    off += 4

    s.import_count = struct.unpack_from("<i", data, off)[0]
    off += 4
    s.import_offset_off = off
    s.import_offset = struct.unpack_from("<i", data, off)[0]
    off += 4

    s.depends_offset_off = off
    s.depends_offset = struct.unpack_from("<i", data, off)[0]
    off += 4

    s.soft_count = struct.unpack_from("<i", data, off)[0]
    off += 4
    s.soft_offset_off = off
    s.soft_offset = struct.unpack_from("<i", data, off)[0]
    off += 4

    s.search_offset_off = off
    s.search_offset = struct.unpack_from("<i", data, off)[0]
    off += 4
    s.thumb_offset_off = off
    s.thumb_offset = struct.unpack_from("<i", data, off)[0]
    off += 4

    off += 16  # Guid
    gen_count = struct.unpack_from("<i", data, off)[0]
    off += 4 + gen_count * 8

    # SavedByEngineVersion + CompatibleWithEngineVersion
    for _ in range(2):
        off += 6 + 4  # Major/Minor/Patch + Changelist
        _branch, off = _read_fstring(data, off)
    off += 4  # CompressionFlags
    chunk_count = struct.unpack_from("<i", data, off)[0]
    off += 4
    if chunk_count:
        raise ValueError("CompressedChunks in cooked header are not supported")
    off += 4  # PackageSource
    additional = struct.unpack_from("<i", data, off)[0]
    off += 4
    for _ in range(additional):
        _pkg, off = _read_fstring(data, off)

    s.asset_registry_offset_off = off
    s.asset_registry_offset = struct.unpack_from("<i", data, off)[0]
    off += 4
    s.bulk_data_offset_off = off
    s.bulk_data_offset = struct.unpack_from("<i", data, off)[0]
    off += 4
    off += 12  # WorldTileInfo / padding zeros observed in templates
    s.preload_count = struct.unpack_from("<i", data, off)[0]
    off += 4
    s.preload_offset_off = off
    s.preload_offset = struct.unpack_from("<i", data, off)[0]
    off += 4

    if off != s.name_offset:
        raise ValueError(f"NameOffset mismatch: cursor {off} != {s.name_offset}")

    names: list[str] = []
    pos = s.name_offset
    for _ in range(s.name_count):
        text, pos = _read_fstring(data, pos)
        pos += 4  # hash
        names.append(text)
    s.names = names
    s.name_map_end = pos
    if pos != s.import_offset:
        raise ValueError(f"Name map end {pos} != ImportOffset {s.import_offset}")

    if s.export_count != 1:
        raise ValueError(f"Expected 1 export, got {s.export_count}")
    # FObjectExport: Class/Super/Template/Outer (4*i32) + ObjectName (FName) + ObjectFlags (u32)
    # then SerialSize (i64) + SerialOffset (i64)
    export = s.export_offset
    s.export_serial_size_off = export + 4 * 4 + 8 + 4
    s.export_serial_offset_off = s.export_serial_size_off + 8
    return s


def _patch_i32(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<i", buf, offset, value)


def _patch_i64(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<q", buf, offset, value)


def _adjust(offset: int, delta: int, threshold: int) -> int:
    if offset != 0 and offset >= threshold:
        return offset + delta
    return offset


def rename_uasset_names(uasset: bytes, replacements: Mapping[str, str]) -> bytes:
    """名前テーブルの完全一致エントリを置換し、TotalHeaderSize と関連オフセットを直す。"""
    summary = _parse_summary(uasset)
    new_names: list[str] = []
    changed = False
    for name in summary.names:
        if name in replacements:
            new_names.append(replacements[name])
            if replacements[name] != name:
                changed = True
        else:
            new_names.append(name)
    if not changed:
        # still verify TotalHeaderSize
        total = struct.unpack_from("<i", uasset, summary.total_header_size_off)[0]
        if total != len(uasset):
            raise ValueError(
                f"TotalHeaderSize ({total}) != file size ({len(uasset)}) before rename"
            )
        return uasset

    new_map = b"".join(_write_name_entry(n) for n in new_names)
    old_map_size = summary.name_map_end - summary.name_offset
    delta = len(new_map) - old_map_size

    out = bytearray()
    out += uasset[: summary.name_offset]
    out += new_map
    out += uasset[summary.name_map_end :]

    threshold = summary.name_offset
    _patch_i32(out, summary.total_header_size_off, len(uasset) + delta)
    _patch_i32(
        out,
        summary.import_offset_off,
        _adjust(summary.import_offset, delta, threshold),
    )
    _patch_i32(
        out,
        summary.export_offset_off,
        _adjust(summary.export_offset, delta, threshold),
    )
    _patch_i32(
        out,
        summary.depends_offset_off,
        _adjust(summary.depends_offset, delta, threshold),
    )
    _patch_i32(
        out,
        summary.gather_offset_off,
        _adjust(summary.gather_offset, delta, threshold),
    )
    _patch_i32(
        out,
        summary.soft_offset_off,
        _adjust(summary.soft_offset, delta, threshold),
    )
    _patch_i32(
        out,
        summary.search_offset_off,
        _adjust(summary.search_offset, delta, threshold),
    )
    _patch_i32(
        out,
        summary.thumb_offset_off,
        _adjust(summary.thumb_offset, delta, threshold),
    )
    _patch_i32(
        out,
        summary.asset_registry_offset_off,
        _adjust(summary.asset_registry_offset, delta, threshold),
    )
    _patch_i32(
        out,
        summary.bulk_data_offset_off,
        summary.bulk_data_offset + delta,
    )
    _patch_i32(
        out,
        summary.preload_offset_off,
        _adjust(summary.preload_offset, delta, threshold),
    )

    # Export map moved with the suffix; its absolute offsets shifted by delta.
    serial_size_off = summary.export_serial_size_off + delta
    serial_offset_off = summary.export_serial_offset_off + delta
    old_serial_offset = struct.unpack_from("<q", out, serial_offset_off)[0]
    _patch_i64(out, serial_offset_off, old_serial_offset + delta)

    if len(out) != len(uasset) + delta:
        raise RuntimeError("internal size mismatch after name rename")
    total = struct.unpack_from("<i", out, summary.total_header_size_off)[0]
    if total != len(out):
        raise RuntimeError(f"TotalHeaderSize ({total}) != file size ({len(out)})")
    return bytes(out)


# Persona uexp: FText display string sits after a 33-char GUID FString.
# TextProperty.Size is 19 bytes before that GUID FString (measured on CPSTemplate_*).
# Top-level PersonaData StructProperty.Size is at offset 16.
_PERSONA_GUID_BODY_LEN = 33
_PERSONA_GUID_FSTR_LEN = 4 + _PERSONA_GUID_BODY_LEN
_PERSONA_SIZE_TO_GUID = 19
_PERSONA_DATA_SIZE_OFF = 16


def replace_uexp_fstrings(uexp: bytes, replacements: Mapping[str, str]) -> tuple[bytes, int]:
    """uexp 内の ASCII FString を置換し、囲んでいる TextProperty / PersonaData の Size も直す。

    表示名だけ縮めると SerialSize は合ってもプロパティ Size が古いまま残り、
    ロード時に Serial size mismatch（Got 巨大 / Expected SerialSize）で落ちる。
    """
    if not replacements:
        return uexp, 0
    items = sorted(replacements.items(), key=lambda kv: len(kv[0]), reverse=True)
    out = bytearray(uexp)
    total_delta = 0
    for old, new in items:
        if old == new:
            continue
        old_bytes = _write_fstring(old)
        new_bytes = _write_fstring(new)
        delta = len(new_bytes) - len(old_bytes)
        positions: list[int] = []
        start = 0
        while True:
            idx = out.find(old_bytes, start)
            if idx < 0:
                break
            positions.append(idx)
            start = idx + len(old_bytes)
        # 後ろから置換して、未処理箇所のオフセットをずらさない
        for idx in reversed(positions):
            guid_start = idx - _PERSONA_GUID_FSTR_LEN
            if guid_start < 0:
                raise ValueError("display FString has no preceding GUID FString")
            guid_len = struct.unpack_from("<i", out, guid_start)[0]
            if guid_len != _PERSONA_GUID_BODY_LEN:
                raise ValueError(
                    f"expected GUID FString length {_PERSONA_GUID_BODY_LEN}, got {guid_len}"
                )
            size_off = guid_start - _PERSONA_SIZE_TO_GUID
            if size_off < 0:
                raise ValueError("TextProperty size field offset is negative")
            old_size = struct.unpack_from("<i", out, size_off)[0]
            new_size = old_size + delta
            if new_size <= 0:
                raise ValueError(f"TextProperty size became non-positive: {new_size}")
            struct.pack_into("<i", out, size_off, new_size)
            out[idx : idx + len(old_bytes)] = new_bytes
            total_delta += delta
    if total_delta != 0:
        old_pd = struct.unpack_from("<i", out, _PERSONA_DATA_SIZE_OFF)[0]
        new_pd = old_pd + total_delta
        if new_pd <= 0:
            raise ValueError(f"PersonaData size became non-positive: {new_pd}")
        struct.pack_into("<i", out, _PERSONA_DATA_SIZE_OFF, new_pd)
    return bytes(out), total_delta


def patch_export_serial_size(uasset: bytes, size_delta: int) -> bytes:
    """Export の SerialSize と BulkDataStartOffset を uexp サイズ変化に合わせて更新する。"""
    if size_delta == 0:
        return uasset
    summary = _parse_summary(uasset)
    out = bytearray(uasset)
    old_size = struct.unpack_from("<q", out, summary.export_serial_size_off)[0]
    _patch_i64(out, summary.export_serial_size_off, old_size + size_delta)
    _patch_i32(
        out,
        summary.bulk_data_offset_off,
        summary.bulk_data_offset + size_delta,
    )
    return bytes(out)


def patch_texture_bulk_offset(uexp: bytes, uasset_size: int, dxt_offset: int = 255) -> bytes:
    """テクスチャ uexp の inline bulk offset を len(uasset)+dxt_offset に書き直す。"""
    bulk_header_offset = dxt_offset - 20
    out = bytearray(uexp)
    struct.pack_into("<q", out, bulk_header_offset + 12, uasset_size + dxt_offset)
    return bytes(out)


def rename_cooked_asset(
    uasset: bytes,
    uexp: bytes,
    name_replacements: Mapping[str, str],
    *,
    uexp_string_replacements: Mapping[str, str] | None = None,
    patch_bulk_offset: bool = False,
    dxt_offset: int = 255,
) -> tuple[bytes, bytes]:
    """名前テーブル（と任意で uexp 文字列）を書き換え、整合するオフセットを更新する。"""
    new_uasset = rename_uasset_names(uasset, name_replacements)
    new_uexp = uexp
    if uexp_string_replacements:
        new_uexp, delta = replace_uexp_fstrings(uexp, uexp_string_replacements)
        new_uasset = patch_export_serial_size(new_uasset, delta)
    if patch_bulk_offset:
        new_uexp = patch_texture_bulk_offset(new_uexp, len(new_uasset), dxt_offset)
    # Final TotalHeaderSize check
    summary = _parse_summary(new_uasset)
    total = struct.unpack_from("<i", new_uasset, summary.total_header_size_off)[0]
    if total != len(new_uasset):
        raise RuntimeError(f"TotalHeaderSize ({total}) != file size ({len(new_uasset)})")
    serial_size = struct.unpack_from("<q", new_uasset, summary.export_serial_size_off)[0]
    if serial_size != len(new_uexp) - 4:
        raise RuntimeError(
            f"Export SerialSize ({serial_size}) != uexp serial ({len(new_uexp) - 4})"
        )
    serial_offset = struct.unpack_from("<q", new_uasset, summary.export_serial_offset_off)[0]
    if serial_offset != len(new_uasset):
        raise RuntimeError(
            f"Export SerialOffset ({serial_offset}) != uasset size ({len(new_uasset)})"
        )
    return new_uasset, new_uexp
