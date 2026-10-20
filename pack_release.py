"""Validate release inputs and package only explicitly approved portable files."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile


VERSION_PATTERN = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
DOCUMENTS = (
    "README.md",
    "README.en.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/data-sources.md",
    "docs/preload-evidence.md",
    "docs/reemr-usage.md",
    "docs/route-sync.md",
    "docs/save-data.md",
    "docs/release-checklist.md",
)
WEB_FILES = (
    "app.js", "index.html", "mobile.css", "mobile.html", "mobile.js",
    "preference_sync.js", "route_tools.js", "save_tools.js", "styles.css",
)
LICENSE_REPORT = "THIRD_PARTY_LICENSES.txt"
BUILD_ONLY_DEPENDENCIES = {
    "altgraph", "iniconfig", "pefile", "pluggy", "pygments",
    "pyinstaller-hooks-contrib", "pytest", "pywin32-ctypes",
}
LICENSE_NAME = re.compile(
    r"(?:(?:.*[_-])?(?:licen[cs]es?|copying|copyright|notices?)(?:[-_][^.]+)?|thirdpartynotices?)"
    r"(?:\.(?:txt|text|md|rst|apache|bsd|mit|gpl|lgpl|mpl))?", re.IGNORECASE,
)
PYTHON_LICENSE_FILES = ("LICENSE_PYTHON.txt", "LICENSE.txt", "LICENSE")
INSTALLED_ONLY_DEPENDENCIES = {
    ("colorama", "0.4.6"), ("flatbuffers", "25.12.19"), ("protobuf", "7.36.2"),
    ("six", "1.17.0"), ("tqdm", "4.70.1"),
}
VENDORED_LICENSES = {
    ("rapidocr-onnxruntime", "1.4.4"): (
        "third_party/licenses/rapidocr-onnxruntime-1.4.4-LICENSE.txt",
        "3e0af25fdd06aa9586ae97adb00ea927ebe5a3805ac77d2d3a81ce5f55693333",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: Path, *arguments: str) -> str:
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], check=True,
        capture_output=True, text=True, encoding="utf-8", env=environment,
    )
    return result.stdout.strip()


def release_version(root: Path, version: str | None = None, tag: str | None = None) -> dict:
    value = json.loads((root / "release_version.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("release_version.json must contain an object.")
    declared = value.get("version")
    if not isinstance(declared, str) or not re.fullmatch(VERSION_PATTERN, declared):
        raise ValueError("Invalid version in release_version.json.")
    if version is not None and version != declared:
        raise ValueError("Version must match release_version.json.")
    if tag is not None and tag != f"v{declared}":
        raise ValueError("Tag must match release_version.json as vMAJOR.MINOR.PATCH.")
    if value.get("python") != "3.11.17":
        raise ValueError("Release Python must be pinned to 3.11.17.")
    return value


def validate_source(root: Path, source_commit: str, tag: str | None = None) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("Source commit must be a full lowercase 40-character commit ID.")
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise ValueError("Source root must be the checkout root.")
    if git(root, "rev-parse", "HEAD") != source_commit:
        raise ValueError("Source commit does not match checkout HEAD.")
    if git(root, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"):
        raise ValueError("Release builds require a clean working tree, including untracked files.")
    if tag is not None and git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}") != source_commit:
        raise ValueError("Release tag does not point to the source commit.")


def regular_file(root: Path, relative: str) -> Path:
    path = root / relative
    for component in (path, *path.parents):
        if component == root:
            break
        attributes = component.lstat()
        if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Release input must not use links or reparse points: {relative}")
    if not path.is_file():
        raise ValueError(f"Missing regular release input: {relative}")
    return path


def portable_inputs(root: Path, version: str) -> dict[str, Path]:
    names = (*DOCUMENTS, f"docs/releases/v{version}.md")
    files = {name: regular_file(root, name) for name in names}
    files["LICENSE.txt"] = regular_file(root, "LICENSE")
    return files


def locked_dependencies(root: Path) -> dict[str, str]:
    dependencies = {}
    lock = regular_file(root, "requirements-lock-windows.txt")
    for line in lock.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9_.+!-]+)", line)
        if match is None:
            raise ValueError("Every lock entry must be an exact name==version pin.")
        name, expected = match.groups()
        canonical = re.sub(r"[-_.]+", "-", name).lower()
        if canonical in dependencies:
            raise ValueError(f"Duplicate locked dependency: {name}")
        actual = metadata.version(name)
        if actual != expected:
            raise ValueError(f"Locked dependency mismatch: {name}: expected {expected}, got {actual}")
        dependencies[canonical] = actual
    if not dependencies:
        raise ValueError("The Windows dependency lock must not be empty.")
    return dict(sorted(dependencies.items()))


def license_text(root: Path, relative: str, expected_sha256: str | None = None) -> str:
    if not relative or relative.startswith("/") or ":" in relative or ".." in relative.split("/"):
        raise ValueError("License file must have a safe relative public filename.")
    try:
        raw = regular_file(root, relative).read_bytes()
        if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError(f"Vendored license checksum mismatch: {relative}")
        content = raw.decode("utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Cannot read UTF-8 license text: {relative}") from error
    if not content.strip() or "\x00" in content:
        raise ValueError(f"Empty or non-text license file: {relative}")
    return content


def third_party_licenses(dependencies: dict[str, str], source_root: Path | None = None) -> str:
    sections = [
        "THIRD-PARTY LICENSE TEXTS\n"
        "Collected offline from locked installed distributions, version-specific source licenses and the running Python.\n"
        "File names are relative to the stated origin: installed distribution, source checkout or Python runtime.\n"
        "This inventory does not prove which components are bundled in the executable.\n"
        "Build-only entries describe build environment tools, not bundled runtime components.\n"
        "Installed-only entries were absent from the reviewed release inventory; recheck them when rebuilding.\n"
    ]
    missing = []
    for name, version in sorted(dependencies.items()):
        distribution = metadata.distribution(name)
        if distribution.version != version:
            raise ValueError(f"Locked dependency mismatch while collecting licenses: {name}")
        scope = "build-only" if name in BUILD_ONLY_DEPENDENCIES else "runtime dependency"
        installed_only = (name, version) in INSTALLED_ONLY_DEPENDENCIES
        if installed_only:
            scope = "installed-only; not bundled (version-specific release inventory)"
        if name == "pyinstaller":
            scope = "build tool; its bootloader may be bundled"
        sections.append(f"\nComponent: {name}\nVersion: {version}\nScope: {scope}\n")
        files = sorted({
            str(item).replace("\\", "/") for item in distribution.files or ()
            if LICENSE_NAME.fullmatch(str(item).replace("\\", "/").rsplit("/", 1)[-1])
        })
        origin = "installed distribution"
        license_root = Path(distribution.locate_file(""))
        vendored = VENDORED_LICENSES.get((name, version))
        expected_sha256 = None
        if not files and vendored is not None and source_root is not None and (source_root / vendored[0]).is_file():
            files = [vendored[0]]
            expected_sha256 = vendored[1]
            origin = "source checkout (version-specific license fallback)"
            license_root = source_root
        sections.append(f"Origin: {origin}\n")
        if not files:
            explanation = (
                f"{name}=={version}: no license text in installed distribution.files; "
                "a license name or URL in metadata is not a license text."
            )
            if vendored is not None:
                explanation += f" Supply the full reviewed upstream license at {vendored[0]}."
            if name not in BUILD_ONLY_DEPENDENCIES and not installed_only:
                missing.append(explanation)
            sections.append(f"Unavailable: {explanation}\n")
        for relative in files:
            content = license_text(license_root, relative, expected_sha256)
            sections.append(f"\nFile: {relative}\n----- BEGIN LICENSE TEXT -----\n{content}")
            sections.append("\n----- END LICENSE TEXT -----\n")
    sections.append(f"\nComponent: Python\nVersion: {platform.python_version()}\nScope: runtime\nOrigin: Python runtime\n")
    python_root = Path(sys.base_prefix)
    for relative in PYTHON_LICENSE_FILES:
        if (python_root / relative).is_file():
            content = license_text(python_root, relative)
            if "PYTHON SOFTWARE FOUNDATION LICENSE" not in content.upper():
                continue
            sections.append(f"\nFile: {relative}\n----- BEGIN LICENSE TEXT -----\n{content}")
            sections.append("\n----- END LICENSE TEXT -----\n")
            break
    else:
        missing.append("Python: no PSF license text in the supported runtime-root license files.")
    if missing:
        raise ValueError("Missing required runtime license text:\n" + "\n".join(missing))
    return "".join(sections)


def build_info(root: Path, version: str | None, source_commit: str, tag: str | None = None) -> dict:
    value = release_version(root, version, tag)
    validate_source(root, source_commit, tag)
    if platform.python_version() != value["python"]:
        raise ValueError(f"Python {value['python']} is required.")
    if platform.system() != "Windows" or struct.calcsize("P") != 8 or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("Windows x64 is required for a release build.")
    portable_inputs(root, value["version"])
    for name in WEB_FILES:
        regular_file(root, f"web/{name}")
    input_hashes = {
        name: sha256(regular_file(root, name))
        for name in ("requirements.txt", "requirements-build.txt", "requirements-lock-windows.txt", "release_version.json", ".github/conda-release.yml")
    }
    return {
        "version": value["version"],
        "source_commit": source_commit,
        "tag": tag,
        "python": platform.python_version(),
        "python_runtime": sys.version,
        "platform": "Windows-x64",
        "dependencies": locked_dependencies(root),
        "lock_sha256": input_hashes["requirements-lock-windows.txt"],
        "input_sha256": input_hashes,
        "reproducibility": (
            "Checkout the recorded commit; install requirements-build.txt in a fresh Python 3.11.17 Windows x64 environment; "
            "run pip check and build_windows.ps1. Commit, lock and process are verifiable; "
            "The full runtime string records the local Python distributor; CI uses the pinned conda-forge recipe. "
            "PyInstaller executables and ZIPs are not guaranteed byte-identical across machines."
        ),
    }


def write_checksums(path: Path, files: dict[str, Path]) -> None:
    path.write_text("".join(f"{sha256(source)}  {name}\n" for name, source in sorted(files.items())), encoding="ascii")


def package_release(root: Path, executable: Path, output: Path, version: str | None,
                    source_commit: str, tag: str | None = None,
                    licenses_output: Path | None = None) -> dict[str, Path]:
    root = root.resolve()
    info = build_info(root, version, source_commit, tag)
    if licenses_output is None:
        raise ValueError("Provide the license report generated before building the executable.")
    licenses_output = regular_file(licenses_output.parent.resolve(), licenses_output.name)
    licenses = third_party_licenses(info["dependencies"], root).encode("utf-8")
    if licenses_output.read_bytes() != licenses:
        raise ValueError("License report differs from the current locked environment; regenerate and rebuild the executable.")
    version = info["version"]
    executable = regular_file(executable.parent.resolve(), executable.name)
    with executable.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Expected a Windows executable with an MZ header.")
    stem = f"EFTTaskAssistant-v{version}-Windows-x64"
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "exe": output / f"{stem}.exe",
        "zip": output / f"{stem}-portable.zip",
        "checksums": output / "SHA256SUMS.txt",
    }
    if any(path.exists() for path in artifacts.values()):
        raise ValueError("Release outputs already exist; use a fresh output directory.")
    with tempfile.TemporaryDirectory(prefix="eft-release-", dir=output.parent) as temporary:
        stage = Path(temporary)
        files = portable_inputs(root, version)
        licenses_path = stage / LICENSE_REPORT
        licenses_path.write_bytes(licenses)
        files[LICENSE_REPORT] = licenses_path
        info["third_party_licenses_sha256"] = sha256(licenses_path)
        staged_executable = stage / f"{stem}.exe"
        shutil.copyfile(executable, staged_executable)
        files[staged_executable.name] = staged_executable
        info["executable_sha256"] = sha256(staged_executable)
        info_path = stage / "BUILD-INFO.json"
        info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        files["BUILD-INFO.json"] = info_path
        sums = stage / "SHA256SUMS.txt"
        write_checksums(sums, files)
        files["SHA256SUMS.txt"] = sums
        archive = stage / artifacts["zip"].name
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for name, source in sorted(files.items()):
                bundle.write(source, name)
        validate_source(root, source_commit, tag)
        shutil.copyfile(staged_executable, artifacts["exe"])
        shutil.copyfile(archive, artifacts["zip"])
        write_checksums(artifacts["checksums"], {path.name: path for key, path in artifacts.items() if key != "checksums"})
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--version")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--tag")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--licenses-output", type=Path, help="Generate this license report before building; supply the same file when packaging.")
    args = parser.parse_args()
    try:
        if args.check_only:
            print(json.dumps(build_info(args.root.resolve(), args.version, args.source_commit, args.tag), indent=2))
        elif args.exe is None and args.licenses_output is not None:
            info = build_info(args.root.resolve(), args.version, args.source_commit, args.tag)
            licenses = third_party_licenses(info["dependencies"], args.root.resolve()).encode("utf-8")
            args.licenses_output.write_bytes(licenses)
            print(f"Generated {LICENSE_REPORT}")
        else:
            if args.exe is None or args.output_dir is None or args.licenses_output is None:
                parser.error("--exe, --output-dir and --licenses-output are required for packaging")
            artifacts = package_release(args.root, args.exe, args.output_dir, args.version, args.source_commit, args.tag, args.licenses_output)
            print(json.dumps({name: str(path) for name, path in artifacts.items()}, indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError, metadata.PackageNotFoundError) as error:
        parser.exit(1, f"Release validation failed: {error}\n")


if __name__ == "__main__":
    main()
