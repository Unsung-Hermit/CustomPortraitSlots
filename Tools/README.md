# Tools

Scripts, frozen exes, `repak`, licenses, and cooked templates live here.

Templates go under `templates/` (Male / Female / Nonbinary sets). Each set holds the texture `CPST_Tex` and a Portrait + Persona pair, cooked from the Mod Editor template mod `CPSTemplate_<Sex>`.

- `generate_slot.py` — rename templates to `CPS_<Id>`, rewrite Tags / AssetRegistry / `target.json`, write `out/CPS_<Id>/`
- `bake_portrait.py` — bake `Resources/portrait.*` into the generated slot pak
- `merge_slots.py` — MergeInbox pack merge (double-click `merge_slots.bat`, no args). Skips unbaked slots, detects Id collisions, keeps each `CPS_<Id>` registry side-by-side, writes `PackCatalog.html`
- `registry_writer.py` — AssetRegistry.bin read/write
- `uasset_rename.py` — cooked name-map rename + TotalHeaderSize / bulk offset fixups
- `make_placeholder.py` — generates the mod folder icon. The shipped file is `assets/Icon128.png`; `generate_slot` copies it into each generated mod
