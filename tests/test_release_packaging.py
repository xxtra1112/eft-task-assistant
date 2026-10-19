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
    )
    expected = {
        "EFTTaskAssistant-v1.3.0-Windows-x64.exe", "README.md", "README.en.md", "LICENSE.txt",
        "THIRD_PARTY_NOTICES.md", "docs/data-sources.md", "docs/preload-evidence.md",
        "docs/reemr-usage.md", "docs/route-sync.md", "docs/save-data.md", "docs/release-checklist.md",
        "docs/releases/v1.3.0.md", "BUILD-INFO.json", "SHA256SUMS.txt",
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
        pack_release.package_release(release_tree, executable, output, "1.3.0", SOURCE_COMMIT)
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
        pack_release.package_release(release_tree, executable_fixture(release_tree), output, None, SOURCE_COMMIT)
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
    artifacts = pack_release.package_release(release_tree, executable, output, None, SOURCE_COMMIT)
    before = {path: path.read_bytes() for path in artifacts.values()}
    with pytest.raises(ValueError, match="already exist"):
        pack_release.package_release(release_tree, executable, output, None, SOURCE_COMMIT)
    assert {path: path.read_bytes() for path in artifacts.values()} == before


def test_runtime_requirements_are_satisfied_by_the_fixed_lock():
    lines = (PROJECT_ROOT / "requirements-lock-windows.txt").read_text().splitlines()
    versions = {Requirement(line).name.lower().replace("_", "-"): Requirement(line).specifier for line in lines}
    assert len(versions) == 23
    for line in (PROJECT_ROOT / "requirements.txt").read_text().splitlines():
        if not line.strip():
            continue
        requirement = Requirement(line)
        pinned = next(iter(versions[requirement.name.lower().replace("_", "-")])).version
        assert pinned in requirement.specifier
    assert (PROJECT_ROOT / "requirements-build.txt").read_text().splitlines() == [
        "-r requirements.txt", "-r requirements-lock-windows.txt",
    ]
