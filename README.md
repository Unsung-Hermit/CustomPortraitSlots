# CustomPortraitSlots

English / [日本語](#日本語)

Toolkit that **adds new pilot portrait slots** for MechWarrior 5: Mercenaries (MW5 Primary Asset types). Companion Optional file for [Custom Player Portrait](https://www.nexusmods.com/mechwarrior5mercenaries/mods/1621).

This is **not** CustomPortraitKit (vanilla texture replace) and **not** an update to Custom Player Portrait.

## Status

`generate_slot` / `bake_portrait` / `merge_slots` are available. Freeze / Nexus packaging still pending.

## Requirements

- Windows
- In-game: **RollCall** or **Pilot Overhaul Eternal** (do not assume both together)

## Planned usage

1. `.\generate_slot.bat <Id> -Sex Female` → `out\CPS_<Id>\`
2. Put `Resources\portrait.png` (or `.jpg` / `.jpeg`), run `bake_portrait.bat`, restart the game
3. To pack many slots: put baked `CPS_*` folders under `MergeInbox\<PackName>\`, double-click `merge_slots.bat`

See `Guide.html` when available.

## GitHub

This folder is the repository root. Remote / publish settings are maintained by the maintainer.

---

## 日本語

MechWarrior 5: Mercenaries 向けに、**新しいポートレートスロットを追加**するツールキット（MW5 Primary Asset 型）。[Custom Player Portrait](https://www.nexusmods.com/mechwarrior5mercenaries/mods/1621) の Optional 姉妹成果物です。

**CustomPortraitKit（既存テクスチャ差し替え）ではありません。** Custom Player Portrait 本体の更新でもありません。

## 状態

`generate_slot` / `bake_portrait` / `merge_slots` は利用可能。freeze / Nexus 梱包は未着手。

## 必要なもの

- Windows
- ゲーム側: **RollCall** または **Pilot Overhaul Eternal**（併用は前提にしない）

## 予定フロー

1. `.\generate_slot.bat <Id> -Sex Female` → `out\CPS_<Id>\`
2. `Resources\portrait.png`（または `.jpg` / `.jpeg`）を置き、`bake_portrait.bat` → 再起動
3. まとめる場合: bake 済み `CPS_*` を `MergeInbox\<PackName>\` に入れ、`merge_slots.bat` をダブルクリック

詳細は `Guide.html`（準備中）。

## GitHub

このフォルダがリポジトリルートです。リモートと公開設定はメンテナが行います。
