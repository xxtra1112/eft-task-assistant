# EFT Task Assistant

**A quest, map, and Hideout planning companion for Escape from Tarkov.** Recognize trader quests from screenshots, track each objective, plan quest keys and Hideout materials, and view quest locations on maps.

[简体中文](README.md) · [Download for Windows](https://github.com/xxtra1112/eft-task-assistant/releases/latest) · [Report a problem](https://github.com/xxtra1112/eft-task-assistant/issues)

> This is a community-made tool. It is not affiliated with Battlestate Games and is not an official client or data service. Always verify requirements in the game.

## Contents

- [Features](#features)
- [Install and run](#install-and-run)
- [First-time setup](#first-time-setup)
- [Screenshot recognition](#screenshot-recognition)
- [Quest list and maps](#quest-list-and-maps)
- [Hideout planning](#hideout-planning)
- [LAN access and privacy](#lan-access-and-privacy)
- [Back up your data](#back-up-your-data)
- [Troubleshooting](#troubleshooting)
- [Development and build](#development-and-build)
- [Data sources and license](#data-sources-and-license)

## Features

- **Screenshot recognition:** Import screenshots from a folder you authorize, identify trader quest lists, and match quests. Matched quests are added to your list automatically, with a record of what was recognized.
- **Quest tracking:** Filter by trader or map, check off individual objectives or track item counts, collapse quest cards, toggle hidden quests, add or remove quests manually, and undo recent actions.
- **Key checklist:** Summarize keys required by tracked quests, see which quests need them, and review prompts when new keys appear.
- **Quest maps:** View objectives, source images, and location notes. Switch map backgrounds by floor, zoom and pan, mark points as visited, and draw routes. Changing floors only changes the background; markers for all floors remain visible.
- **Hideout planning:** Select stations and target levels, include prerequisite stations automatically, and total required materials while tracking what you already own.
- **Player settings:** Use separate player accounts and PvE, regular PvP, or season PvP profiles. The interface supports Chinese and English, plus light and dark themes.

## Install and run

### Windows executable (recommended)

1. Open [GitHub Releases](https://github.com/xxtra1112/eft-task-assistant/releases/latest).
2. Download and run `EFTTaskAssistant-v1.0.0-Windows-x64.exe`.
3. The app starts a local web server and attempts to open your browser. Create the administrator account on this computer the first time you run it.

The default address is `http://127.0.0.1:8765/`. If the port is busy, the app tries ports `8766` through `8785`; use the address and port printed in the launch window. Keep that window open while using the app. Closing it stops the service. The prebuilt executable does not require Python or Conda.

The executable is not code-signed, so Windows may show an unknown-publisher warning. Download it only from this project's Releases page.

### Run from source

You need Windows, [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html), and Python 3.11. In PowerShell, run:

~~~powershell
git clone https://github.com/xxtra1112/eft-task-assistant.git
cd eft-task-assistant
conda create -n eft-task-assistant python=3.11 pip
conda activate eft-task-assistant
python -m pip install -r requirements.txt
python main.py
~~~

Internet access is needed for the initial dependency installation and online catalog sync. Keep the terminal open while the service is running; press `Ctrl+C` to stop it.

## First-time setup

1. **Create an account.** The first account becomes the administrator and must be created on the computer hosting the service, using its local address. Player names must be 1–32 characters with no spaces; passwords must be at least 8 characters. Other players can register afterward.
2. **Create a game profile.** Choose PvE, regular PvP, or season PvP. Quest progress is stored separately for each profile.
3. **Load quest data.** Expand **Quest List → Import from EFTarkov quest catalog** and select **Sync public catalog**. Once synced, search, preview, and import quests. Online data may change or be temporarily unavailable.
4. **Choose your screenshot folder.** Sign in, select **Choose screenshot folder**, choose the game's actual `Screenshots` directory, and grant the browser permission when prompted.
5. **Start planning.** Review the quest list, filter by map, check your keys, and choose Hideout stations and target levels.

## Screenshot recognition

The app reads screenshots from the folder selected in the **browser's device**. It does not guess or read a hard-coded Windows user path. Choose the `Screenshots` folder used by your Escape from Tarkov installation. Supported image formats are PNG, JPG/JPEG, and WebP.

For local use at `127.0.0.1`, the latest Chrome or Edge is recommended. If the browser supports persistent directory access, the app imports recent screenshots and watches for new ones. If the browser does not support that feature—or you open the app over a LAN address—you may need to select the folder again to scan it. Changing browsers, clearing site data, or switching player accounts may also require new permission.

Recognition results list the quests matched in each screenshot. Matched quests are automatically added to the selected profile. OCR runs locally on the computer hosting the assistant; screenshots are not sent to a cloud AI model. Recognition can be affected by the game language, screenshot crop, resolution, and interface changes, so review the results.

**A quest missing from a screenshot is not considered complete.** Quests are never automatically completed or removed just because they are absent from an image. Manage them manually in the quest list. Search the public catalog or add a quest manually if recognition misses it.

## Quest list and maps

- Each quest objective can be checked off individually. Use a counter for objectives requiring multiple items. A quest is completed automatically when all required objectives are complete.
- Filter the list by trader or map. The quest list and map stay in sync when you change the map filter.
- Collapsing a quest saves space. Hidden quests remain in the profile and can be shown with **Toggle hidden**. Clearing the quest list removes quests from the current profile, so use it carefully.
- The map's side panel groups locations and objectives by quest. Select a marker to view its location details; right-click a marker to toggle its visited status. Maps support zoom, pan, fullscreen, and route drawing.
- Map backgrounds and location data come from public sources and may be incomplete or differ from the current game version. Verify destinations and required items before a raid.

## Hideout planning

In **Upgrade Targets**, select Hideout stations and target levels. A target may be the station's current level. Prerequisite stations are selected automatically. **Upgrade Materials** totals the requirements for the selected plan and lets you enter owned quantities to see what's still missing. Roubles and euros are excluded from the item count.

**Reset levels** clears station selections and target levels. **Reset owned quantities** clears the material counts you entered. These actions are separate.

## LAN access and privacy

By default, the service accepts connections only from the computer running it. To allow other devices on a trusted local network, set the host before launching the app in PowerShell:

~~~powershell
$env:EFT_TASK_ASSISTANT_HOST = "0.0.0.0"
& "$PWD/EFTTaskAssistant-v1.0.0-Windows-x64.exe"
~~~

Run `ipconfig` on the host computer to find its LAN IPv4 address. On another device, open `http://<host-LAN-IP>:<port-shown-at-startup>/`. If it does not connect, check that Windows Firewall allows the app on a **Private network**. Do not forward the port to the public internet.

LAN mode uses unencrypted HTTP. Do not use it on an untrusted public network or with a sensitive password; others on the network could intercept passwords or session information. Each device should choose its own local game screenshot folder in its browser. The images are sent to the computer hosting the assistant for recognition; other devices do not need—and cannot use—the host's path to access their local game files.

Passwords are stored as PBKDF2 hashes. Screenshot recognition, quests, and profile data are stored on the host computer and isolated by player account. Up to 10 recent screenshot records are retained. Screenshot folder permission stays in the local browser.

Hideout upgrade targets, owned material counts, quest and key visibility settings, map route drawings, and other interface preferences are stored in the current browser's local storage and scoped to the player account and profile. They do not sync to other browsers or devices and are not included in the server data-folder backup below. Clearing browser site data may erase them.

Screenshots are not sent to cloud AI; when syncing quest, map, or Hideout data, the app accesses public sources such as [EFTarkov](https://www.eftarkov.com/) and [Tarkov.dev](https://tarkov.dev/).

## Back up your data

By default, app data is stored in `%LOCALAPPDATA%/EFTTaskAssistant`. It includes accounts, quests, profiles, and recognition records. To back up or move your data:

1. Close the app and make sure the service has stopped.
2. Copy the entire `EFTTaskAssistant` folder to a safe location.
3. To restore it, put the folder back in the same data directory and restart the app.

Do not copy SQLite database files while the service is running; the backup may be incomplete. Backups may contain personal screenshots and game history, so keep them private.

## Troubleshooting

**The page did not open.** Make sure the launch window is still running and manually open the `127.0.0.1` address printed there. If the default port was busy, use the next port shown in the window.

**Screenshots are not imported or monitored.** In Chrome or Edge, select the screenshot folder again and grant access. Check that you selected the actual folder and that the files use a supported image format. When using a LAN address, browsers usually cannot continuously monitor a directory; select the folder again to scan it.

**A quest was missed or matched incorrectly.** Check that the screenshot shows the full trader quest list and that the game language matches the available data. Sync the public quest catalog, then search for or manually add the quest. Always review recognition results.

**Quest or map data will not load.** Public data sync requires internet access. If a source website changes or is temporarily unavailable, try again later. Previously downloaded and cached data may still be available.

**Other devices cannot connect.** Set `EFT_TASK_ASSISTANT_HOST=0.0.0.0` before starting the service, make sure both devices are on the same trusted LAN, use the correct LAN IP and startup port, and check Windows Firewall.

If the problem persists, report it on [GitHub Issues](https://github.com/xxtra1112/eft-task-assistant/issues). Before sharing diagnostics, remove usernames, screenshots, and other personal information.

## Development and build

To build a single-file Windows x64 executable, activate a Conda environment with the app dependencies installed, then run:

~~~powershell
python -m pip install -r requirements-build.txt
& "$PWD/build_windows.ps1" -Version 1.0.0
~~~

The executable is written to the `dist` directory. Building requires Windows x64, Python 3.11, and internet access to install and bundle the OCR runtime dependencies. Bug reports and improvement suggestions are welcome on GitHub Issues.

## Data sources and license

Quest details, key requirements, and map points primarily come from [EFTarkov](https://www.eftarkov.com/). Hideout upgrade materials come from [Tarkov.dev](https://tarkov.dev/). These are community sources, not official game APIs; their data may be outdated, incomplete, or differ by game mode. EFT tasks and data change over time, so verify requirements in the game. The app does not guess key acquisition methods or point locations when reliable source data is unavailable.

Original code in this project is available under the [MIT License](LICENSE). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the open-source components bundled in the Windows executable. Game trademarks and third-party content are not relicensed by this project.
