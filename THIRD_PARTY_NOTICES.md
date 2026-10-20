# Third-party notices

This inventory describes the inspected local Windows `v1.3.0` release candidate, not a claim that a release has been published. Versions were checked on 2026-10-20 against `requirements-lock-windows.txt`, the build environment's installed distribution metadata and license files, and the executable's PyInstaller archive. An installed or locked package is not necessarily bundled. Their licenses are separate from the MIT license for this project's original code.

## Components found in the candidate executable

| Component | Version in the inspected build | License evidence |
| --- | --- | --- |
| RapidOCR ONNX Runtime | 1.4.4 | Apache-2.0; installed metadata and [upstream v1.4.4 license](https://github.com/RapidAI/RapidOCR/blob/v1.4.4/LICENSE) |
| OpenCV-Python / OpenCV | 5.0.0.93 | MIT for the Python packaging scripts; Apache-2.0 for OpenCV, plus bundled third-party terms in the wheel's `LICENSE-3RD-PARTY.txt`; see [packaging license](https://github.com/opencv/opencv-python/blob/master/LICENSE.txt) |
| NumPy | 2.4.6 | Installed `License-Expression`: `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`; accompanying license files retain additional component terms |
| qrcode | 8.2 | BSD-3-Clause, with retained MIT-origin attribution; installed `qrcode-8.2.dist-info/LICENSE` and [upstream license](https://github.com/lincolnloop/python-qrcode/blob/main/LICENSE) |
| ONNX Runtime | 1.31.0 | MIT; installed `onnxruntime/LICENSE` and [upstream license](https://github.com/microsoft/onnxruntime/blob/main/LICENSE); its `ThirdPartyNotices.txt` covers additional components |
| PyClipper | 1.4.0 | MIT |
| Shapely | 2.2.0 | BSD-3-Clause; installed `shapely-2.2.0.dist-info/licenses/LICENSE.txt` and [upstream license](https://github.com/shapely/shapely/blob/main/LICENSE.txt) |
| PyYAML | 6.0.3 | MIT |
| Pillow | 13.0.0 | MIT-CMU; installed `pillow-13.0.0.dist-info/licenses/LICENSE` and [upstream license](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| packaging | 26.3 | `Apache-2.0 OR BSD-2-Clause`; installed metadata, `LICENSE.APACHE` and `LICENSE.BSD` |
| setuptools / pkg_resources | 79.0.1 | MIT for setuptools itself; vendored components have separate licenses; installed `setuptools-79.0.1.dist-info/licenses/LICENSE` and [upstream license](https://github.com/pypa/setuptools/blob/v79.0.1/LICENSE) |
| Python runtime | 3.11.17 | Python Software Foundation license terms and included third-party notices |

PyClipper is a declared RapidOCR dependency and is present in both the installed environment and the executable. Its installed `pyclipper-1.4.0.dist-info/licenses/LICENSE` and [upstream license](https://github.com/fonttools/pyclipper/blob/main/LICENSE) identify MIT. PyClipper and setuptools are now explicitly pinned in `requirements-lock-windows.txt`; rebuilt CI assets must still be inspected rather than assumed byte-identical to a local build.

The Shapely wheel also contributes GEOS shared libraries found under `Shapely.libs/` in the executable. The installed matching Shapely runtime reports GEOS `3.14.1`. The wheel's `licenses/LICENSE_GEOS` identifies LGPL v2.1, separately from Shapely's BSD license; see [GEOS 3.14.1 COPYING](https://github.com/libgeos/geos/blob/3.14.1/COPYING) and the [matching upstream source](https://github.com/libgeos/geos/tree/3.14.1). The wheel also supplies `LICENSE_win32` for Microsoft runtime files. To use a modified GEOS, rebuild Shapely against that library using the [official source-build instructions](https://shapely.readthedocs.io/en/stable/installation.html#installation-from-source-with-custom-geos-library), then rebuild this MIT-licensed application from its published source. This application does not restrict reverse engineering for debugging such library modifications. The Python, OpenCV, NumPy and other native libraries can carry further component-specific terms; their supplied license texts and notices remain authoritative.

The archive also contains setuptools vendored code, including backports, importlib_metadata, jaraco, more_itertools, packaging, platformdirs, tomli, typing_extensions, wheel and zipp. These components do not all inherit setuptools' MIT license. Preserve their own license and attribution files for the code actually distributed.

## Build environment versus bundled runtime

PyInstaller `6.22.3` is the build tool. Its build-time `PyInstaller` package is not bundled, while its bootloader, loader modules and runtime hooks are embedded. The installed `COPYING.txt` distinguishes GPL-2.0-or-later with the bootloader exception from Apache-2.0 runtime hooks and additional runtime modules; see the [official licensing explanation](https://pyinstaller.org/en/stable/license.html). The exception does not replace dependencies' own license requirements.

The inspected executable contains no modules from these locked build/test tools: altgraph `0.17.5`, pefile `2024.8.26`, pywin32-ctypes `0.2.3`, pyinstaller-hooks-contrib `2026.8`, pytest `9.1.1`, pluggy `1.7.0`, iniconfig `2.3.1`, and Pygments `2.21.0`. Their presence in the build lock is not evidence that they ship in the application.

The lock and installed metadata also contain colorama `0.4.6`, tqdm `4.70.1`, flatbuffers `25.12.19`, protobuf `7.36.2` and six `1.17.0`, but their Python modules were not found in the inspected executable. They are not listed as bundled Python runtime components here. Native libraries' own use of third-party code remains subject to their notices. cffi and pycparser were neither installed in the inspected build environment nor found in the executable; the old runtime entries have been removed.

## License texts distributed with new builds

The builder generates `THIRD_PARTY_LICENSES.txt` before freezing the executable and includes the same report in both the EXE and portable ZIP. It preserves full matching license/copyright/NOTICE texts from explicitly locked installed distributions, including nested vendor notices, plus the Python PSF license. The report distinguishes build tools and inspected non-bundled dependencies; an unavailable license for a non-bundled installed package is explicitly identified, not represented by a guessed text. A missing required runtime license stops the build.

RapidOCR's wheel lacks a standalone license file. Its reviewed [official v1.4.4 license](https://github.com/RapidAI/RapidOCR/blob/v1.4.4/LICENSE) is therefore stored at `third_party/licenses/rapidocr-onnxruntime-1.4.4-LICENSE.txt` and checked against its fixed SHA-256 before inclusion. ONNX Runtime's `ThirdPartyNotices.txt`, Shapely's `LICENSE_GEOS` and `LICENSE_win32`, OpenCV's third-party notices and the supplied NumPy/setuptools/vendor license trees are collected from their installed distributions.

`BUILD-INFO.json` records the generated report's SHA-256, and portable checksums cover it. The release acceptance checks that the report is identical in the actual EXE and ZIP. Historical candidates built before this correction lack that report and must not be substituted for corrected release assets. The project's `LICENSE.txt` remains the application's MIT license; it does not relicense dependencies, OCR models or online artwork. Redistributors must retain the accompanying upstream notices and review any additional components they add.

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
