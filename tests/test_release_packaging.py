import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
from packaging.requirements import Requirement

import pack_release


SOURCE_COMMIT = "a" * 40
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def release_tree(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    root.mkdir()
    names = (*pack_release.DOCUMENTS, "LICENSE", "docs/releases/v1.3.0.md")
    for name in names:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"Release document: {name}\n", encoding="utf-8")
    for name in pack_release.WEB_FILES:
        target = root / "web" / name
        target.parent.mkdir(exist_ok=True)
        target.write_text("fixture", encoding="utf-8")
    for name in ("release_version.json", "requirements.txt", "requirements-build.txt", "requirements-lock-windows.txt"):
        (root / name).write_bytes((PROJECT_ROOT / name).read_bytes())
    (root / ".github").mkdir()
    (root / ".github/conda-release.yml").write_bytes((PROJECT_ROOT / ".github/conda-release.yml").read_bytes())
    versions = dict(line.split("==") for line in (root / "requirements-lock-windows.txt").read_text().splitlines())
    monkeypatch.setattr(pack_release.metadata, "version", versions.__getitem__)
    installed = tmp_path / "installed"
    installed.mkdir()
    distributions = {}
    for name, version in versions.items():
        canonical = name.lower().replace("_", "-")
        relative = f"{canonical}-{version}.dist-info/licenses/LICENSE.txt"
        target = installed / relative
        target.parent.mkdir(parents=True)
        target.write_text(f"Complete license text for {canonical}\nRedistribution is permitted.\n", encoding="utf-8")
        distributions[canonical] = SimpleNamespace(
            version=version, files=[Path(relative)], locate_file=lambda relative: installed / relative,
        )
    monkeypatch.setattr(pack_release.metadata, "distribution", distributions.__getitem__)
    python_root = tmp_path / "python-runtime"
    python_root.mkdir()
    (python_root / "LICENSE_PYTHON.txt").write_text(
        "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2\nComplete PSF fixture text.\n", encoding="utf-8",
    )
    monkeypatch.setattr(pack_release.sys, "base_prefix", str(python_root))
    monkeypatch.setattr(pack_release.platform, "python_version", lambda: "3.11.17")
    monkeypatch.setattr(pack_release.platform, "system", lambda: "Windows")
    monkeypatch.setattr(pack_release.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(pack_release.struct, "calcsize", lambda _format: 8)

    def clean_git(_root, *arguments):
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(root)
        if arguments[0] == "status":
            return ""
        return SOURCE_COMMIT

    monkeypatch.setattr(pack_release, "git", clean_git)
    (root / "build").mkdir()
    (root / "build" / pack_release.LICENSE_REPORT).write_bytes(
        pack_release.third_party_licenses(pack_release.locked_dependencies(root)).encode("utf-8"),
    )
    return root


def executable_fixture(root):
    executable = root / "build" / "EFTTaskAssistant.exe"
    executable.parent.mkdir(exist_ok=True)
    executable.write_bytes(b"MZ\x00release executable fixture")
    return executable


def test_portable_whitelist_checksums_and_build_provenance(release_tree):
    for name in (
        "tasks.sqlite3", "players.sqlite3-wal", "cache/maps.db", ".env", "credentials.json",
        "tokens/session.json", "logs/app.log", "docs/images/screenshot.png",
        "docs/promo/video.mp4", "web/private.png", "public-data/map.svg", "docs/releases/v1.2.0.md",
    ):
        target = release_tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"private or downloaded content")
    executable = executable_fixture(release_tree)
    artifacts = pack_release.package_release(
        release_tree, executable, release_tree / "dist", "1.3.0", SOURCE_COMMIT, "v1.3.0",
        licenses_output=release_tree / "build" / pack_release.LICENSE_REPORT,
    )
    expected = {
        "EFTTaskAssistant-v1.3.0-Windows-x64.exe", "README.md", "README.en.md", "LICENSE.txt",
        "THIRD_PARTY_NOTICES.md", "docs/data-sources.md", "docs/preload-evidence.md",
        "docs/reemr-usage.md", "docs/route-sync.md", "docs/save-data.md", "docs/release-checklist.md",
        "docs/releases/v1.3.0.md", "BUILD-INFO.json", "SHA256SUMS.txt", "THIRD_PARTY_LICENSES.txt",
    }
    with zipfile.ZipFile(artifacts["zip"]) as archive:
        assert set(archive.namelist()) == expected
        assert len(archive.namelist()) == len(expected)
        for line in archive.read("SHA256SUMS.txt").decode("ascii").splitlines():
            digest, name = line.split("  ")
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        sums = archive.read("SHA256SUMS.txt").decode("ascii").splitlines()
        assert {line.split("  ")[1] for line in sums} == expected - {"SHA256SUMS.txt"}
        info = json.loads(archive.read("BUILD-INFO.json"))
        assert info["source_commit"] == SOURCE_COMMIT
        assert info["version"] == "1.3.0"
        assert info["tag"] == "v1.3.0"
        assert info["python"] == "3.11.17"
        assert info["dependencies"]["pyinstaller"] == "6.22.3"
        assert info["lock_sha256"] == pack_release.sha256(release_tree / "requirements-lock-windows.txt")
        assert info["executable_sha256"] == pack_release.sha256(artifacts["exe"])
        licenses = archive.read(pack_release.LICENSE_REPORT)
        assert licenses == (release_tree / "build" / pack_release.LICENSE_REPORT).read_bytes()
        assert info["third_party_licenses_sha256"] == hashlib.sha256(licenses).hexdigest()
        assert str(release_tree.parent).encode("utf-8") not in licenses
        assert "not guaranteed byte-identical" in info["reproducibility"]
        assert archive.read(artifacts["exe"].name) == artifacts["exe"].read_bytes()
    external_sums = artifacts["checksums"].read_text(encoding="ascii").splitlines()
    assert {line.split("  ")[1] for line in external_sums} == {artifacts["zip"].name, artifacts["exe"].name}
    for line in external_sums:
        digest, name = line.split("  ")
        assert pack_release.sha256(artifacts["checksums"].parent / name) == digest


@pytest.mark.parametrize("version,tag", [("1.2.0", None), ("1.3.0", "v1.2.0"), (None, "v1.3.0-rc1"), (None, "1.3.0")])
def test_version_and_tag_must_match_metadata(release_tree, version, tag):
    with pytest.raises(ValueError, match="match release_version.json"):
        pack_release.release_version(release_tree, version, tag)


def test_default_version_is_formal_130(release_tree):
    assert pack_release.release_version(release_tree)["version"] == "1.3.0"
    info = pack_release.build_info(release_tree, None, SOURCE_COMMIT)
    assert info["version"] == "1.3.0"
    assert info["tag"] is None


@pytest.mark.parametrize("value", [[], {"version": "01.3.0", "python": "3.11.17"}, {"version": "1.3.0", "python": "3.11"}])
def test_malformed_version_metadata_is_rejected(release_tree, value):
    (release_tree / "release_version.json").write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        pack_release.release_version(release_tree)


@pytest.mark.parametrize("commit", ["a03a2ca", "A" * 40, "z" * 40, "b" * 40])
def test_commit_must_be_full_and_match_head(release_tree, commit):
    with pytest.raises(ValueError, match="commit"):
        pack_release.validate_source(release_tree, commit)


@pytest.mark.parametrize("status", [" M main.py", "M  main.py", "?? credentials.json"])
def test_dirty_source_is_rejected_before_output(release_tree, monkeypatch, status):
    clean_git = pack_release.git
    monkeypatch.setattr(pack_release, "git", lambda root, *args: status if args[0] == "status" else clean_git(root, *args))
    executable = executable_fixture(release_tree)
    output = release_tree / "dist"
    with pytest.raises(ValueError, match="clean working tree"):
        pack_release.package_release(
            release_tree, executable, output, "1.3.0", SOURCE_COMMIT,
            licenses_output=release_tree / "build" / pack_release.LICENSE_REPORT,
        )
    assert not output.exists()


def test_tag_must_resolve_to_same_commit(release_tree, monkeypatch):
    clean_git = pack_release.git
    monkeypatch.setattr(pack_release, "git", lambda root, *args: "b" * 40 if "--verify" in args else clean_git(root, *args))
    with pytest.raises(ValueError, match="tag does not point"):
        pack_release.validate_source(release_tree, SOURCE_COMMIT, "v1.3.0")


def test_source_changes_during_packaging_are_rejected(release_tree, monkeypatch):
    clean_git = pack_release.git
    calls = []

    def changing_git(root, *arguments):
        if arguments[0] == "status":
            calls.append(arguments)
            if len(calls) > 1:
                return " M main.py"
        return clean_git(root, *arguments)

    monkeypatch.setattr(pack_release, "git", changing_git)
    output = release_tree / "dist"
    with pytest.raises(ValueError, match="clean working tree"):
        pack_release.package_release(
            release_tree, executable_fixture(release_tree), output, None, SOURCE_COMMIT,
            licenses_output=release_tree / "build" / pack_release.LICENSE_REPORT,
        )
    assert not list(output.iterdir())


def test_missing_versioned_notes_prevent_packaging(release_tree):
    (release_tree / "docs/releases/v1.3.0.md").unlink()
    with pytest.raises(FileNotFoundError):
        pack_release.build_info(release_tree, None, SOURCE_COMMIT)


def test_reparse_point_inputs_are_rejected(release_tree, monkeypatch):
    original_lstat = Path.lstat
    target = release_tree / "README.md"
    monkeypatch.setattr(Path, "lstat", lambda path: SimpleNamespace(st_mode=0o100644, st_file_attributes=0x400) if path == target else original_lstat(path))
    with pytest.raises(ValueError, match="reparse points"):
        pack_release.portable_inputs(release_tree, "1.3.0")


def test_locked_dependency_drift_is_rejected(release_tree, monkeypatch):
    monkeypatch.setattr(pack_release.metadata, "version", lambda name: "0.0.0")
    with pytest.raises(ValueError, match="Locked dependency mismatch"):
        pack_release.build_info(release_tree, None, SOURCE_COMMIT)


def test_wrong_python_is_rejected(release_tree, monkeypatch):
    monkeypatch.setattr(pack_release.platform, "python_version", lambda: "3.11.16")
    with pytest.raises(ValueError, match="Python 3.11.17"):
        pack_release.build_info(release_tree, None, SOURCE_COMMIT)


def test_existing_artifacts_are_never_overwritten(release_tree):
    executable = executable_fixture(release_tree)
    output = release_tree / "dist"
    artifacts = pack_release.package_release(
        release_tree, executable, output, None, SOURCE_COMMIT,
        licenses_output=release_tree / "build" / pack_release.LICENSE_REPORT,
    )
    before = {path: path.read_bytes() for path in artifacts.values()}
    with pytest.raises(ValueError, match="already exist"):
        pack_release.package_release(
            release_tree, executable, output, None, SOURCE_COMMIT,
            licenses_output=release_tree / "build" / pack_release.LICENSE_REPORT,
        )
    assert {path: path.read_bytes() for path in artifacts.values()} == before


def test_runtime_requirements_are_satisfied_by_the_fixed_lock():
    lines = (PROJECT_ROOT / "requirements-lock-windows.txt").read_text().splitlines()
    versions = {Requirement(line).name.lower().replace("_", "-"): Requirement(line).specifier for line in lines}
    assert len(versions) == len(lines)
    for line in (PROJECT_ROOT / "requirements.txt").read_text().splitlines():
        if not line.strip():
            continue
        requirement = Requirement(line)
        pinned = next(iter(versions[requirement.name.lower().replace("_", "-")])).version
        assert pinned in requirement.specifier
    assert (PROJECT_ROOT / "requirements-build.txt").read_text().splitlines() == [
        "-r requirements.txt", "-r requirements-lock-windows.txt",
    ]


def test_locked_installed_metadata_dependency_closure_includes_pyclipper_and_setuptools():
    dependencies = pack_release.locked_dependencies(PROJECT_ROOT)
    required_by = {}
    for name in dependencies:
        required_by[name] = set()
        for value in pack_release.metadata.requires(name) or ():
            requirement = Requirement(value)
            if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
                continue
            canonical = pack_release.re.sub(r"[-_.]+", "-", requirement.name).lower()
            assert canonical in dependencies, f"Missing locked dependency: {name} requires {requirement}"
            assert dependencies[canonical] in requirement.specifier, f"Incompatible lock: {name} requires {requirement}"
            required_by[name].add(canonical)
    assert "pyclipper" in required_by["rapidocr-onnxruntime"]
    assert "setuptools" in dependencies
    assert "setuptools" in required_by["pyinstaller"]


def test_license_collection_keeps_all_recorded_texts_and_ignores_unlisted_files(release_tree):
    distribution = pack_release.metadata.distribution("onnxruntime")
    installed = distribution.locate_file("")
    for relative, content in (
        ("onnxruntime/LICENSE", "First complete license\nFinal license line"),
        ("onnxruntime/ThirdPartyNotices.txt", "Native dependency notice\nComplete notice ending"),
        ("onnxruntime/COPYING", "Copying terms\nComplete copying ending"),
    ):
        target = installed / relative
        target.parent.mkdir(exist_ok=True)
        target.write_text(content, encoding="utf-8")
        distribution.files.append(Path(relative))
    (installed / "credentials.json").write_text("PRIVATE CREDENTIAL FIXTURE", encoding="utf-8")
    (installed / "LICENSE-secret.txt").write_text("UNLISTED PRIVATE FILE", encoding="utf-8")
    dependencies = pack_release.locked_dependencies(release_tree)
    report = pack_release.third_party_licenses(dependencies)
    for relative in distribution.files:
        assert f"File: {relative.as_posix()}\n" in report
        assert (installed / relative).read_bytes().decode("utf-8") in report
    assert "PRIVATE" not in report
    assert "Component: Python\nVersion: 3.11.17\nScope: runtime" in report
    assert "File: LICENSE_PYTHON.txt" in report
    assert "Complete PSF fixture text." in report
    assert "Component: pytest\nVersion: 9.1.1\nScope: build-only" in report
    assert "build tool; its bootloader may be bundled" in report
    assert str(installed) not in report
    assert str(pack_release.sys.base_prefix) not in report
    assert report == pack_release.third_party_licenses(dependencies)


@pytest.mark.parametrize("name", ["pyclipper", "setuptools", "rapidocr-onnxruntime", "numpy", "pyinstaller"])
@pytest.mark.parametrize("files", [None, [], [Path("package/AUTHORS")], [Path("package/license.py")]])
def test_missing_critical_licenses_are_explicit(release_tree, name, files):
    pack_release.metadata.distribution(name).files = files
    with pytest.raises(ValueError, match=rf"{name}==.*no license text"):
        pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree))


def test_missing_runtime_licenses_are_reported_together(release_tree):
    for name in ("numpy", "rapidocr-onnxruntime"):
        pack_release.metadata.distribution(name).files = []
    with pytest.raises(ValueError) as failure:
        pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree))
    assert "numpy==" in str(failure.value)
    assert "rapidocr-onnxruntime==" in str(failure.value)
    assert "metadata is not a license text" in str(failure.value)


def test_missing_build_only_license_is_explained(release_tree):
    pack_release.metadata.distribution("pytest").files = None
    report = pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree))
    assert "Scope: build-only\nOrigin: installed distribution\nUnavailable: pytest==9.1.1: no license text" in report


@pytest.mark.parametrize("relative", ["../LICENSE", "/private/LICENSE", "C:/private/LICENSE", "C:\\private\\LICENSE"])
def test_unsafe_license_record_paths_are_rejected(release_tree, relative):
    pack_release.metadata.distribution("numpy").files = [relative]
    with pytest.raises(ValueError, match="safe relative public filename"):
        pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree))


@pytest.mark.parametrize("content", [b"", b"\xff", b"binary\x00text"])
def test_empty_or_invalid_license_text_is_rejected(release_tree, content):
    distribution = pack_release.metadata.distribution("numpy")
    distribution.locate_file(distribution.files[0]).write_bytes(content)
    with pytest.raises(ValueError, match="license"):
        pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree))


def test_missing_recorded_license_cannot_silently_disappear(release_tree):
    distribution = pack_release.metadata.distribution("numpy")
    distribution.locate_file(distribution.files[0]).unlink()
    with pytest.raises(ValueError, match="Cannot read UTF-8 license text") as failure:
        pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree))
    assert str(release_tree.parent) not in str(failure.value)


@pytest.mark.parametrize("content", [None, "License name only, no PSF text"])
def test_python_psf_text_is_required(release_tree, content):
    target = Path(pack_release.sys.base_prefix) / "LICENSE_PYTHON.txt"
    if content is None:
        target.unlink()
    else:
        target.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="Python: no PSF license text"):
        pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree))


def test_license_collection_rechecks_distribution_versions(release_tree):
    pack_release.metadata.distribution("numpy").version = "0.0.0"
    with pytest.raises(ValueError, match="Locked dependency mismatch while collecting licenses: numpy"):
        pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree))


@pytest.mark.parametrize("content", [None, b"stale or tampered report"])
def test_packaging_requires_matching_prebuild_license_report(release_tree, content):
    licenses = release_tree / "build" / pack_release.LICENSE_REPORT
    if content is not None:
        licenses.write_bytes(content)
    output = release_tree / "dist"
    with pytest.raises(ValueError, match="license report|License report"):
        pack_release.package_release(
            release_tree, executable_fixture(release_tree), output, None, SOURCE_COMMIT,
            licenses_output=licenses if content is not None else None,
        )
    assert not output.exists()


def test_license_generation_cli_preserves_release_validation(release_tree, monkeypatch):
    output = release_tree / "build" / "generated-licenses.txt"
    monkeypatch.setattr(pack_release.sys, "argv", [
        "pack_release.py", "--root", str(release_tree), "--source-commit", SOURCE_COMMIT,
        "--licenses-output", str(output),
    ])
    pack_release.main()
    assert output.read_bytes() == (release_tree / "build" / pack_release.LICENSE_REPORT).read_bytes()
    output.unlink()
    clean_git = pack_release.git
    monkeypatch.setattr(pack_release, "git", lambda root, *args: " M main.py" if args[0] == "status" else clean_git(root, *args))
    with pytest.raises(SystemExit) as failure:
        pack_release.main()
    assert failure.value.code == 1
    assert not output.exists()


def test_build_script_embeds_prebuild_report_and_passes_it_to_packager():
    script = (PROJECT_ROOT / "build_windows.ps1").read_text(encoding="utf-8")
    assert script.index("--licenses-output $licensesFile") < script.index('"-B", "-m", "PyInstaller"')
    assert '"--add-data", "$licensesFile;."' in script
    assert "--exe $builtExecutable --output-dir $distRoot --licenses-output $licensesFile" in script


def test_only_version_specific_reviewed_source_fallback_is_used(release_tree, monkeypatch):
    name = "rapidocr-onnxruntime"
    dependencies = pack_release.locked_dependencies(release_tree)
    distribution = pack_release.metadata.distribution(name)
    distribution.files = []
    relative, _digest = pack_release.VENDORED_LICENSES[(name, dependencies[name])]
    target = release_tree / relative
    target.parent.mkdir(parents=True)
    content = "Full reviewed upstream license\nAll original conditions and disclaimers."
    target.write_bytes(content.encode("utf-8"))
    monkeypatch.setitem(pack_release.VENDORED_LICENSES, (name, dependencies[name]), (
        relative, hashlib.sha256(target.read_bytes()).hexdigest(),
    ))
    report = pack_release.third_party_licenses(dependencies, release_tree)
    assert "Origin: source checkout (version-specific license fallback)" in report
    assert f"File: {relative}\n" in report
    assert content in report
    dependencies[name] = "0.0.0"
    distribution.version = "0.0.0"
    with pytest.raises(ValueError, match=rf"{name}==0.0.0: no license text"):
        pack_release.third_party_licenses(dependencies, release_tree)


def test_missing_fallback_does_not_accept_unlisted_source_licenses(release_tree):
    pack_release.metadata.distribution("rapidocr-onnxruntime").files = []
    (release_tree / "LICENSE-rapidocr.txt").write_text("Unreviewed alternate location", encoding="utf-8")
    with pytest.raises(ValueError, match="Supply the full reviewed upstream license at third_party/licenses/rapidocr"):
        pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree), release_tree)


@pytest.mark.parametrize("name", ["pyclipper", "setuptools"])
def test_new_locked_components_and_recorded_vendor_licenses_are_included(release_tree, monkeypatch, name):
    installed = release_tree.parent / "additional-installed"
    relative = f"{name}-1.4.0.dist-info/licenses/LICENSE"
    vendor_relative = f"{name}/_vendor/example-2.0.dist-info/LICENSE.BSD"
    for filename in (relative, vendor_relative):
        path = installed / filename
        path.parent.mkdir(parents=True)
        path.write_text(f"Complete text: {filename}", encoding="utf-8")
    distribution = SimpleNamespace(
        version="1.4.0", files=[Path(relative), Path(vendor_relative)],
        locate_file=lambda filename: installed / filename,
    )
    original_distribution = pack_release.metadata.distribution
    original_version = pack_release.metadata.version
    monkeypatch.setattr(pack_release.metadata, "distribution", lambda value: distribution if value == name else original_distribution(value))
    monkeypatch.setattr(pack_release.metadata, "version", lambda value: "1.4.0" if value == name else original_version(value))
    lock = release_tree / "requirements-lock-windows.txt"
    lines = [line for line in lock.read_text().splitlines() if not line.lower().startswith(f"{name}==")]
    lock.write_text("\n".join([*lines, f"{name}==1.4.0"]) + "\n", encoding="utf-8")
    report = pack_release.third_party_licenses(pack_release.locked_dependencies(release_tree), release_tree)
    assert f"Component: {name}\nVersion: 1.4.0" in report
    for filename in (relative, vendor_relative):
        assert f"File: {filename}\n" in report
        assert f"Complete text: {filename}" in report


def test_vendored_rapidocr_license_checksum_is_enforced(release_tree):
    name = "rapidocr-onnxruntime"
    pack_release.metadata.distribution(name).files = []
    dependencies = pack_release.locked_dependencies(release_tree)
    relative, _digest = pack_release.VENDORED_LICENSES[(name, dependencies[name])]
    target = release_tree / relative
    target.parent.mkdir(parents=True)
    target.write_text("Tampered or incomplete license", encoding="utf-8")
    with pytest.raises(ValueError, match="Vendored license checksum mismatch"):
        pack_release.third_party_licenses(dependencies, release_tree)


@pytest.mark.parametrize("name,version", sorted(pack_release.INSTALLED_ONLY_DEPENDENCIES))
def test_installed_only_missing_text_is_explicit_and_version_scoped(release_tree, name, version):
    dependencies = pack_release.locked_dependencies(release_tree)
    distribution = pack_release.metadata.distribution(name)
    distribution.files = []
    report = pack_release.third_party_licenses(dependencies, release_tree)
    assert f"Component: {name}\nVersion: {version}\nScope: installed-only; not bundled" in report
    assert f"Unavailable: {name}=={version}: no license text" in report
    dependencies[name] = "0.0.0"
    distribution.version = "0.0.0"
    with pytest.raises(ValueError, match=rf"{name}==0.0.0: no license text"):
        pack_release.third_party_licenses(dependencies, release_tree)
