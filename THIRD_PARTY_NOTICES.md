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

Historical reviewed PvE Factory waypoint photograph metadata retains links to https://www.eftarkov.com. The current preview filters photographs under the site's robots-disallowed `/uploads/` paths at both backend and browser boundaries, including image-proxy fallbacks. It does not automatically load or bundle those photographs. Reference page links remain available. Such third-party imagery is not granted under this project's MIT license.

## Multi-source preview

The optional EFTarkov mode reads public HTML task/map pages and native SVG floors
from https://www.eftarkov.com. It is not an official API. The preview respects the
site's robots rules and does not request /api/ or /uploads/ photographs/icons
through the new adapter. No broad redistribution license was verified; assets are
loaded online on demand and are not bundled as MIT content.

The RE3MR selector can retrieve original images explicitly linked from
https://reemr.se for local personal noncommercial desktop viewing and local disk
caching. Original attribution and encoding remain unchanged. No artwork is
bundled, published, or exposed through the mobile/LAN image route. The homepage
identifies CC BY-NC-SA 4.0; some pages also link to 2.0, and the FAQ asks website
and application uploaders to contact the author. No individual authorization or
commercial redistribution permission is claimed. Robots-denied or ambiguous
resources remain blocked; the application does not guess replacement URLs.
No RE3MR task API or calibrated quest coordinates have been verified. Other
providers' coordinates are never overlaid on RE3MR maps. See
[the source evidence and limits](docs/reemr-usage.md).
