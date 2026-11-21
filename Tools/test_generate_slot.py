"""generate_slot / uasset_rename の検算。

実行: Tools フォルダで python -m unittest test_generate_slot -v
"""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

import bake_portrait as bake
import generate_slot as gen
import registry_writer as rw
import uasset_rename as ua

TOOLS = Path(__file__).resolve().parent
TEMPLATES = TOOLS / "templates"


class IdValidationTests(unittest.TestCase):
    def test_accepts_my_ace_01(self) -> None:
        gen.validate_id("My_Ace_01")

    def test_rejects_hyphen(self) -> None:
        with self.assertRaises(ValueError):
            gen.validate_id("My-Ace_01")

    def test_rejects_leading_digit(self) -> None:
        with self.assertRaises(ValueError):
            gen.validate_id("1Ace")

    def test_rejects_cpst_prefix(self) -> None:
        with self.assertRaises(ValueError):
            gen.validate_id("CPST_Test")


class RenameRoundTripTests(unittest.TestCase):
    def test_female_texture_total_header_and_bulk(self) -> None:
        base = TEMPLATES / "Female"
        uasset = (base / "CPST_Tex.uasset").read_bytes()
        uexp = (base / "CPST_Tex.uexp").read_bytes()
        reps = gen.build_name_replacements(
            "Female", "CPS_My_Ace_01", "My_Ace_01", "PO_My_Ace_01", "My_Ace_01_Template"
        )
        new_u, new_e = ua.rename_cooked_asset(
            uasset, uexp, reps, patch_bulk_offset=True
        )
        bake.check_uasset_size(new_u, "My_Ace_01")
        bake.validate_texture_uexp(new_e)
        offset = struct.unpack_from("<q", new_e, bake.BULK_HEADER_OFFSET + 12)[0]
        self.assertEqual(offset, len(new_u) + bake.DXT_OFFSET)
        self.assertIn(b"/CPS_My_Ace_01/UI/Textures/Pilots/My_Ace_01\x00", new_u)
        self.assertNotIn(b"CPST_Tex", new_u)
        self.assertNotIn(b"CPSTemplate_Female", new_u)


class GenerateSlotTests(unittest.TestCase):
    def test_generate_my_ace_01_female(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cps_gen_") as tmp:
            dest = gen.generate("My_Ace_01", "Female", Path(tmp), force=False)
            self.assertEqual(dest.name, "CPS_My_Ace_01")
            target = json.loads((dest / "Tools" / "target.json").read_text(encoding="utf-8"))
            for key in bake.REQUIRED_TARGET_KEYS:
                self.assertTrue(target.get(key), key)
            self.assertEqual(target["id"], "My_Ace_01")
            self.assertEqual(target["sex"], "Female")
            self.assertEqual(target["plugin"], "CPS_My_Ace_01")
            self.assertEqual(target["texture"], "My_Ace_01")
            self.assertEqual(target["portrait"], "PO_My_Ace_01")
            self.assertEqual(target["persona"], "My_Ace_01_Template")
            self.assertEqual(target["contentPath"], "UI/Textures/Pilots/My_Ace_01")
            self.assertEqual(
                target["gamePath"],
                "/CPS_My_Ace_01/UI/Textures/Pilots/My_Ace_01.My_Ace_01",
            )

            cooked = dest / "Tools" / "cooked"
            for name in (
                target["texture"],
                target["portrait"],
                target["persona"],
            ):
                ua_path = cooked / f"{name}.uasset"
                ue_path = cooked / f"{name}.uexp"
                self.assertTrue(ua_path.is_file(), name)
                self.assertTrue(ue_path.is_file(), name)
                bake.check_uasset_size(ua_path.read_bytes(), name)

            tex_u = (cooked / f"{target['texture']}.uasset").read_bytes()
            tex_e = (cooked / f"{target['texture']}.uexp").read_bytes()
            bake.validate_texture_uexp(tex_e)
            bulk = struct.unpack_from("<q", tex_e, bake.BULK_HEADER_OFFSET + 12)[0]
            self.assertEqual(bulk, len(tex_u) + bake.DXT_OFFSET)

            persona_uexp = (cooked / f"{target['persona']}.uexp").read_bytes()
            self.assertIn(b"My_Ace_01", persona_uexp)
            self.assertNotIn(b"CPS Template Female", persona_uexp)
            # PersonaData StructProperty.Size must shrink with display-name FStrings
            # (533 -> 503 for Female "CPS Template Female" -> "My_Ace_01" x3).
            self.assertEqual(struct.unpack_from("<i", persona_uexp, 16)[0], 503)

            reg = (
                dest
                / "Tools"
                / "pak_template"
                / "MW5Mercs"
                / "Plugins"
                / "CPS_My_Ace_01"
                / "AssetRegistry.bin"
            ).read_bytes()
            model = rw.parse_registry_bin(reg)
            self.assertEqual(len(model["fAssetDatas"]), 3)
            names = {e["AssetName"] for e in model["fAssetDatas"]}
            self.assertEqual(names, {"My_Ace_01", "PO_My_Ace_01", "My_Ace_01_Template"})

            tags = (
                dest
                / "Tools"
                / "pak_template"
                / "MW5Mercs"
                / "Config"
                / "Tags"
                / "CPS_My_Ace_01Tags.ini"
            ).read_text(encoding="utf-8")
            self.assertIn('Tag="Portrait.CPS"', tags)

            mod = json.loads((dest / "mod.json").read_text(encoding="utf-8"))
            self.assertEqual(mod["displayName"], "Custom Portrait (My_Ace_01)")
            self.assertEqual(mod["gameVersion"], "1.15.399")
            self.assertEqual(mod["defaultLoadOrder"], 20)
            self.assertEqual(mod["manifest"], [])
            self.assertTrue((dest / "Resources" / "Icon128.png").is_file())
            self.assertTrue((dest / "bake_portrait.bat").is_file())
            self.assertTrue((dest / "Tools" / "bake_portrait.py").is_file())


if __name__ == "__main__":
    unittest.main()
