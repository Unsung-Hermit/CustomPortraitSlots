# CustomPortraitSlots

GitHub / maintainer README. **End users:** open `Guide.html` (the full guide in the Nexus zip). `MergeInbox\README.md` is only a short placement note for that folder.

Toolkit that **adds new pilot portrait slots** for MechWarrior 5: Mercenaries (MW5 Primary Asset types). Companion Optional file for [Custom Player Portrait](https://www.nexusmods.com/mechwarrior5mercenaries/mods/1621) — not CustomPortraitKit (vanilla texture replace).

## Maintainer commands

```bat
Tools\freeze_exes.ps1
Tools\stage_release.ps1
```

`stage_release.ps1` writes `dist\CustomPortraitSlots\` (no root README, no freeze/tests/placeholder). **That tree is tracked in git** so Nexus quarantine reviewers can match the uploaded ZIP to GitHub. Zip the folder contents for Nexus; keep `*.zip` out of the repo.

## Layout

- `Guide.html` — user guide (EN + JA)
- `generate_slot.bat` / `merge_slots.bat`
- `Tools\` — sources, frozen exes, templates, `repak`
- `MergeInbox\` — user packs (gitignored except `README.md`)
- `dist\CustomPortraitSlots\` — staged release tree (**tracked**; same contents as the Nexus ZIP)

---

## 日本語

**本ガイドは `Guide.html`。** Nexus ZIP にルート README は入れない。`MergeInbox\README.md` はそのフォルダ向けの短い配置説明のみ。

この README は GitHub / メンテナ用です。`Tools\stage_release.ps1` が `dist\CustomPortraitSlots\` を組み立てます（ルート README・freeze・test・placeholder は含めない）。**そのツリーはリポジトリで追跡**し、検疫担当が配布 ZIP と GitHub の整合を確認できるようにします。`*.zip` 自体は ignore のままです。
