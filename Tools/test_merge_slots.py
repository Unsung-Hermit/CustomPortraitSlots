"""merge_slots の検算。

実行: Tools フォルダで python -m unittest test_merge_slots -v
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import merge_slots as ms

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
TESTPACK = ROOT / "MergeInbox" / "TestPack"


class CollisionTests(unittest.TestCase):
    def test_case_insensitive_id_collision(self) -> None:
        a = ms.SlotInfo(
            folder=Path("a"),
            target={
                "id": "My_Ace_01",
                "sex": "Female",
                "plugin": "CPS_My_Ace_01",
                "texture": "My_Ace_01",
                "portrait": "PO_My_Ace_01",
                "persona": "My_Ace_01_Template",
            },
            pak_path=Path("x.pak"),
            tags_text=ms.TAGS_INI,
        )
        b = ms.SlotInfo(
            folder=Path("b"),
            target={
                "id": "my_ace_01",
                "sex": "Male",
                "plugin": "CPS_my_ace_01",
                "texture": "my_ace_01",
                "portrait": "PO_my_ace_01",
                "persona": "my_ace_01_Template",
            },
            pak_path=Path("y.pak"),
            tags_text=ms.TAGS_INI,
        )
        with self.assertRaises(RuntimeError) as ctx:
            ms.detect_collisions([a, b])
        self.assertIn("collision", str(ctx.exception).lower())


class CatalogCommandTests(unittest.TestCase):
    def test_command_matches_target_sex(self) -> None:
        for sex in ("Female", "Male", "Nonbinary"):
            cmd = f".\\generate_slot.bat SampleId -Sex {sex}"
            self.assertIn(f"-Sex {sex}", cmd)


@unittest.skipUnless(TESTPACK.is_dir(), "MergeInbox/TestPack not present")
class MergeTestPackTests(unittest.TestCase):
    def test_merge_testpack_and_catalog(self) -> None:
        # Ensure at least one baked slot exists
        baked = list((TESTPACK).glob("CPS_*/Paks/*.pak"))
        self.assertGreaterEqual(len(baked), 1, "TestPack needs baked paks")

        with tempfile.TemporaryDirectory(prefix="cps_merge_out_") as tmp:
            old_out = ms.OUT_ROOT
            try:
                ms.OUT_ROOT = Path(tmp) / "out"
                result = ms.merge_one_pack(TESTPACK)
                self.assertTrue(result.ok, result.message)
                self.assertIsNotNone(result.out_dir)
                assert result.out_dir is not None
                pak = result.out_dir / "Paks" / "TestPack.pak"
                catalog = result.out_dir / "PackCatalog.html"
                mod_json = json.loads(
                    (result.out_dir / "mod.json").read_text(encoding="utf-8")
                )
                self.assertTrue(pak.is_file())
                self.assertTrue(catalog.is_file())
                self.assertEqual(mod_json["displayName"], "TestPack")
                self.assertEqual(mod_json["gameVersion"], "1.15.399")

                html = catalog.read_text(encoding="utf-8")
                for slot_id in result.slots:
                    target = json.loads(
                        (
                            TESTPACK / f"CPS_{slot_id}" / "Tools" / "target.json"
                        ).read_text(encoding="utf-8")
                    )
                    cmd = f".\\generate_slot.bat {target['id']} -Sex {target['sex']}"
                    self.assertIn(cmd, html)
                    self.assertEqual(target["id"], slot_id)
                # No game/plugin paths in the catalog body
                self.assertNotRegex(html, r"/CPS_")
                self.assertIsNone(re.search(r"UI/Textures/Pilots", html))
            finally:
                ms.OUT_ROOT = old_out

    def test_unbaked_slot_skipped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cps_merge_skip_") as tmp:
            pack = Path(tmp) / "SkipPack"
            pack.mkdir()
            # Copy one baked slot
            src = next(TESTPACK.glob("CPS_*"))
            dest = pack / src.name
            shutil.copytree(src, dest)
            # Add an unbaked sibling (target.json but empty Paks)
            unbaked = pack / "CPS_Unbaked_01"
            unbaked.mkdir()
            (unbaked / "Tools").mkdir()
            (unbaked / "Paks").mkdir()
            target = {
                "id": "Unbaked_01",
                "sex": "Female",
                "plugin": "CPS_Unbaked_01",
                "texture": "Unbaked_01",
                "portrait": "PO_Unbaked_01",
                "persona": "Unbaked_01_Template",
                "contentPath": "UI/Textures/Pilots/Unbaked_01",
                "gamePath": "/CPS_Unbaked_01/UI/Textures/Pilots/Unbaked_01.Unbaked_01",
                "uexpLayout": "CPS_DXT5_512",
            }
            (unbaked / "Tools" / "target.json").write_text(
                json.dumps(target, indent=2) + "\n", encoding="utf-8"
            )
            tags = (
                unbaked
                / "Tools"
                / "pak_template"
                / "MW5Mercs"
                / "Config"
                / "Tags"
            )
            tags.mkdir(parents=True)
            (tags / "CPS_Unbaked_01Tags.ini").write_text(ms.TAGS_INI, encoding="utf-8")

            old_out = ms.OUT_ROOT
            try:
                ms.OUT_ROOT = Path(tmp) / "out"
                result = ms.merge_one_pack(pack)
                self.assertTrue(result.ok, result.message)
                self.assertTrue(
                    any("Unbaked_01" in s and "unbaked" in s.lower() for s in result.skipped)
                )
                self.assertNotIn("Unbaked_01", result.slots)
                html = (result.out_dir / "PackCatalog.html").read_text(encoding="utf-8")
                self.assertNotIn("Unbaked_01", html)
            finally:
                ms.OUT_ROOT = old_out


if __name__ == "__main__":
    unittest.main()
