"""registry_writer の検算。

実行: Tools フォルダで python -m unittest test_registry_writer -v

- 既知のハッシュ値（Mod Editor 出力の bin から採取）と一致すること
- テンプレの AssetRegistry.json を bin に書き出し、読み戻して内容が一致すること
- keyValuePairs を初出順に作り直すと、テンプレの番号と一致すること
- 環境変数 CPS_EDITOR_REGISTRY_DIR を指定した場合、Editor 版 bin とバイト単位で一致すること
  （例: %TEMP%\\cps_ar_conv\\Female\\AssetRegistry.bin を含むフォルダ構成を指す）
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

import registry_writer as rw

TOOLS = Path(__file__).resolve().parent
TEMPLATES = TOOLS / "templates"
SEXES = ("Female", "Male", "Nonbinary")

# Mod Editor 出力の bin から採取した既知値（名前, 下位16bit, 上位16bit）
KNOWN_HASHES = [
    ("MWPersonaAsset", 0xB3FD, 0xEB98),
    ("Texture2D", 0xFDFE, 0xD140),
    ("PrimaryAssetType", 0x3C1C, 0x70D8),
    ("NativeClass", 0x1D2B, 0x79FB),
    ("/CPSTemplate_Female", 0x2352, 0xADDD),
]


class HashTests(unittest.TestCase):
    def test_tables_match_known_entries(self) -> None:
        self.assertEqual(rw._TABLE_DEP[1], 0x04C11DB7)
        self.assertEqual(rw._TABLE_SB8[1], 0x77073096)

    def test_known_hashes(self) -> None:
        for name, low, high in KNOWN_HASHES:
            with self.subTest(name=name):
                self.assertEqual(rw.generate_hash(name), low | (high << 16))

    def test_non_ascii_is_rejected(self) -> None:
        with self.assertRaises(UnicodeEncodeError):
            rw.generate_hash("テスト")


class RoundTripTests(unittest.TestCase):
    def test_templates_round_trip(self) -> None:
        for sex in SEXES:
            with self.subTest(sex=sex):
                model = rw.load_model(TEMPLATES / sex / "AssetRegistry.json")
                data = rw.build_registry_bin(model)
                back = rw.parse_registry_bin(data)
                self.assertEqual(back["Header"], model["Header"])
                self.assertEqual(back["Unknown"], model["Unknown"])
                self.assertEqual(back["fAssetDatas"], model["fAssetDatas"])
                self.assertEqual(back["keyValuePairs"], model["keyValuePairs"])

    def test_renumber_matches_templates(self) -> None:
        for sex in SEXES:
            with self.subTest(sex=sex):
                model = rw.load_model(TEMPLATES / sex / "AssetRegistry.json")
                self.assertEqual(rw.renumber_names(model), model["keyValuePairs"])


class EditorBinTests(unittest.TestCase):
    def test_editor_bin_identical(self) -> None:
        base = os.environ.get("CPS_EDITOR_REGISTRY_DIR")
        if not base:
            self.skipTest("CPS_EDITOR_REGISTRY_DIR が未指定")
        for sex in SEXES:
            with self.subTest(sex=sex):
                model = rw.load_model(TEMPLATES / sex / "AssetRegistry.json")
                expected = (Path(base) / sex / "AssetRegistry.bin").read_bytes()
                self.assertEqual(rw.build_registry_bin(model), expected)


if __name__ == "__main__":
    unittest.main()
