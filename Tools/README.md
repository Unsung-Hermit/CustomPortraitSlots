# Tools (maintainer)

Scripts, frozen exes, `repak`, licenses, and cooked templates.

Templates go under `templates/` (Male / Female / Nonbinary). Each set holds `CPST_Tex` plus a Portrait + Persona pair from Mod Editor mod `CPSTemplate_<Sex>`.

| File | Role |
|---|---|
| `generate_slot.py` / `.exe` | Rename templates → `out/CPS_<Id>/` |
| `bake_portrait.py` / `.exe` | Bake `Resources/portrait.*` into the slot pak |
| `merge_slots.py` / `.exe` | MergeInbox → pack + `PackCatalog.html` |
| `registry_writer.py` | AssetRegistry.bin read/write |
| `uasset_rename.py` | Cooked name-map rename + size fixups |
| `make_placeholder.py` | Builds `assets/Icon128.png` (not in release zip) |
| `freeze_exes.ps1` | Rebuild the three PyInstaller exes |
| `stage_release.ps1` | Stage `dist/CustomPortraitSlots/` for Nexus zip |
