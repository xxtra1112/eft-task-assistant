# EFT Task Assistant

**A local quest, map and Hideout planning companion for Escape from Tarkov.**

Recognize trader quests from screenshots, track objectives, and organize map locations, keys and upgrade materials. Manage your profile on a PC and scan a QR code for a read-only map on a phone or tablet on the same LAN. No account registration.

[简体中文](README.md) · [Windows downloads](https://github.com/xxtra1112/eft-task-assistant/releases) · [Report an issue](https://github.com/xxtra1112/eft-task-assistant/issues)
[![CI](https://github.com/xxtra1112/eft-task-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/xxtra1112/eft-task-assistant/actions/workflows/ci.yml)

> This source targets the **1.3.0 release candidate**. Only assets actually present on Releases are published downloads. This is an unofficial community tool, not affiliated with Battlestate Games. In-game requirements take precedence.

## Features

- **Screenshot recognition:** authorize the game's screenshot folder on this PC. Local OCR recognizes trader quests and automatically adds matches, with a notification in screenshot order. Missing quests are never automatically deleted.
- **Objective tracking:** independent checkboxes/counters, trader/map filters, collapsible cards, visibility, completion and action undo.
- **Multiple map sources:** switch between Tarkov.dev, EFTarkov and RE3MR with explicit provenance and restrictions. Zoom, pan, fullscreen, background floor selection and visited markers are supported.
- **Routes and companion maps:** route color/width, scoped by profile/source/map/floor; paired read-only phones synchronize routes for supported sources. Tablets use map-left/task-list-right layout.
- **Keys and materials:** genuine quest keys, Hideout prerequisites and combined required/owned/missing material counts. Currency is excluded from the item-piece total.
- **Local persistent saves:** submitted profile preferences and routes stay in the PC's database, with separate datasets, explicit imports, conflict backups and rollback.

## Screenshots

These are existing-version captures of an isolated demo profile, **not full 1.3.0 acceptance evidence**. They contain no personal save or gameplay screenshot. The interface offers Chinese/English and light/dark themes.

![Desktop quest workspace](https://raw.githubusercontent.com/xxtra1112/eft-task-assistant/main/docs/images/desktop-overview-zh.png)
![Tablet companion](https://raw.githubusercontent.com/xxtra1112/eft-task-assistant/main/docs/images/tablet-map-zh.png)
![Phone companion](https://raw.githubusercontent.com/xxtra1112/eft-task-assistant/main/docs/images/mobile-map-zh.png)

## Install and start

1. Download the Windows x64 EXE from [Releases](https://github.com/xxtra1112/eft-task-assistant/releases), or extract the corresponding portable ZIP into a new folder.
2. Run the downloaded or extracted EXE directly. **No Python, Conda or capture helper is needed.**
3. Keep the app running and use the URL printed by the program, normally `http://127.0.0.1:8765/`. Default ports try subsequent ports if busy; explicitly requested conflicting ports fail without stopping another instance.
4. Enter a local profile name and authorize the actual Tarkov screenshots folder. Each player runs the complete application on their own PC.
5. Check recognized quests and select a map. Public catalogs can also be synced/searched/imported manually.

Desktop management binds only to `127.0.0.1`. Builds are unsigned: verify the source and `SHA256SUMS.txt`, and do not disable system protection. Closing the process window or pressing `Ctrl+C` stops the service.

### Screenshots

Take screenshots normally in the game, then authorize its `Screenshots` folder in the PC's Chrome/Edge browser. No hard-coded Windows user directory is assumed, and other devices' files are not read. PNG, JPG/JPEG and WebP are supported; up to 10 recent recognition records are retained.

OCR runs locally, not in cloud AI. Language, capture area, resolution and game UI changes affect matching. Sync the catalog or add a quest manually if needed. A quest missing from a screenshot is not proof of completion.

## Map providers and boundaries

| Provider | Purpose and limits |
| --- | --- |
| **Tarkov.dev** | Default task/map provider, including quest regions, locations, extracts/transits and artwork; Hideout data and item icons still use Tarkov.dev |
| **EFTarkov** | Public Chinese task/map information; only verifiable provider-specific associations, not matching points merely by similar names |
| **RE3MR** | Explicitly linked, policy-permitted original reference artwork for local personal noncommercial desktop viewing only; no calibrated quest coordinates, cross-provider overlays or mobile/LAN image rehosting |

Switching providers does not reimport or overwrite existing quests. Imported records retain their provenance and progress. Unknown points remain explained task contexts rather than invented coordinates; quest covers are not substituted for waypoint photos. PMC, Scav and faction-unconfirmed extracts are distinguished without guessing missing evidence.

Community data can be outdated or incomplete and does not certify every game patch. PvE, regular PvP and seasonal PvP depend on actual source coverage; another mode is not silently substituted. See [provider notes](docs/data-sources.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

### Background cache

Startup preloads all permitted sources with current-map priority. Downloads are bounded to 2 and full-image decoding to 1. Disk storage is capped at 512 MiB with LRU eviction. Cancel, resume and restart have separate status for discovered/cached/newly downloaded/blocked/failed/deferred assets.

**Finishing a pass does not mean every map was downloaded or will remain cached.** Robots failures and HTTP denials are not bypassed, including through old cache data.

```powershell
.\EFTTaskAssistant-v1.3.0-Windows-x64.exe --no-preload
.\EFTTaskAssistant-v1.3.0-Windows-x64.exe --preload-budget-mib 32 --preload-max-assets 1
```

`--no-preload` disables startup preloading only, not on-demand/manual loads. Both budget options accept integers `1..512`, defaulting to 512 MiB and 512 new assets per pass. Batch budgets and disk capacity are separate. See [measured preload evidence](docs/preload-evidence.md).

## Phone / tablet companion

Connect both devices to the same trusted LAN and scan **Mobile map QR code** on the desktop. No second login or certificate download is needed. Codes expire after two minutes and can be used once; paired devices have restricted read-only access and can end their session.

Phones can switch maps/floors, zoom, use immersive view and resize the task sheet; tablets use split layout. See [route synchronization](docs/route-sync.md). RE3MR only provides a source link/restriction notice on the companion, not rehosted original images.

For connection issues, check the LAN and allow the application through Windows Firewall on **private networks** only. Select the appropriate interface address on the PC. Do not expose ports publicly or share pairing codes/sessions with untrusted people.

## Saves, upgrades and rollback

Version 1.3.0 queries the configured Windows Saved Games Known Folder, normally:

```text
%USERPROFILE%\Saved Games\EFTTaskAssistant
```

Check the actual `root` in **Save and cache**. Production and preview channels have separate stable roots. Renaming/moving the EXE or changing CWD/ports does not require a new data directory. Use an absolute `--data-dir` only for a deliberate custom root.

On discovering legacy saves, **check paths/counts and explicitly select a source**. Migration retains originals, backups and a separate dataset; it does not merge nonempty roots or choose by modification time. Imported datasets need explicit next-start selection. Future schemas, invalid databases and discovery failures are reported instead of silently selecting an empty fallback.

Submitted key answers, visibility, collapse state, Hideout plans and material counts are persisted to the PC's profile database and can be read by another local browser; shared routes are server-side too. Screenshot-folder permission, unsent offline route queues and some temporary caches remain in the original browser. Browser-only preferences from an old origin/port must be exported there and explicitly imported; the server cannot recover state never uploaded or exported.

Close the app before backing up the **complete save root**, not individual live SQLite files. Backups can contain screenshots, history and sessions: keep them private. Roll back using the old EXE with its preserved original root; do not point unsupported old binaries at newer schemas, lower schema numbers or delete conflict snapshots. New progress is not automatically copied backward. See [migration, conflicts and rollback](docs/save-data.md).

## Privacy and network access

No online account is required. The app does not read game memory or send screenshots to cloud AI. Synchronization contacts the selected public sources. Tarkov.dev item icons may retry via an image proxy; profile data and screenshots are not sent. Provider/media access rules remain applicable. User databases, runtime caches and original map artwork are not bundled.

Redact usernames, screenshots, paths and personal information before sharing diagnostics. Never publish save databases, pairing tokens or complete browser storage.

## Tested scope and limits

Stage4 isolated checks covered legacy migration, default-path restarts across EXE/CWD changes, same-root locks, preference conflicts, route recovery and one real Reserve original's background cache, display, zoom/fullscreen and simulated offline recovery. Exact final candidate source, artifact size/hash and test results belong to its `BUILD-INFO.json`, `SHA256SUMS.txt` and validation report.

**Physical phones and every map's real original/offline behavior are not tested; not all Windows users or package hosts are covered.** Phone/tablet browser emulation is not physical-device acceptance. This round downloaded only one additional Reserve original. See [evidence](docs/preload-evidence.md); do not interpret it as all-map offline coverage.

## Develop and build

Source use requires Windows x64 and Python 3.11:

```powershell
git clone https://github.com/xxtra1112/eft-task-assistant.git
cd eft-task-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Release builds start from a **clean, fixed commit** with version metadata and pinned Windows dependencies:

```powershell
python -m pip install -r requirements-build.txt
python -m pip check
& "$PWD/build_windows.ps1" -Version 1.3.0
```

Outputs are in `dist`; local and CI builds use the same entry point. Fixed commits/dependencies/process make inputs verifiable, not a promise of byte-identical EXEs across different machines/times. Tests: `python -m pytest -q` and `node --test tests/test_*.cjs`.

CI installs the exact Python patch through `.github/conda-release.yml`, pinning Miniforge and the conda-forge Python build instead of requesting an unavailable setup-python Windows 3.11.17 package. `BUILD-INFO.json` records the complete runtime string, distinguishing distributors such as local Anaconda and CI conda-forge.

CI checks main/PR source; manual candidate artifacts are not releases. Release tags must match version metadata and bilingual notes, and verification gates publication. Formal GitHub publication must also deliver the identical verified package to the confirmed Lanzou Cloud destination and check size/hash. No success link is reported before actual upload. See [release checklist](docs/release-checklist.md).

## License

Original code is [MIT licensed](LICENSE). Maps, trademarks, third-party data and dependencies retain their own terms: **MIT code licensing does not grant unrestricted media rights**. Read [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and verify tasks in-game.

Release packages also include `THIRD_PARTY_LICENSES.txt` with dependency/Python license texts and upstream notices; the identical report is embedded in the EXE. `BUILD-INFO.json` records its hash, and portable checksums cover it. Preserve it when redistributing.
