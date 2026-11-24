# CustomPortraitSlots

GitHub / maintainer README. **End users:** open `Guide.html` (the full guide in the Nexus zip). `MergeInbox\README.md` is only a short placement note for that folder.

Toolkit that **adds new pilot portrait slots** for MechWarrior 5: Mercenaries (MW5 Primary Asset types). Companion Optional file for [Custom Player Portrait](https://www.nexusmods.com/mechwarrior5mercenaries/mods/1621) — not CustomPortraitKit (vanilla texture replace).

## Maintainer commands

```bat
Tools\freeze_exes.ps1
Tools\stage_release.ps1
```

`stage_release.ps1` writes `dist\CustomPortraitSlots\` (no root README, no freeze/tests/placeholder). **That tree is tracked in git** so Nexus quarantine reviewers can match the uploaded ZIP to GitHub. Zip that folder itself for Nexus (`CustomPortraitSlots\` at the ZIP root, same as CustomPortraitKit); keep `*.zip` out of the repo.

## Layout

- `Guide.html` — user guide (EN + JA)
- `generate_slot.bat` / `merge_slots.bat`
- `Tools\` — sources, frozen exes, templates, `repak`
- `MergeInbox\` — user packs (gitignored except `README.md`)
- `dist\CustomPortraitSlots\` — staged release tree (**tracked**; same contents as the Nexus ZIP)

---

## For Nexus / quarantine reviewers

Full source for this toolkit is this GitHub repository (root). The uploaded Nexus Optional archive (`CustomPortraitSlots.zip`) is intended to match the tracked staged tree:

[`dist/CustomPortraitSlots/`](dist/CustomPortraitSlots/)

End-user tool Python sources are in that tree (and in the ZIP). Maintainer build scripts (`Tools\freeze_exes.ps1`, `Tools\stage_release.ps1`, etc.) live at the repo root.

### What this archive is

A Windows-only local toolkit. Workflow: generate a slot folder → put an image in `Resources` → run `bake_portrait.bat` → optionally merge baked slots via `MergeInbox` → enable the mod and restart the game.

### Contents (high level)

```
CustomPortraitSlots\Guide.html
CustomPortraitSlots\generate_slot.bat
CustomPortraitSlots\merge_slots.bat
CustomPortraitSlots\MergeInbox\README.md
CustomPortraitSlots\Tools\bake_portrait.exe
CustomPortraitSlots\Tools\bake_portrait.py
CustomPortraitSlots\Tools\generate_slot.exe
CustomPortraitSlots\Tools\generate_slot.py
CustomPortraitSlots\Tools\merge_slots.exe
CustomPortraitSlots\Tools\merge_slots.py
CustomPortraitSlots\Tools\registry_writer.py
CustomPortraitSlots\Tools\uasset_rename.py
CustomPortraitSlots\Tools\THIRD_PARTY_NOTICES.md
CustomPortraitSlots\Tools\repak.exe
CustomPortraitSlots\Tools\repak_LICENSE-APACHE.txt
CustomPortraitSlots\Tools\repak_LICENSE-MIT.txt
CustomPortraitSlots\Tools\assets\Icon128.png
CustomPortraitSlots\Tools\templates\...   (Female / Male / Nonbinary cooked templates + AssetRegistry.json)
```

`Tools\templates\` holds cooked Unreal Engine assets created in the MW5 Mod Editor (template mods `CPSTemplate_Female` / `Male` / `Nonbinary`). Local patch templates only. `Guide.html` is an offline HTML user guide (no remote content). `PackCatalog.html` is generated later inside merged pack mods, not in this toolkit zip.

Author-only rebuild scripts are **not** in the ZIP / not under `dist/CustomPortraitSlots/`. They live at the repo root (`Tools\freeze_exes.ps1`, `Tools\stage_release.ps1`, `Tools\make_placeholder.py`, `Tools\test_*.py`).

### What each helper tool does

**generate_slot.bat** — Thin launcher. Passes arguments to `Tools\generate_slot.exe` (or `generate_slot.py` if the exe is missing). No network I/O in the batch file.

**Tools\generate_slot.exe** — PyInstaller one-file build from `generate_slot.py` (+ `registry_writer.py`, `uasset_rename.py`). Copies cooked templates from `Tools\templates\<Sex>\`, renames assets to `CPS_{Id}`, rewrites Tags / AssetRegistry / `target.json` / `mod.json`, writes `out\CPS_{Id}\` on disk. Does not download anything.

**Tools\bake_portrait.exe** — PyInstaller one-file build from `bake_portrait.py`. Copied into each generated mod folder. Loads local `Resources\portrait.(png|jpg|jpeg)`, converts to 512×512 DXT5, patches the cooked template `.uexp`, then runs local `Tools\repak.exe` to rebuild that mod’s `.pak`.

**merge_slots.bat / Tools\merge_slots.exe** — PyInstaller one-file build from `merge_slots.py` (+ bake / generate helpers). Double-click with no arguments. Scans `MergeInbox\<PackName>\` for baked `CPS_*` folders, packs them into one mod under `out\`, writes `PackCatalog.html`. Local disk only.

**Tools\repak.exe** — Third-party Unreal `.pak` CLI. On the author’s machine, `repak --version` prints `repak_cli 0.2.3`. Obtained from the public release [trumank/repak v0.2.3](https://github.com/trumank/repak/releases/tag/v0.2.3) and not modified. MIT / Apache-2.0 license texts are included. Used only as a local CLI for packing and listing `.pak` files.

### Network

`generate_slot.py` / `registry_writer.py` / `uasset_rename.py` import only the Python standard library plus local helpers. `bake_portrait.py` and `merge_slots.py` import the standard library plus third-party Pillow and etcpak (imported inside functions where used). The application source contains no download, upload, socket, HTTP client, or auto-update logic.

The built `.exe` files may still contain unused standard-library modules capable of network communication, because PyInstaller can bundle modules that the app does not call. The claim above is limited to the applications’ own source: it does not implement network functionality.

### How the .exe files were built

```bat
powershell -File Tools\freeze_exes.ps1
powershell -File Tools\stage_release.ps1
```

These do **not** guarantee a bit-for-bit identical rebuild or matching SHA-256 hashes. Equivalent PyInstaller one-file flags are in `Tools\freeze_exes.ps1` (`bake_portrait`: `--collect-all etcpak --collect-all archspec` + PIL hidden-imports; `generate_slot`: hidden-imports for `registry_writer` / `uasset_rename`; `merge_slots`: bake + generate hidden-imports + Pillow / etcpak collect-all).

Author build environment (at build time; a rebuild may differ):

- Python 3.11.9
- PyInstaller 6.22.3
- Pillow 12.2.0
- etcpak 0.9.15

`archspec` is a dependency of etcpak; `bake_portrait.py` does not import it directly. `--collect-all` is used as a precaution. `generate_slot.exe` does not need Pillow / etcpak.

Archive-level SHA-256 and VirusTotal links are provided in the Nexus support email for each upload, not hard-coded here (they change every package).

---

## 日本語

**本ガイドは `Guide.html`。** Nexus ZIP にルート README は入れない。`MergeInbox\README.md` はそのフォルダ向けの短い配置説明のみ。

この README は GitHub / メンテナ用です。`Tools\stage_release.ps1` が `dist\CustomPortraitSlots\` を組み立てます（ルート README・freeze・test・placeholder は含めない）。**そのツリーはリポジトリで追跡**し、検疫担当が配布 ZIP と GitHub の整合を確認できるようにします。Nexus 用 ZIP はフォルダごと固める（ZIP 内トップが `CustomPortraitSlots\`。Kit と同じ）。`*.zip` 自体は ignore のままです。

Nexus 検疫向けの詳細（中身一覧・各ツール・ネットワーク・ビルド）は上の **For Nexus / quarantine reviewers** にあります。サポート依頼メールは短くし、ソースとビルド手順は本リポジトリを指します。
