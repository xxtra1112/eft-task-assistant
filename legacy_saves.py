from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from save_data import SaveDataError
from save_runtime import RuntimeStatus, export_runtime_status


def discover_legacy_saves(root: Path, candidates: Iterable[Path]) -> RuntimeStatus | None:
    root = Path(root)
    current = export_runtime_status(root)
    if current["status"] != "empty":
        return None
    sources = []
    seen = {os.path.normcase(str(root.resolve()))}
    for candidate in candidates:
        candidate = Path(candidate)
        if not candidate.is_absolute():
            raise ValueError("Legacy candidates must be absolute.")
        identity = os.path.normcase(str(candidate.resolve()))
        if identity in seen:
            continue
        seen.add(identity)
        if not any((candidate / name).exists() for name in ("tasks.sqlite3", "players.sqlite3", "active-dataset.json")):
            if not (candidate / "players").is_dir() or not next((candidate / "players").glob("*.sqlite3"), None):
                continue
        try:
            inventory = export_runtime_status(candidate)
            databases = inventory["databases"]
            if not databases and not inventory.get("datasets"):
                continue
            counts = {name: sum(database["counts"].get(name, 0) for database in databases)
                      for name in ("tasks", "profiles")}
            sources.append({"path": str(candidate), "databases": databases, "counts": counts,
                            "available": True, "notice": "仅复制到独立目录；原文件保留，不合并其他存档。"})
        except (SaveDataError, OSError, ValueError) as error:
            sources.append({"path": str(candidate), "databases": [], "counts": {},
                            "available": False, "notice": str(error)})
    if not sources:
        return None
    return RuntimeStatus("legacy_import_required", root, reason="choose_previous_default_root",
                         legacy_roots=tuple(sources))
