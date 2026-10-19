import argparse
import ctypes
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import uuid

import pytest

import default_paths
from default_paths import DefaultPathError, default_data_dir, legacy_candidates
from save_data import SaveDataError, add_data_dir_argument, resolve_data_dir


NATIVE_KNOWN_FOLDER_PATH = default_paths.known_folder_path
QA_ID = "71db9e63-45ae-4d63-b2e5-704e759b0029"


def forbidden(*args, **kwargs):
    pytest.fail("A pure path operation touched the host namespace or database contents")


@pytest.mark.parametrize("channel,relative", [
    ("", Path("EFTTaskAssistant")),
    ("preview", Path("EFTTaskAssistant-Preview")),
    ("qa-" + QA_ID, Path("EFTTaskAssistant-QA") / QA_ID),
])
def test_default_is_independent_of_exe_cwd_localappdata_and_host(
    tmp_path, monkeypatch, isolated_known_folders, channel, relative,
):
    monkeypatch.setenv(default_paths.CHANNEL_VARIABLE, channel)
    expected = isolated_known_folders["SavedGames"] / relative
    monkeypatch.setattr(Path, "resolve", forbidden)
    for index in range(2):
        location = tmp_path / f"build-{index}"
        location.mkdir()
        monkeypatch.chdir(location)
        monkeypatch.setattr(sys, "executable", str(location / "renamed.exe"))
        monkeypatch.setattr(sys, "_MEIPASS", str(location / "onefile"), raising=False)
        monkeypatch.setenv("LOCALAPPDATA", str(location / "host-cache"))
        monkeypatch.setenv("USERPROFILE", str(location / "host-profile"))
        monkeypatch.setenv("PACKAGE_FAMILY_NAME", f"fake-host-{index}")
        assert resolve_data_dir() == expected
    assert not expected.parent.exists()


def test_redirected_known_folder_is_used_without_creating_it(tmp_path, monkeypatch, isolated_known_folders):
    relocated = tmp_path / "redirected" / "游戏存档"
    monkeypatch.setattr(default_paths, "known_folder_path", lambda name: (
        relocated if name == "SavedGames" else isolated_known_folders[name]
    ))
    monkeypatch.setattr(default_paths, "_IS_WINDOWS", True)
    assert resolve_data_dir() == relocated / "EFTTaskAssistant"
    assert not relocated.exists()


def test_explicit_environment_is_closed_and_never_queries_real_user(tmp_path, monkeypatch):
    monkeypatch.setattr(default_paths, "known_folder_path", forbidden)
    monkeypatch.setattr(Path, "home", forbidden)
    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setenv(default_paths.CHANNEL_VARIABLE, "invalid-in-host")
    profile = tmp_path / "synthetic"
    assert resolve_data_dir(environ={"USERPROFILE": str(profile), "LOCALAPPDATA": "ignored-relative"}) == (
        profile / "Saved Games" / "EFTTaskAssistant"
    )
    assert resolve_data_dir(environ={"HOME": str(profile)}) == profile / "Saved Games" / "EFTTaskAssistant"
    for environment in ({}, {"LOCALAPPDATA": str(profile)}, {"USERPROFILE": "~"}, {"USERPROFILE": "relative"}):
        with pytest.raises(SaveDataError):
            resolve_data_dir(environ=environment)
    assert legacy_candidates(tmp_path / "target", environ={}) == []
    assert not profile.exists()


@pytest.mark.parametrize("channel", [
    "production", "PREVIEW", " preview", "preview/other", "../escape", "qa-x", "qa-" + QA_ID.upper(),
    "qa-{" + QA_ID + "}", "qa-" + QA_ID.replace("-", ""),
])
def test_channels_are_allowlisted_before_any_host_access(tmp_path, monkeypatch, channel):
    monkeypatch.setattr(default_paths, "known_folder_path", forbidden)
    environment = {default_paths.CHANNEL_VARIABLE: channel, "USERPROFILE": str(tmp_path)}
    with pytest.raises(SaveDataError):
        resolve_data_dir(environ=environment)
    with pytest.raises(DefaultPathError):
        legacy_candidates(tmp_path, environ=environment)


def test_qa_ids_isolate_runs_but_are_stable_when_reused(tmp_path):
    environment = {"USERPROFILE": str(tmp_path), default_paths.CHANNEL_VARIABLE: "qa-" + QA_ID}
    first = resolve_data_dir(environ=environment)
    assert resolve_data_dir(environ=dict(environment)) == first
    environment[default_paths.CHANNEL_VARIABLE] = "qa-" + str(uuid.uuid4())
    assert resolve_data_dir(environ=environment) != first


def test_explicit_data_dir_bypasses_defaults_and_channel_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(default_paths, "known_folder_path", forbidden)
    monkeypatch.setenv(default_paths.CHANNEL_VARIABLE, "invalid")
    explicit = tmp_path / "explicit"
    parser = argparse.ArgumentParser()
    add_data_dir_argument(parser)
    assert resolve_data_dir(parser.parse_args(["--data-dir", str(explicit)]).data_dir) == explicit
    assert resolve_data_dir(explicit, environ={}) == explicit
    assert not explicit.exists()
    for relative in ("", "relative", "../saves"):
        with pytest.raises(ValueError):
            resolve_data_dir(relative)


def test_known_folder_failure_cannot_silently_change_root(tmp_path, monkeypatch):
    def unavailable(name):
        raise DefaultPathError("Known Folder unavailable")

    monkeypatch.setattr(default_paths, "_IS_WINDOWS", True)
    monkeypatch.setattr(default_paths, "known_folder_path", unavailable)
    with pytest.raises(SaveDataError, match="Known Folder unavailable"):
        resolve_data_dir()
    with pytest.raises(DefaultPathError):
        legacy_candidates(tmp_path)


@pytest.mark.parametrize("parent", ["profile-appdata", "relocated-local", "relocated-roaming"])
def test_saved_games_under_appdata_is_rejected(tmp_path, monkeypatch, parent):
    folders = {
        "Profile": tmp_path / "profile",
        "LocalAppData": tmp_path / "relocated-local",
        "RoamingAppData": tmp_path / "relocated-roaming",
    }
    appdata = folders["Profile"] / "AppData" if parent == "profile-appdata" else tmp_path / parent
    folders["SavedGames"] = appdata / "Saved Games"
    monkeypatch.setattr(default_paths, "_IS_WINDOWS", True)
    monkeypatch.setattr(default_paths, "known_folder_path", lambda name: folders[name])
    with pytest.raises(SaveDataError, match="AppData"):
        resolve_data_dir()


def test_synthetic_profile_can_live_under_the_host_temp_appdata(tmp_path, monkeypatch):
    monkeypatch.setattr(default_paths, "known_folder_path", forbidden)
    profile = tmp_path / "AppData" / "Local" / "Temp" / "fixture-user"
    assert default_data_dir(environ={"USERPROFILE": str(profile)}) == profile / "Saved Games" / "EFTTaskAssistant"


def install_fake_known_folder_api(monkeypatch, path, result=0, allocate=True):
    allocation = ctypes.create_unicode_buffer(str(path))
    calls = []
    freed = []

    def query(folder_id, flags, token, output):
        calls.append((ctypes.string_at(folder_id, 16), flags, token))
        if allocate:
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.cast(allocation, ctypes.c_void_p)
        return result

    def free(buffer):
        freed.append(buffer.value)

    def load(name, **kwargs):
        return SimpleNamespace(SHGetKnownFolderPath=query) if name == "shell32" else SimpleNamespace(CoTaskMemFree=free)

    monkeypatch.setattr(default_paths, "_IS_WINDOWS", True)
    monkeypatch.setattr(ctypes, "WinDLL", load, raising=False)
    return allocation, calls, freed


def test_native_api_uses_saved_games_guid_flags_and_frees_allocated_unicode(tmp_path, monkeypatch):
    path = tmp_path / "保存的游戏"
    allocation, calls, freed = install_fake_known_folder_api(monkeypatch, path)
    assert NATIVE_KNOWN_FOLDER_PATH("SavedGames") == path
    assert calls == [(uuid.UUID("4c5c32ff-bb9d-43b0-b5b4-2d72e54eaaa4").bytes_le, 0x14000, None)]
    assert freed == [ctypes.addressof(allocation)]
    assert not path.exists()


@pytest.mark.parametrize("result,allocate", [(-2147467259, True), (-2147024809, False), (0, False)])
def test_native_api_failure_still_frees_buffer(tmp_path, monkeypatch, result, allocate):
    allocation, calls, freed = install_fake_known_folder_api(monkeypatch, tmp_path, result, allocate)
    with pytest.raises(DefaultPathError, match="HRESULT"):
        NATIVE_KNOWN_FOLDER_PATH("SavedGames")
    assert len(calls) == 1
    assert freed == [ctypes.addressof(allocation) if allocate else None]


def test_native_api_unavailable_has_no_fallback(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr(default_paths, "_IS_WINDOWS", True)
    monkeypatch.setattr(ctypes, "WinDLL", unavailable, raising=False)
    with pytest.raises(DefaultPathError, match="no fallback"):
        NATIVE_KNOWN_FOLDER_PATH("SavedGames")


def test_legacy_candidates_preserve_two_nonempty_roots_without_reading_databases(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    local = profile / "AppData" / "Local"
    legacy = local / "EFTTaskAssistant"
    package = local / "Packages" / "OpenAI.Codex_fixture" / "LocalCache" / "Local" / "EFTTaskAssistant"
    target = tmp_path / "new-default"
    for index, directory in enumerate((legacy, package, target)):
        directory.mkdir(parents=True)
        (directory / "tasks.sqlite3").write_bytes(f"opaque fixture {index}".encode())
    (target / "active-dataset.json").write_bytes(b"opaque manifest")
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tmp_path.rglob("*") if path.is_file()}
    with monkeypatch.context() as probes:
        probes.setattr(sqlite3, "connect", forbidden)
        probes.setattr(Path, "read_bytes", forbidden)
        probes.setattr(Path, "read_text", forbidden)
        probes.setattr(Path, "resolve", forbidden)
        probes.setattr(default_paths, "known_folder_path", forbidden)
        candidates = legacy_candidates(target, environ={"USERPROFILE": str(profile), "LOCALAPPDATA": str(local)})
    assert isinstance(candidates, list)
    assert candidates == [legacy, package]
    assert all(path.is_absolute() for path in candidates)
    assert target not in candidates
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before


@pytest.mark.parametrize("branch", [Path("LocalCache") / "Local", Path("LocalCache") / "Roaming", Path("LocalState")])
def test_package_layouts_are_directory_metadata_only(tmp_path, branch):
    local = tmp_path / "local"
    packaged = local / "Packages" / "host_fixture" / branch / "EFTTaskAssistant"
    packaged.mkdir(parents=True)
    assert packaged in legacy_candidates(tmp_path / "root", environ={"LOCALAPPDATA": str(local)})


def test_production_discovery_includes_native_environment_and_profile_defaults(tmp_path, monkeypatch):
    folders = {
        "LocalAppData": tmp_path / "native-local",
        "RoamingAppData": tmp_path / "native-roaming",
        "Profile": tmp_path / "profile",
    }
    monkeypatch.setattr(default_paths, "_IS_WINDOWS", True)
    monkeypatch.setattr(default_paths, "known_folder_path", lambda name: folders[name])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "launcher-local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "launcher-roaming"))
    target = folders["LocalAppData"] / "EFTTaskAssistant"
    candidates = legacy_candidates(target)
    assert candidates == [
        tmp_path / "launcher-local" / "EFTTaskAssistant",
        folders["Profile"] / "AppData" / "Local" / "EFTTaskAssistant",
        folders["RoamingAppData"] / "EFTTaskAssistant",
        tmp_path / "launcher-roaming" / "EFTTaskAssistant",
    ]
    assert len(candidates) == len(set(candidates))


def test_qa_discovery_only_uses_process_legacy_environment(tmp_path, monkeypatch):
    local = tmp_path / "qa" / "legacy-env"
    monkeypatch.setattr(default_paths, "known_folder_path", forbidden)
    monkeypatch.setattr(Path, "home", forbidden)
    monkeypatch.setenv(default_paths.CHANNEL_VARIABLE, "qa-" + QA_ID)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("USERPROFILE", "invalid-and-never-read")
    monkeypatch.setenv("APPDATA", "invalid-and-never-read")
    assert legacy_candidates(tmp_path / "target") == [local / "EFTTaskAssistant"]
    monkeypatch.delenv("LOCALAPPDATA")
    with pytest.raises(DefaultPathError, match="QA legacy"):
        legacy_candidates(tmp_path / "target")


def test_preview_includes_historical_unlabelled_legacy_roots(tmp_path):
    environment = {"LOCALAPPDATA": str(tmp_path), default_paths.CHANNEL_VARIABLE: "preview"}
    assert legacy_candidates(tmp_path / "new", environment) == [
        tmp_path / "EFTTaskAssistant", tmp_path / "EFTTaskAssistant-Preview",
    ]


def test_discovery_errors_do_not_claim_old_saves_are_absent(tmp_path, monkeypatch):
    packages = tmp_path / "local" / "Packages"
    packages.mkdir(parents=True)

    def denied(path):
        raise PermissionError("fixture")

    monkeypatch.setattr(os, "scandir", denied)
    with pytest.raises(DefaultPathError, match="old saves may still exist"):
        legacy_candidates(tmp_path / "root", {"LOCALAPPDATA": str(packages.parent)})


def test_discovery_does_not_walk_package_reparse_points(tmp_path, monkeypatch):
    packages = tmp_path / "local" / "Packages"
    package = packages / "host_fixture"
    (package / "LocalCache" / "Local" / "EFTTaskAssistant").mkdir(parents=True)
    real_lstat = Path.lstat

    def metadata(path):
        if path == package:
            return SimpleNamespace(st_mode=0o40755, st_file_attributes=0x400)
        return real_lstat(path)

    monkeypatch.setattr(Path, "lstat", metadata)
    assert legacy_candidates(tmp_path / "root", {"LOCALAPPDATA": str(packages.parent)}) == [
        packages.parent / "EFTTaskAssistant",
    ]


def test_invalid_candidate_inputs_do_not_probe_host(tmp_path, monkeypatch):
    monkeypatch.setattr(default_paths, "known_folder_path", forbidden)
    with pytest.raises(DefaultPathError):
        legacy_candidates("relative", {})
    with pytest.raises(DefaultPathError):
        legacy_candidates(tmp_path, {"LOCALAPPDATA": "relative"})
