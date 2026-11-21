"""AssetRegistry.bin の読み書き（MW5 Mod 用、UE 4.26 形式）。

入力は JSON と同じ構造の dict（Header / Unknown / fAssetDatas / keyValuePairs）。
書式は Mod Editor 出力（性別別テンプレ 3 件）とバイト単位で一致することを確認済み。

名前ハッシュは UAssetAPI の CRCGenerator（MIT, Copyright Atenfyr）と同じ式。
出典と著作権表示は THIRD_PARTY_NOTICES.md を参照。
"""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Any

ASSET_KEYS = ("ObjectPath", "PackagePath", "AssetClass", "PackageName", "AssetName")
HEADER_SIZE = 16
# アセット領域の直後に続く 16 バイト（int32 4 + ゼロ 12 バイト）。3 性別で同一。意味は未確認。
GAP_AFTER_ASSETS = bytes.fromhex("04000000") + bytes(12)
MASK32 = 0xFFFFFFFF


def _make_tables() -> tuple[list[int], list[int]]:
    # Strihash 用（MSB 先頭の CRC-32 テーブル、多項式 0x04C11DB7）
    dep: list[int] = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) & MASK32 if c & 0x80000000 else (c << 1) & MASK32
        dep.append(c)
    # StrCrc32 用（反射型 CRC-32 の標準テーブル、多項式 0xEDB88320）
    sb8: list[int] = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
        sb8.append(c)
    return dep, sb8


_TABLE_DEP, _TABLE_SB8 = _make_tables()


def _strihash(text: str) -> int:
    num = 0
    for ch in text:
        c = ord(ch)
        if 97 <= c <= 122:  # ASCII の小文字だけ大文字化
            c -= 32
        num = ((num >> 8) & 0xFFFFFF) ^ _TABLE_DEP[(num ^ c) & 0xFF]
    return num & 0xFFFF


def _strcrc32(text: str) -> int:
    crc = MASK32
    for ch in text:
        c = ord(ch)
        for _ in range(4):  # C# 側と同じく 1 文字あたり 4 回更新（上位バイト、残りは 0）
            crc = ((crc >> 8) ^ _TABLE_SB8[(crc ^ c) & 0xFF]) & MASK32
            c >>= 8
    return (~crc) & 0xFFFF


def generate_hash(name: str) -> int:
    """FName の 4 バイトハッシュ（下位 16bit = NonCase、上位 16bit = Case）。ASCII 専用。"""
    name.encode("ascii")  # 非 ASCII は未対応として例外にする
    return _strihash(name) | (_strcrc32(name) << 16)


def _fstring(s: str) -> bytes:
    raw = s.encode("ascii") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def _names_in_index_order(key_value_pairs: dict[str, int]) -> list[str]:
    indices = sorted(key_value_pairs.values())
    if indices != list(range(len(indices))):
        raise ValueError("keyValuePairs の番号が 0 から連続していません")
    names = [""] * len(indices)
    for name, idx in key_value_pairs.items():
        names[idx] = name
    return names


def renumber_names(model: dict[str, Any]) -> dict[str, int]:
    """keyValuePairs を初出順（各エントリの 5 キー、次にタグのキー）で作り直す。"""
    order: dict[str, int] = {}

    def add(name: str) -> None:
        if name not in order:
            order[name] = len(order)

    for entry in model["fAssetDatas"]:
        for key in ASSET_KEYS:
            add(entry[key])
        for tag in entry["TagAndValue"]:
            add(tag["Item1"])
    return order


def build_registry_bin(model: dict[str, Any]) -> bytes:
    """JSON と同じ構造の dict から AssetRegistry.bin のバイト列を作る。"""
    names = _names_in_index_order(model["keyValuePairs"])
    index = {name: i for i, name in enumerate(names)}
    header = base64.b64decode(model["Header"])
    if len(header) != HEADER_SIZE:
        raise ValueError("Header は 16 バイトの GUID である必要があります")

    def fname(name: str) -> bytes:
        return struct.pack("<ii", index[name], 0)

    assets = model["fAssetDatas"]
    out = bytearray(header)
    out += struct.pack("<i", int(model["Unknown"]))
    out += struct.pack("<q", 0)  # 名前テーブルの位置（後で書き換える）
    out += struct.pack("<i", len(assets))
    for entry in assets:
        for key in ASSET_KEYS:
            out += fname(entry[key])
        out += struct.pack("<i", len(entry["TagAndValue"]))
        for tag in entry["TagAndValue"]:
            out += fname(tag["Item1"]) + _fstring(tag["Item2"])
        chunks = entry["ChunkIDs"]
        out += struct.pack("<i", len(chunks)) + struct.pack(f"<{len(chunks)}i", *chunks)
        out += struct.pack("<I", int(entry["PackageTags"]))
    out += GAP_AFTER_ASSETS
    struct.pack_into("<q", out, 20, len(out))
    out += struct.pack("<i", len(names))
    for name in names:
        out += _fstring(name) + struct.pack("<I", generate_hash(name))
    return bytes(out)


def parse_registry_bin(data: bytes) -> dict[str, Any]:
    """AssetRegistry.bin を JSON と同じ構造の dict に戻す（検算用）。"""
    off = HEADER_SIZE
    unknown, = struct.unpack_from("<i", data, off)
    off += 4
    name_off, = struct.unpack_from("<q", data, off)
    off += 8
    count, = struct.unpack_from("<i", data, off)
    off += 4

    def read_fname(pos: int) -> tuple[int, int]:
        idx, num = struct.unpack_from("<ii", data, pos)
        return idx, num

    def read_fstring(pos: int) -> tuple[str, int]:
        n, = struct.unpack_from("<i", data, pos)
        text = data[pos + 4 : pos + 4 + n - 1].decode("ascii")
        return text, pos + 4 + n

    raw_assets = []
    for _ in range(count):
        fnames = []
        for _key in ASSET_KEYS:
            fnames.append(read_fname(off))
            off += 8
        tag_count, = struct.unpack_from("<i", data, off)
        off += 4
        tags = []
        for _ in range(tag_count):
            key = read_fname(off)
            off += 8
            text, off = read_fstring(off)
            tags.append((key, text))
        chunk_count, = struct.unpack_from("<i", data, off)
        off += 4
        chunks = list(struct.unpack_from(f"<{chunk_count}i", data, off))
        off += 4 * chunk_count
        flags, = struct.unpack_from("<I", data, off)
        off += 4
        raw_assets.append((fnames, tags, chunks, flags))
    if data[off : off + len(GAP_AFTER_ASSETS)] != GAP_AFTER_ASSETS:
        raise ValueError("アセット領域の後の固定 16 バイトが想定と異なります")
    off += len(GAP_AFTER_ASSETS)
    if off != name_off:
        raise ValueError(f"名前テーブルの位置が一致しません: {off} != {name_off}")
    name_count, = struct.unpack_from("<i", data, off)
    off += 4
    names: list[str] = []
    hashes: list[int] = []
    for _ in range(name_count):
        text, off = read_fstring(off)
        hashes.append(struct.unpack_from("<I", data, off)[0])
        off += 4
        names.append(text)
    if off != len(data):
        raise ValueError("名前テーブルの後に余分なバイトがあります")
    for text, value in zip(names, hashes):
        if generate_hash(text) != value:
            raise ValueError(f"名前ハッシュが一致しません: {text}")

    def name_of(fname: tuple[int, int]) -> str:
        idx, num = fname
        if num != 0:
            raise ValueError("FName の number が 0 以外（未対応）")
        return names[idx]

    assets = []
    for fnames, tags, chunks, flags in raw_assets:
        entry: dict[str, Any] = {key: name_of(fn) for key, fn in zip(ASSET_KEYS, fnames)}
        entry["TagAndValue"] = [{"Item1": name_of(k), "Item2": v} for k, v in tags]
        entry["ChunkIDs"] = chunks
        entry["PackageTags"] = flags
        assets.append(entry)
    return {
        "Header": base64.b64encode(data[:HEADER_SIZE]).decode("ascii"),
        "Unknown": unknown,
        "fAssetDatas": assets,
        "keyValuePairs": {name: i for i, name in enumerate(names)},
    }


def load_model(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
