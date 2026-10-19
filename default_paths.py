"""Stable save roots and read-only legacy directory discovery; no import-time I/O."""

from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import Mapping
import uuid


CHANNEL_VARIABLE = "EFT_TASK_ASSISTANT_CHANNEL"
_IS_WINDOWS = os.name == "nt"
_KNOWN_FOLDERS = {
    "SavedGames": "4c5c32ff-bb9d-43b0-b5b4-2d72e54eaaa4",
    "LocalAppData": "f1b32785-6fba-4fcf-9d55-7b8e7f157091",
    "RoamingAppData": "3eb685db-65f9-4cf6-a03a-e3ef65729f3d",
    "Profile": "5e6c858f-0e22-4760-9afe-ea3317b67173",
}
_KNOWN_FOLDER_FLAGS = 0x00010000 | 0x00004000


class DefaultPathError(ValueError):
    """A stable default or a complete discovery could not be established."""


def _absolute(value: str | os.PathLike[str]) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise DefaultPathError("Default-path inputs must be absolute; no user or cwd expansion is performed.")
    return Path(os.path.normpath(path))


def known_folder_path(name: str) -> Path:
    """Query the current Windows user's configured folder without creating it.

    NO_PACKAGE_REDIRECTION controls the returned name, not subsequent file I/O.
    DONT_VERIFY permits absent folders; CREATE and DEFAULT_PATH are never used.
    """
    if not _IS_WINDOWS:
        raise DefaultPathError("Windows Known Folders are unavailable on this platform.")
    if name not in _KNOWN_FOLDERS:
        raise DefaultPathError("Unsupported Known Folder.")
    import ctypes

    class FolderGuid(ctypes.Structure):
        _fields_ = [
            ("data1", ctypes.c_uint32),
            ("data2", ctypes.c_uint16),
            ("data3", ctypes.c_uint16),
            ("data4", ctypes.c_ubyte * 8),
        ]

    folder_id = FolderGuid.from_buffer_copy(uuid.UUID(_KNOWN_FOLDERS[name]).bytes_le)
    buffer = ctypes.c_void_p()
    try:
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        allocator = ctypes.WinDLL("ole32", use_last_error=True)
        query = shell.SHGetKnownFolderPath
        query.argtypes = [ctypes.POINTER(FolderGuid), ctypes.c_uint32, ctypes.c_void_p,
                          ctypes.POINTER(ctypes.c_void_p)]
        query.restype = ctypes.c_int32
        free = allocator.CoTaskMemFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = None
    except (OSError, AttributeError):
        raise DefaultPathError("Windows Known Folder API is unavailable; no fallback root was selected.") from None
    try:
        result = query(ctypes.byref(folder_id), _KNOWN_FOLDER_FLAGS, None, ctypes.byref(buffer))
        if result != 0 or not buffer.value:
            raise DefaultPathError(f"Windows Known Folder query failed (HRESULT 0x{result & 0xffffffff:08x}).")
        return _absolute(ctypes.wstring_at(buffer))
    finally:
        free(buffer)


def _channel(environment: Mapping[str, str]) -> str:
    channel = environment.get(CHANNEL_VARIABLE, "")
    if channel in ("", "preview"):
        return channel
    if channel.startswith("qa-"):
        try:
            identifier = str(uuid.UUID(channel[3:]))
        except ValueError:
            identifier = ""
        if identifier and channel == "qa-" + identifier:
            return channel
    raise DefaultPathError("EFT_TASK_ASSISTANT_CHANNEL must be unset, preview, or qa-<canonical lowercase UUID>.")


def _environment_path(environment: Mapping[str, str], name: str) -> Path | None:
    value = environment.get(name)
    return _absolute(value) if value else None


def default_data_dir(*, environ: Mapping[str, str] | None = None) -> Path:
    """Select a root without filesystem probes or writes.

    An explicit environ is a closed synthetic namespace: USERPROFILE (or HOME)
    supplies its Saved Games parent. It never queries Windows or Path.home().
    Normal callers omit environ and use the configured Windows Known Folder.
    """
    environment = os.environ if environ is None else environ
    channel = _channel(environment)
    if environ is not None:
        profile = _environment_path(environment, "USERPROFILE") or _environment_path(environment, "HOME")
        if profile is None:
            raise DefaultPathError("An explicit environ requires an absolute USERPROFILE or HOME.")
        saved_games = profile / "Saved Games"
    elif _IS_WINDOWS:
        saved_games = _absolute(known_folder_path("SavedGames"))
        appdata_roots = (
            _absolute(known_folder_path("Profile")) / "AppData",
            _absolute(known_folder_path("LocalAppData")),
            _absolute(known_folder_path("RoamingAppData")),
        )
        if any(saved_games.is_relative_to(base) for base in appdata_roots):
            raise DefaultPathError("Saved Games points into AppData; a stable default cannot be guaranteed.")
    else:
        saved_games = _absolute(Path.home()) / "Saved Games"
    if channel == "preview":
        return saved_games / "EFTTaskAssistant-Preview"
    if channel.startswith("qa-"):
        return saved_games / "EFTTaskAssistant-QA" / channel[3:]
    return saved_games / "EFTTaskAssistant"


def _directory_without_redirection(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(metadata.st_mode) and not (
        getattr(metadata, "st_file_attributes", 0) & 0x400
    )


def legacy_candidates(
    root: str | os.PathLike[str], environ: Mapping[str, str] | None = None,
) -> list[Path]:
    """Return candidate absolute roots, never DB contents or an import decision.

    Direct old defaults are returned even if absent. Package candidates require
    an existing product directory, and package junctions/symlinks aren't walked.
    QA discovery only uses LOCALAPPDATA from the supplied/process environment.
    Access errors abort discovery instead of pretending there are no old saves.
    """
    target = _absolute(root)
    environment = os.environ if environ is None else environ
    channel = _channel(environment)
    local_bases = []
    roaming_bases = []
    process_local = _environment_path(environment, "LOCALAPPDATA")
    if process_local is not None:
        local_bases.append(process_local)
    if not channel.startswith("qa-"):
        if environ is None and _IS_WINDOWS:
            local_bases.append(known_folder_path("LocalAppData"))
            roaming_bases.append(known_folder_path("RoamingAppData"))
            profile = known_folder_path("Profile")
        else:
            profile = _environment_path(environment, "USERPROFILE") or _environment_path(environment, "HOME")
        if profile is not None:
            local_bases.append(profile / "AppData" / "Local")
        roaming = _environment_path(environment, "APPDATA")
        if roaming is not None:
            roaming_bases.append(roaming)
    elif process_local is None:
        raise DefaultPathError("QA legacy discovery requires an absolute LOCALAPPDATA sandbox.")
    product_names = ("EFTTaskAssistant", "EFTTaskAssistant-Preview") if channel == "preview" else ("EFTTaskAssistant",)
    candidates = []
    seen = {os.path.normcase(str(target))}

    def include(path: Path) -> None:
        candidate = _absolute(path)
        key = os.path.normcase(str(candidate))
        if key not in seen:
            seen.add(key)
            candidates.append(candidate)

    for base in (*local_bases, *roaming_bases):
        for product in product_names:
            include(base / product)
    scanned = set()
    try:
        for base in local_bases:
            packages = base / "Packages"
            key = os.path.normcase(str(packages))
            if key in scanned:
                continue
            scanned.add(key)
            if not _directory_without_redirection(packages):
                continue
            with os.scandir(packages) as entries:
                package_paths = sorted((Path(entry.path) for entry in entries), key=lambda path: path.name.casefold())
            for package in package_paths:
                if not _directory_without_redirection(package):
                    continue
                for relative in (Path("LocalCache") / "Local", Path("LocalCache") / "Roaming", Path("LocalState")):
                    parent = package
                    for component in relative.parts:
                        parent = parent / component
                        if not _directory_without_redirection(parent):
                            break
                    else:
                        for product in product_names:
                            candidate = parent / product
                            if _directory_without_redirection(candidate):
                                include(candidate)
    except OSError:
        raise DefaultPathError("Legacy package directory discovery failed; old saves may still exist.") from None
    return candidates
