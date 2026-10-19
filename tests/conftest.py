import logging
from pathlib import Path

import pytest

import default_paths


@pytest.fixture(autouse=True)
def isolated_known_folders(tmp_path, monkeypatch):
    profile = tmp_path / "windows-user"
    folders = {
        "Profile": profile,
        "SavedGames": profile / "Saved Games",
        "LocalAppData": profile / "AppData" / "Local",
        "RoamingAppData": profile / "AppData" / "Roaming",
    }
    monkeypatch.setattr(default_paths, "known_folder_path", lambda name: folders[name])
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: profile))
    monkeypatch.setenv("USERPROFILE", str(profile))
    monkeypatch.setenv("HOME", str(profile))
    monkeypatch.setenv("LOCALAPPDATA", str(folders["LocalAppData"]))
    monkeypatch.setenv("APPDATA", str(folders["RoamingAppData"]))
    monkeypatch.delenv(default_paths.CHANNEL_VARIABLE, raising=False)
    yield folders
    logger = logging.getLogger("eft_task_assistant")
    for handler in list(logger.handlers):
        filename = getattr(handler, "baseFilename", None)
        if filename and Path(filename).is_relative_to(tmp_path):
            handler.close()
            logger.removeHandler(handler)
