# Third-party notices

The Windows `v1.0.0` executable bundles the following open-source runtime components. Their licenses apply to those components and are separate from the MIT license for this project's original code.

| Component | Version in the Windows build | License |
| --- | --- | --- |
| RapidOCR ONNX Runtime | 1.4.4 | Apache-2.0 |
| OpenCV-Python | 5.0.0.93 | Apache-2.0 |
| NumPy | 2.4.6 | BSD-3-Clause, 0BSD, MIT, Zlib, and CC0-1.0 components |
| qrcode | 8.2 | BSD-3-Clause |
| cffi | 2.1.1 | MIT |
| pycparser | 3.11 | BSD-3-Clause |
| ONNX Runtime | 1.30.0 | MIT |
| PyClipper | 1.4.0 | MIT |
| Shapely | 2.1.2 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| Pillow | 12.3.0 | MIT-CMU |
| tqdm | 4.67.1 | MPL-2.0 and MIT components |
| FlatBuffers | 25.12.19 | Apache-2.0 |
| Protocol Buffers | 7.36.2 | BSD-3-Clause |
| six | 1.17.0 | MIT |
| Python runtime | 3.11 | Python Software Foundation License |

PyInstaller 6.22.3 is used to build the executable. PyInstaller is licensed under GPL-2.0-or-later with a bootloader exception that permits distributing applications built with it under other licenses.

The versions above describe the published binary. Rebuilding from source may resolve different compatible dependency versions; consult each package's own license and notices when redistributing a rebuilt executable.

The app may use the public [wsrv.nl](https://wsrv.nl/) image proxy as a browser-side fallback when an item image host is unavailable. It is an online service, is not bundled with the executable, and receives only the public image URL being requested.

## Online game data and map artwork

The app retrieves quest, map, extract, transit, and Hideout data from the public [Tarkov.dev JSON API](https://json.tarkov.dev/endpoints). Interactive-map configuration is read from [the Tarkov.dev project](https://github.com/the-hideout/tarkov-dev). These are community resources, not official Battlestate Games services, and are not bundled as a local database in the executable.

SVG basemaps are fetched on demand from `assets.tarkov.dev`, which serves maps maintained in [the tarkov-dev-svg-maps repository](https://github.com/the-hideout/tarkov-dev-svg-maps). The repository's map artwork is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), separately from this project's MIT-licensed code. The interface links to the map source and displays the map author and license when the upstream metadata provides an author. Do not assume this license permits commercial use or relicenses artwork as MIT; review the upstream license and attribution requirements before redistribution. The app uses the maps as a standalone quest-planning tool and does not read game memory, show live player positions, or automate gameplay.

## EFTarkov waypoint photographs

A limited set of reviewed PvE Factory waypoint photographs is loaded from public pages on https://www.eftarkov.com. Each photograph retains a link to its map marker source. These third-party photographs are not bundled in the executable or granted under this project's MIT license; the game imagery and source content remain subject to their respective owners' rights. Task data and coordinates continue to use Tarkov.dev.
