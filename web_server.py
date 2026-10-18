from __future__ import annotations

import argparse
import errno
import ipaddress
import json
import logging
import math
import mimetypes
import os
import re
import socket
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone
from difflib import SequenceMatcher
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import cv2
import numpy as np
import qrcode

from catalog import (
    CatalogError,
    is_key_item_name,
)
from diagnostics import configure_logging, log_event, log_path
from point_images import supplement_verified_point_images
from hideout_data import get_hideout_catalog
from tarkov_dev_catalog import fetch_tarkov_dev_catalog, fetch_tarkov_dev_task_detail
from tarkov_dev_maps import (
    fetch_tarkov_dev_map_data,
    fetch_tarkov_dev_map_floor_image,
    fetch_tarkov_dev_map_index,
)
from players import (
    MOBILE_PAIRING_LIFETIME_SECONDS,
    SESSION_LIFETIME_SECONDS,
    Player,
    PlayerAuthStore,
)
from recognition import MERCHANT_CARD_ORDER, PageAnalyzer, ScreenAnalysis, ScreenKind
from storage import GAME_MODES, Profile, Task, TaskStore, default_database_path, normalize_text
from task_requirements import filter_assault_weapon_items


MODE_LABELS = {"pve": "PvE", "regular": "PvP", "pvp-season": "赛季 PvP"}
WEB_ROOT = Path(__file__).parent / "web"
SCREENSHOT_TASK_MATCH_THRESHOLD = 0.8
SCREENSHOT_TASK_CJK_MATCH_THRESHOLD = 0.72
SCREENSHOT_TASK_OCR_CONFIDENCE = 0.65
SCREENSHOT_TASK_MIN_FUZZY_LENGTH = 5
SCREENSHOT_TASK_AMBIGUITY_MARGIN = 0.08
CAPTURE_HISTORY_LIMIT = 10
CATALOG_MATCH_PENDING_WARNING = "任务资料目录尚未就绪；截图已保存，目录同步后会自动补匹配。"
CAPTURE_PENDING_LIMIT = 8
CAPTURE_ACTIVE_STATES = {"waiting_for_device", "capturing", "queued", "processing"}
MAX_CAPTURE_BYTES = 16 * 1024 * 1024
MAX_CAPTURE_PIXELS = 20_000_000
CAPTURE_DECODE_SLOTS = threading.BoundedSemaphore(2)
JPEG_START_OF_FRAME_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}


def _jpeg_dimensions(jpeg: bytes) -> tuple[int, int] | None:
    if len(jpeg) < 4 or jpeg[:2] != b"\xff\xd8":
        return None
    offset = 2
    while offset < len(jpeg):
        if jpeg[offset] != 0xFF:
            return None
        while offset < len(jpeg) and jpeg[offset] == 0xFF:
            offset += 1
        if offset >= len(jpeg):
            return None
        marker = jpeg[offset]
        offset += 1
        if marker == 0xD9 or marker == 0xDA:
            return None
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        if offset + 2 > len(jpeg):
            return None
        segment_length = int.from_bytes(jpeg[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(jpeg):
            return None
        if marker in JPEG_START_OF_FRAME_MARKERS:
            if segment_length < 7:
                return None
            height = int.from_bytes(jpeg[offset + 3 : offset + 5], "big")
            width = int.from_bytes(jpeg[offset + 5 : offset + 7], "big")
            return (width, height) if width and height else None
        offset += segment_length
    return None


def _point_image_urls(*values: Any) -> list[str]:
    urls: list[str] = []
    for value in values:
        entries = value if isinstance(value, (list, tuple)) else [value]
        for entry in entries:
            if isinstance(entry, dict):
                entry = entry.get("url") or entry.get("src") or entry.get("image_url") or ""
            image_url = str(entry or "").strip()
            parsed = urlparse(image_url)
            if (
                parsed.scheme == "https"
                and parsed.netloc == "www.eftarkov.com"
                and re.fullmatch(r"/uploads/infoImg/[A-Za-z0-9._-]+\.(?:webp|png|jpe?g)", parsed.path, re.IGNORECASE)
                and image_url not in urls
            ):
                urls.append(image_url)
                if len(urls) >= 24:
                    return urls
    return urls


def _map_annotation_categories(marker: dict[str, Any]) -> list[str]:
    marker_type = str(marker.get("marker_type", "")).strip().casefold()
    category = str(marker.get("category", "")).strip().casefold()
    category_path = str(marker.get("category_path", "")).strip().casefold()
    icon_path = urlparse(str(marker.get("icon_url") or marker.get("icon") or "")).path.casefold()
    if marker_type == "label":
        return ["location"]
    if marker_type != "point":
        return []
    if "撤离点 - pmc" in category_path or "extract_pmc" in icon_path:
        return ["pmc-exit"]
    if "撤离点 - scav" in category_path or "extract_scav" in icon_path:
        return ["scav-exit"]
    if "撤离点 - 转移点" in category_path or "extract_transit" in icon_path:
        return ["transfer"]
    if category == "pmc" and "出生点" not in category_path:
        return ["pmc-exit"]
    if category == "scav" and "出生点" not in category_path:
        return ["scav-exit"]
    if category == "转移点":
        return ["transfer"]
    return []


class APIError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _profile_json(profile: Profile) -> dict[str, Any]:
    result = asdict(profile)
    result["mode_label"] = MODE_LABELS.get(profile.game_mode, profile.game_mode)
    return result


def _task_json(task: Task) -> dict[str, Any]:
    return asdict(task)


def _mobile_lan_info(server: ThreadingHTTPServer) -> dict[str, Any]:
    bound_host = str(server.server_address[0])
    try:
        bound_ip = ipaddress.ip_address(bound_host)
    except ValueError:
        bound_ip = None
    if bound_ip is not None and bound_ip.version == 4 and bound_ip.is_unspecified:
        addresses: set[str] = set()
        try:
            for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
                address = ipaddress.ip_address(result[4][0])
                if address.is_private and not address.is_loopback and not address.is_link_local and not address.is_unspecified:
                    addresses.add(str(address))
        except OSError:
            pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("192.0.2.1", 80))
                address = ipaddress.ip_address(probe.getsockname()[0])
                if address.is_private and not address.is_loopback and not address.is_link_local and not address.is_unspecified:
                    addresses.add(str(address))
        except OSError:
            pass
        lan_enabled = bool(addresses)
    elif bound_ip is not None and bound_ip.version == 4 and bound_ip.is_private and not bound_ip.is_loopback and not bound_ip.is_link_local:
        addresses = {str(bound_ip)}
        lan_enabled = True
    else:
        addresses = set()
        lan_enabled = False
    return {
        "lan_enabled": lan_enabled,
        "addresses": sorted(addresses, key=lambda value: int(ipaddress.ip_address(value))),
        "port": int(server.server_port),
        "pairing_lifetime_seconds": MOBILE_PAIRING_LIFETIME_SECONDS,
    }


def _analysis_json(analysis: ScreenAnalysis | None) -> dict[str, Any] | None:
    if analysis is None:
        return None
    return {
        "kind": analysis.kind.value,
        "trader": analysis.trader,
        "text_lines": analysis.text_lines,
        "task_page_confident": analysis.task_page_confident,
        "warning": analysis.warning,
        "diagnostics": analysis.diagnostics,
    }


def _analysis_from_json(value: Any) -> ScreenAnalysis | None:
    if not isinstance(value, dict):
        return None
    try:
        kind = ScreenKind(str(value.get("kind", "")))
    except ValueError:
        return None
    text_lines = value.get("text_lines", [])
    diagnostics = value.get("diagnostics", {})
    return ScreenAnalysis(
        kind=kind,
        trader=str(value["trader"]) if value.get("trader") is not None else None,
        text_lines=[str(line) for line in text_lines] if isinstance(text_lines, list) else [],
        task_page_confident=bool(value.get("task_page_confident", False)),
        warning=str(value.get("warning", "")),
        diagnostics=diagnostics if isinstance(diagnostics, dict) else {},
    )


def _task_title_variants(title: str) -> set[str]:
    variants = {normalize_text(title)}
    without_mode = re.sub(r"\s*[（(]\s*(?:pve|pvp|赛季)\s*[）)]\s*$", "", title, flags=re.IGNORECASE)
    variants.add(normalize_text(without_mode))
    without_part_number = re.sub(r"\s*[-—–]\s*\d+\s*$", "", without_mode)
    variants.add(normalize_text(without_part_number))
    return {variant for variant in variants if variant}


def _is_one_character_cjk_truncation(ocr_text: str, title_variant: str) -> bool:
    return (
        len(ocr_text) >= 3
        and len(title_variant) == len(ocr_text) + 1
        and bool(re.search(r"[\u4e00-\u9fff]", ocr_text))
        and bool(re.search(r"[\u4e00-\u9fff]", title_variant))
        and (title_variant.startswith(ocr_text) or title_variant.endswith(ocr_text))
    )


def _is_one_character_cjk_ocr_noise(ocr_text: str, title_variant: str) -> bool:
    return (
        len(title_variant) >= 2
        and len(ocr_text) == len(title_variant) + 1
        and bool(re.fullmatch(r"[\u4e00-\u9fff]+", title_variant))
        and bool(re.fullmatch(r"[\u4e00-\u9fff]+", ocr_text))
        and (ocr_text.startswith(title_variant) or ocr_text.endswith(title_variant))
    )


def _match_screenshot_task_candidates(
    analysis: ScreenAnalysis,
    catalog_tasks: list[dict[str, Any]],
    tracked_tasks: list[Task],
    capture_id: str,
    profile_id: int,
) -> list[dict[str, Any]]:
    if analysis.kind != ScreenKind.TRADER_TASKS or not analysis.task_page_confident or not analysis.trader:
        return []

    trader_key = normalize_text(analysis.trader)
    tracked_ids = {
        task.source_task_id
        for task in tracked_tasks
        if normalize_text(task.trader) == trader_key and task.source_task_id
    }
    tracked_titles = {
        normalize_text(task.title)
        for task in tracked_tasks
        if normalize_text(task.trader) == trader_key
    }
    matches_by_id: dict[str, dict[str, Any]] = {}
    match_ranks: dict[str, tuple[float, float]] = {}

    ocr_lines = analysis.diagnostics.get("task_list_ocr", [])
    ordered_lines = sorted(
        enumerate(line for line in ocr_lines if isinstance(line, dict)),
        key=lambda entry: (
            int(entry[1]["bounds"][1])
            if isinstance(entry[1].get("bounds"), (list, tuple)) and len(entry[1]["bounds"]) > 1
            else entry[0],
            int(entry[1]["bounds"][0])
            if isinstance(entry[1].get("bounds"), (list, tuple)) and entry[1]["bounds"]
            else 0,
            entry[0],
        ),
    )
    for _, line in ordered_lines:
        text = str(line.get("text", "")).strip()
        normalized_text = normalize_text(text)
        try:
            ocr_confidence = float(line.get("confidence", 0.0))
        except (TypeError, ValueError):
            continue
        if not normalized_text or ocr_confidence < SCREENSHOT_TASK_OCR_CONFIDENCE:
            continue

        raw_bounds = line.get("bounds")
        if not isinstance(raw_bounds, (list, tuple)) or len(raw_bounds) != 4:
            continue
        try:
            x0, y0, x1, y1 = (int(value) for value in raw_bounds)
        except (TypeError, ValueError):
            continue
        if x1 < x0 or y1 < y0:
            continue
        text_bounds = {
            "x": x0,
            "y": y0,
            "width": x1 - x0,
            "height": y1 - y0,
        }

        ranked: list[tuple[float, dict[str, Any]]] = []
        for catalog_task in catalog_tasks:
            title = str(catalog_task.get("title", "")).strip()
            title_variants = _task_title_variants(title)
            if not title_variants:
                continue
            scores = [
                1.0 if normalized_text == variant else
                SequenceMatcher(None, normalized_text, variant, autojunk=False).ratio()
                for variant in title_variants
                if normalized_text == variant
                or min(len(normalized_text), len(variant)) >= SCREENSHOT_TASK_MIN_FUZZY_LENGTH
                or (re.search(r"[\u4e00-\u9fff]", normalized_text) and len(normalized_text) >= 4 and len(variant) >= 4)
                or _is_one_character_cjk_truncation(normalized_text, variant)
                or _is_one_character_cjk_ocr_noise(normalized_text, variant)
            ]
            if not scores:
                continue
            score = max(scores)
            contains_chinese = bool(re.search(r"[\u4e00-\u9fff]", normalized_text))
            threshold = (
                SCREENSHOT_TASK_CJK_MATCH_THRESHOLD
                if contains_chinese and min(len(normalized_text), max(map(len, title_variants))) >= 4
                else SCREENSHOT_TASK_MATCH_THRESHOLD
            )
            if score >= threshold:
                ranked.append((score, catalog_task))

        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            continue
        best_score, best_task = ranked[0]
        exact_matches = [task for score, task in ranked if score == 1.0]
        if exact_matches:
            exact_source_ids = {str(task.get("source_task_id", "")) for task in exact_matches}
            if len(exact_source_ids) > 1:
                continue
            best_task = exact_matches[0]
        elif len(ranked) > 1 and best_score - ranked[1][0] < SCREENSHOT_TASK_AMBIGUITY_MARGIN:
            continue

        source_task_id = str(best_task.get("source_task_id", ""))
        if not source_task_id:
            continue
        already_tracked = (
            source_task_id in tracked_ids
            or normalize_text(str(best_task.get("title", ""))) in tracked_titles
        )

        image_y = text_bounds["y"]
        image_x = text_bounds["x"]
        candidate = {
            "capture_id": capture_id,
            "profile_id": profile_id,
            "snapshot_id": int(best_task["snapshot_id"]),
            "source_task_id": source_task_id,
            "trader": str(best_task.get("trader", analysis.trader)),
            "title": str(best_task["title"]),
            "source_url": str(best_task.get("source_url", "")),
            "source_version": str(best_task.get("source_version", "")),
            "recognized_text": text,
            "ocr_confidence": round(ocr_confidence, 3),
            "match_score": round(best_score, 3),
            "match_type": "exact" if best_score == 1.0 else "fuzzy",
            "already_tracked": already_tracked,
            "match_region": "task_list",
            "bounds": text_bounds,
            "image_y": image_y,
            "image_x": image_x,
        }
        existing = matches_by_id.get(source_task_id)
        candidate_rank = (best_score, ocr_confidence)
        if existing is None or candidate_rank > match_ranks[source_task_id]:
            matches_by_id[source_task_id] = candidate
            match_ranks[source_task_id] = candidate_rank

    ordered_candidates = sorted(
        matches_by_id.values(),
        key=lambda item: (item["image_y"], item["image_x"], item["title"]),
    )
    for image_order, candidate in enumerate(ordered_candidates, start=1):
        candidate["image_order"] = image_order
    return ordered_candidates


class AssistantState:
    def __init__(
        self,
        store: TaskStore | None = None,
        player: Player | None = None,
        recover_empty_capture_candidates: bool = False,
        require_profile_name: bool = False,
    ) -> None:
        self.store = store or TaskStore()
        self.player = player
        self.recover_empty_capture_candidates = recover_empty_capture_candidates
        self.profile_name_required = require_profile_name
        self.analyzer = PageAnalyzer()
        self.lock = threading.RLock()
        self.capture_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="eft-capture")
        self.catalog_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="eft-catalog")
        self.map_detail_retry_after: dict[tuple[int, str], float] = {}
        default_profile_id = self.store.default_profile_id()
        profile_ids = {profile.id for profile in self.store.list_profiles()}
        try:
            stored_profile_id = int(self.store.get_app_setting("selected_profile_id", "") or "")
        except ValueError:
            stored_profile_id = default_profile_id
        self.selected_profile_id = (
            stored_profile_id if stored_profile_id in profile_ids else default_profile_id
        )
        self.store.set_app_setting("selected_profile_id", str(self.selected_profile_id))
        self.latest_capture_id: str | None = None
        self.selected_capture_id: str | None = None
        self.capture_records: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.catalog_busy = False
        self.catalog_status = "尚无任务目录；可手动同步 Tarkov.dev JSON API 公开资料。"
        self.catalog_error = ""
        self.catalog_pending_captures: set[tuple[str, int]] = set()
        self._closed = False
        self._restore_capture_records()
        selected_profile = next(
            (profile for profile in self.store.list_profiles() if profile.id == self.selected_profile_id),
            None,
        )
        if selected_profile and selected_profile.game_mode != "pvp-season":
            if self.store.latest_catalog_snapshot(selected_profile.game_mode):
                self._retry_catalog_pending_captures(selected_profile.game_mode)
            else:
                self.request_catalog_refresh()
        log_event(
            "application_started",
            database_path=str(self.store.path),
            log_path=str(log_path()),
            selected_profile_id=self.selected_profile_id,
            game_mode="pve",
            frontend="local_web",
            restored_capture_count=len(self.capture_records),
        )

    def _restore_capture_records(self) -> None:
        captures_to_resume: list[tuple[str, int]] = []
        for saved in self.store.list_capture_records(CAPTURE_HISTORY_LIMIT):
            candidates = [
                dict(candidate)
                for candidate in saved["task_candidates"]
                if isinstance(candidate, dict)
            ]
            analysis = _analysis_from_json(saved["analysis"])
            if (
                self.recover_empty_capture_candidates
                and not candidates
                and saved["state"] == "done"
                and analysis is not None
            ):
                candidates = self.screenshot_task_candidates(
                    analysis, int(saved["profile_id"]), str(saved["id"])
                )
                for candidate in candidates:
                    candidate["objectives"] = []
                    candidate["key_requirements"] = []
                    candidate["map_points"] = []
                    candidate["details_status"] = "loading"
                    candidate["details_error"] = ""
                    candidate["notification_status"] = "processing"
                    candidate["notification_message"] = "正在查询任务详情…"
                if candidates:
                    log_event(
                        "screenshot_candidates_recovered",
                        capture_id=saved["id"],
                        profile_id=saved["profile_id"],
                        source_task_ids=[item["source_task_id"] for item in candidates],
                    )
            for image_order, candidate in enumerate(candidates, start=1):
                candidate.setdefault("image_order", image_order)
                candidate.setdefault("image_y", image_order)
                candidate.setdefault("image_x", 0)
                candidate.setdefault("notification_status", "processing")
                if candidate["notification_status"] in {"processing", "importing"}:
                    candidate["details_status"] = (
                        "ready" if candidate.get("details_status") == "ready" else "loading"
                    )
                    captures_to_resume.append(
                        (saved["id"], int(candidate.get("profile_id", saved["profile_id"])))
                    )
            state = saved["state"]
            error = saved["error"]
            if state in CAPTURE_ACTIVE_STATES:
                state = "failed"
                error = "服务在此截图处理完成前重启，已恢复预览与记录。"
            record = {
                "id": saved["id"],
                "profile_id": saved["profile_id"],
                "source": saved["source"],
                "created_at": saved["created_at"],
                "state": state,
                "error": error,
                "jpeg": saved["jpeg"],
                "resolution": saved["resolution"],
                "analysis": analysis,
                "task_candidates": candidates,
            }
            self.capture_records[record["id"]] = record
            if (
                record["state"] == "done"
                and analysis
                and analysis.diagnostics.get("catalog_match_pending")
            ):
                self.catalog_pending_captures.add((record["id"], int(record["profile_id"])))
            self.store.save_pending_task_candidates(
                [candidate for candidate in candidates if not candidate.get("already_tracked")]
            )
            if state != saved["state"] or candidates != saved["task_candidates"]:
                self.store.save_capture_record({**record, "analysis": _analysis_json(record["analysis"])})
        self.latest_capture_id = next(reversed(self.capture_records), None)
        stored_capture_id = self.store.get_app_setting(
            f"selected_capture_id:{self.selected_profile_id}", ""
        )
        stored_capture = self.capture_records.get(stored_capture_id or "")
        if stored_capture and stored_capture["profile_id"] == self.selected_profile_id:
            self.selected_capture_id = stored_capture["id"]
        else:
            self.selected_capture_id = next(
                (
                    capture_id
                    for capture_id, capture in reversed(self.capture_records.items())
                    if capture["profile_id"] == self.selected_profile_id
                ),
                None,
            )
        if self.selected_capture_id:
            self.store.set_app_setting(
                f"selected_capture_id:{self.selected_profile_id}", self.selected_capture_id
            )
        self.store.prune_capture_records(CAPTURE_HISTORY_LIMIT)
        self._prune_capture_records_locked()
        self.recover_empty_capture_candidates = False
        resumed: set[tuple[str, int]] = set()
        for capture_id, profile_id in captures_to_resume:
            key = (capture_id, profile_id)
            if key in resumed:
                continue
            resumed.add(key)
            self.catalog_executor.submit(
                self._load_screenshot_candidate_details, capture_id, profile_id
            )

    def _persist_capture_locked(self, capture: dict[str, Any]) -> None:
        self.store.save_capture_record(
            {
                **capture,
                "analysis": _analysis_json(capture["analysis"]),
            }
        )

    def profiles(self) -> list[Profile]:
        return self.store.list_profiles()

    def select_profile(self, profile_id: int) -> Profile:
        profile = next((entry for entry in self.profiles() if entry.id == profile_id), None)
        if profile is None:
            raise APIError("找不到所选档案", 404)
        with self.lock:
            self.selected_profile_id = profile.id
            self.store.set_app_setting("selected_profile_id", str(profile.id))
            stored_capture_id = self.store.get_app_setting(f"selected_capture_id:{profile.id}", "")
            stored_capture = self.capture_records.get(stored_capture_id or "")
            if stored_capture and stored_capture["profile_id"] == profile.id:
                self.selected_capture_id = stored_capture["id"]
            else:
                self.selected_capture_id = next(
                    (
                        capture_id
                        for capture_id, capture in reversed(self.capture_records.items())
                        if capture["profile_id"] == profile.id
                    ),
                    None,
                )
                self.store.set_app_setting(
                    f"selected_capture_id:{profile.id}", self.selected_capture_id or ""
                )
        log_event(
            "profile_selected",
            profile_id=profile.id,
            game_mode=profile.game_mode,
            season_id=profile.season_id,
        )
        return profile

    def create_profile(self, name: str, game_mode: str, season_id: str = "") -> Profile:
        if game_mode not in GAME_MODES:
            raise APIError("未知游戏模式")
        try:
            profile = self.store.create_profile(name, game_mode, season_id)
        except ValueError as error:
            raise APIError(str(error)) from error
        self.select_profile(profile.id)
        log_event(
            "profile_created",
            profile_id=profile.id,
            name=profile.name,
            game_mode=profile.game_mode,
            season_id=profile.season_id,
        )
        return profile

    def name_initial_profile(self, name: str) -> Profile:
        with self.lock:
            if not self.profile_name_required:
                raise ValueError("当前档案无需首次命名。")
            profile = self.store.rename_profile(self.selected_profile_id, name)
            self.store.set_app_setting("profile_name_setup_complete", "1")
            self.profile_name_required = False
        log_event("local_profile_named", profile_id=profile.id, name=profile.name)
        return profile

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            selected_profile_id = self.selected_profile_id
            catalog_busy = self.catalog_busy
            catalog_status = self.catalog_status
            catalog_error = self.catalog_error
            profile_captures = [
                capture
                for capture in self.capture_records.values()
                if capture["profile_id"] == selected_profile_id
            ]
            selected_capture = self.capture_records.get(self.selected_capture_id or "")
            if selected_capture is None or selected_capture["profile_id"] != selected_profile_id:
                selected_capture = profile_captures[-1] if profile_captures else None
            if selected_capture is not None and self.selected_capture_id != selected_capture["id"]:
                self.selected_capture_id = selected_capture["id"]
                self.store.set_app_setting(
                    f"selected_capture_id:{selected_profile_id}", selected_capture["id"]
                )
            pending_count = self._pending_capture_count_locked()
            selected_state = selected_capture["state"] if selected_capture else "idle"
            status_labels = {
                "queued": "排队等待识别",
                "processing": "正在本地识别…",
                "done": "识别完成",
                "failed": "截图或识别失败",
                "idle": "等待截图",
            }
            selected_status = status_labels[selected_state]
            if selected_state == "done" and selected_capture and selected_capture["analysis"]:
                selected_status = f"识别完成：{selected_capture['analysis'].kind.value}"
            task_notifications = []
            for screenshot_record in profile_captures:
                ordered_candidates = sorted(
                    screenshot_record["task_candidates"],
                    key=lambda item: (
                        item.get("image_y", item.get("image_order", 0)),
                        item.get("image_x", 0),
                    ),
                )
                for index, candidate in enumerate(ordered_candidates, start=1):
                    task_notifications.append(
                        {
                            "capture_id": screenshot_record["id"],
                            "created_at": screenshot_record["created_at"],
                            "title": candidate.get("title", "未命名任务"),
                            "trader": candidate.get("trader", ""),
                            "recognized_text": candidate.get("recognized_text", ""),
                            "image_order": candidate.get("image_order", index),
                            "status": candidate.get("notification_status", "processing"),
                            "message": candidate.get("notification_message", ""),
                            "source_url": candidate.get("source_url", ""),
                        }
                    )
            capture = {
                "id": selected_capture["id"] if selected_capture else None,
                "available": bool(selected_capture and selected_capture["jpeg"]),
                "busy": pending_count > 0,
                "processing": selected_state in CAPTURE_ACTIVE_STATES,
                "pending_count": pending_count,
                "queue_full": pending_count >= CAPTURE_PENDING_LIMIT,
                "status": selected_status,
                "error": selected_capture["error"] if selected_capture else "",
                "task_notifications": task_notifications,
            }
            analysis = _analysis_json(selected_capture["analysis"]) if selected_capture else None
            analysis_profile_id = selected_capture["profile_id"] if selected_capture else None
            captures = [
                {
                    "id": item["id"],
                    "created_at": item["created_at"],
                    "state": item["state"],
                    "status": (
                        f"完成 · {item['analysis'].kind.value}"
                        if item["state"] == "done" and item["analysis"]
                        else status_labels[item["state"]]
                    ),
                    "analysis_kind": item["analysis"].kind.value if item["analysis"] else "",
                    "selected": item["id"] == capture["id"],
                }
                for item in reversed(profile_captures)
            ]
        profiles = self.profiles()
        selected_profile = next((profile for profile in profiles if profile.id == selected_profile_id), None)
        tasks = self.store.list_tasks(selected_profile_id)
        tracked_source_ids = {task.source_task_id for task in tasks if task.source_task_id}
        tracked_titles = {
            (normalize_text(task.trader), normalize_text(task.title))
            for task in tasks
        }
        task_candidates = [
            candidate
            for candidate in self.store.list_pending_task_candidates(selected_profile_id)
            if candidate.get("source_task_id") not in tracked_source_ids
            and (
                normalize_text(str(candidate.get("trader", ""))),
                normalize_text(str(candidate.get("title", ""))),
            ) not in tracked_titles
        ]
        catalog_snapshot = self.store.latest_catalog_snapshot(selected_profile.game_mode) if selected_profile else None
        catalog_snapshot_id = int(catalog_snapshot["id"]) if catalog_snapshot else None
        task_payloads = []
        for task in tasks:
            task_data = _task_json(task)
            cached_task = (
                self.store.get_catalog_task(catalog_snapshot_id, task.source_task_id)
                if catalog_snapshot_id and task.source_task_id
                else None
            )
            key_requirements = []
            if cached_task:
                source_objectives = cached_task.get("objectives", [])
                source_items = filter_assault_weapon_items(
                    source_objectives,
                    cached_task.get("key_requirements", []),
                )
                for item in source_items:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    if not is_key_item_name(name):
                        continue
                    item_id = str(item.get("item_id", "")).strip().lower()
                    key_requirements.append(
                        {
                            **item,
                            "name": name or "未命名钥匙",
                            "item_kind": "key",
                            "item_id": item_id,
                            "image_url": (
                                f"https://assets.tarkov.dev/{item_id}-icon.webp"
                                if re.fullmatch(r"[0-9a-f]{24}", item_id, re.I)
                                else ""
                            ),
                        }
                    )
            if not key_requirements:
                for line in task.objective.splitlines():
                    match = re.match(r"\s*(?:需要钥匙|钥匙)\s*[：:]\s*(.+?)\s*$", line, re.IGNORECASE)
                    if match:
                        name = match.group(1).strip()
                        if name and is_key_item_name(name):
                            key_requirements.append(
                                {"name": name, "item_id": "", "item_kind": "key"}
                            )
            task_data["key_requirements"] = key_requirements
            task_payloads.append(task_data)
        return {
            "player": self.player.public_data() if self.player else None,
            "profiles": [_profile_json(profile) for profile in profiles],
            "selected_profile_id": selected_profile_id,
            "profile_name_required": self.profile_name_required,
            "trader_order": list(MERCHANT_CARD_ORDER),
            "tasks": task_payloads,
            "catalog": catalog_snapshot,
            "catalog_busy": catalog_busy,
            "catalog_status": catalog_status,
            "catalog_error": catalog_error,
            "task_candidates": task_candidates,
            "capture": capture,
            "captures": captures,
            "analysis": analysis,
            "analysis_profile_id": analysis_profile_id,
            "log_path": str(log_path()),
            "hotkey": "Ctrl+Shift+F9",
        }

    def select_capture(self, capture_id: str) -> None:
        with self.lock:
            capture = self.capture_records.get(capture_id)
            if capture is None or capture["profile_id"] != self.selected_profile_id:
                raise APIError("找不到当前档案的这张截图。", 404)
            self.selected_capture_id = capture_id
            self.store.set_app_setting(
                f"selected_capture_id:{self.selected_profile_id}", capture_id
            )
        log_event("capture_selected", capture_id=capture_id, profile_id=capture["profile_id"])

    def request_catalog_refresh(self) -> dict[str, Any]:
        with self.lock:
            if self._closed:
                raise APIError("服务正在关闭", 503)
            if self.catalog_busy:
                return {"accepted": False, "message": "任务资料仍在同步。"}
            profile_id = self.selected_profile_id
            profile = next((item for item in self.profiles() if item.id == profile_id), None)
            if profile is None:
                raise APIError("找不到当前游戏档案", 404)
            game_mode = profile.game_mode
            self.catalog_busy = True
            self.catalog_status = "正在同步 Tarkov.dev JSON 任务资料……"
            self.catalog_error = ""
        log_event("catalog_sync_requested", game_mode=game_mode, profile_id=profile_id)
        self.catalog_executor.submit(self._refresh_catalog, game_mode, profile_id)
        return {"accepted": True, "message": "已开始同步任务资料。"}

    def _refresh_catalog(self, game_mode: str, profile_id: int) -> None:
        try:
            bundle = fetch_tarkov_dev_catalog(game_mode)
            snapshot_id = self.store.add_catalog_snapshot(
                source="Tarkov.dev community JSON API",
                source_url=f"https://json.tarkov.dev/{game_mode}/tasks",
                game_mode=game_mode,
                source_version=bundle.source_version or "unknown",
                game_build=None,
                verification_status="unverified",
                content_sha256=bundle.content_sha256,
                metadata=bundle.metadata,
            )
            self.store.save_catalog_tasks(snapshot_id, bundle.tasks)
            with self.lock:
                self.catalog_status = (
                    f"同步完成：Tarkov.dev 返回 {len(bundle.tasks)} 条任务；"
                    f"来源未标注游戏补丁版本。"
                )
                self.catalog_error = ""
            log_event(
                "catalog_sync_completed",
                profile_id=profile_id,
                game_mode=game_mode,
                snapshot_id=snapshot_id,
                source_version=bundle.source_version,
                task_count=len(bundle.tasks),
                content_sha256=bundle.content_sha256,
                metadata=bundle.metadata,
            )
            try:
                self._retry_catalog_pending_captures(game_mode)
            except Exception as error:
                log_event(
                    "screenshot_candidate_catalog_retry_failed",
                    level=logging.ERROR,
                    profile_id=profile_id,
                    game_mode=game_mode,
                    error=repr(error),
                    traceback=traceback.format_exc(),
                )
        except Exception as error:
            with self.lock:
                self.catalog_error = str(error)
                self.catalog_status = "同步失败；原有任务目录未更改。"
            log_event(
                "catalog_sync_failed",
                level=logging.ERROR,
                profile_id=profile_id,
                game_mode=game_mode,
                error=repr(error),
                traceback=traceback.format_exc(),
            )
        finally:
            with self.lock:
                self.catalog_busy = False

    def catalog_tasks(self, query: str = "", trader: str = "", limit: int = 60) -> list[dict[str, Any]]:
        with self.lock:
            profile_id = self.selected_profile_id
        profile = next((item for item in self.profiles() if item.id == profile_id), None)
        if profile is None:
            return []
        return self.store.search_catalog_tasks(profile.game_mode, query, trader, limit)

    def screenshot_task_candidates(
        self, analysis: ScreenAnalysis, profile_id: int, capture_id: str
    ) -> list[dict[str, Any]]:
        if analysis.kind != ScreenKind.TRADER_TASKS or not analysis.task_page_confident or not analysis.trader:
            return []
        profile = next((item for item in self.profiles() if item.id == profile_id), None)
        if profile is None:
            return []
        shared_catalog_path = default_database_path()
        if self.store.path.resolve() != shared_catalog_path.resolve():
            imported_snapshots = self.store.sync_catalog_from(
                shared_catalog_path, game_mode=profile.game_mode
            )
            if imported_snapshots:
                log_event(
                    "player_public_catalog_synced",
                    profile_id=profile_id,
                    game_mode=profile.game_mode,
                    snapshots=imported_snapshots,
                )
        catalog_tasks = self.store.search_catalog_tasks(
            profile.game_mode, trader=analysis.trader, limit=200
        )
        if not catalog_tasks:
            if not self.store.latest_catalog_snapshot(profile.game_mode):
                with self.lock:
                    self.catalog_pending_captures.add((capture_id, profile_id))
            log_event(
                "screenshot_task_catalog_unavailable",
                level=logging.WARNING,
                capture_id=capture_id,
                profile_id=profile_id,
                game_mode=profile.game_mode,
                trader=analysis.trader,
            )
            return []
        tracked_tasks = self.store.list_tasks(profile_id)
        pending_ids = {
            str(candidate.get("source_task_id", ""))
            for candidate in self.store.list_pending_task_candidates(profile_id)
            if candidate.get("details_status") != "error"
        }
        candidates = _match_screenshot_task_candidates(
            analysis, catalog_tasks, tracked_tasks, capture_id, profile_id
        )
        return [
            candidate
            for candidate in candidates
            if candidate.get("already_tracked")
            or candidate["source_task_id"] not in pending_ids
        ]

    def _retry_catalog_pending_captures(self, game_mode: str) -> None:
        with self.lock:
            pending = sorted(self.catalog_pending_captures)
        for capture_id, profile_id in pending:
            profile = next((item for item in self.profiles() if item.id == profile_id), None)
            if profile is None or profile.game_mode != game_mode:
                continue
            with self.lock:
                capture = self.capture_records.get(capture_id)
                if capture is None or capture.get("analysis") is None:
                    self.catalog_pending_captures.discard((capture_id, profile_id))
                    continue
                analysis = capture["analysis"]
            candidates = self.screenshot_task_candidates(analysis, profile_id, capture_id)
            new_candidates = [candidate for candidate in candidates if not candidate.get("already_tracked")]
            already_tracked = [candidate for candidate in candidates if candidate.get("already_tracked")]
            for candidate in candidates:
                candidate["objectives"] = []
                candidate["key_requirements"] = []
                candidate["map_points"] = []
                candidate["details_error"] = ""
                if candidate.get("already_tracked"):
                    candidate["details_status"] = "skipped"
                    candidate["notification_status"] = "already_tracked"
                    candidate["notification_message"] = "已在任务清单中；本次确认识别，不重复添加。"
                else:
                    candidate["details_status"] = "loading"
                    candidate["notification_status"] = "processing"
                    candidate["notification_message"] = "正在查询任务详情…"
            diagnostics = dict(analysis.diagnostics)
            diagnostics.pop("catalog_match_pending", None)
            base_warning = analysis.warning.replace(CATALOG_MATCH_PENDING_WARNING, "").strip()
            notices = []
            if new_candidates:
                notices.append(f"识别到 {len(new_candidates)} 个新任务，正在自动加入清单。")
            if already_tracked:
                notices.append(f"另外识别到 {len(already_tracked)} 个已在清单的任务，不会重复添加。")
            if not candidates:
                notices.append("任务资料目录已同步，但这张截图中没有匹配到目录任务。")
            analysis = replace(
                analysis,
                diagnostics=diagnostics,
                warning=" ".join(part for part in (base_warning, *notices) if part),
            )
            with self.lock:
                capture = self.capture_records.get(capture_id)
                if capture is None:
                    self.catalog_pending_captures.discard((capture_id, profile_id))
                    continue
                capture["analysis"] = analysis
                capture["task_candidates"] = candidates
                self.store.save_pending_task_candidates(new_candidates)
                self._persist_capture_locked(capture)
                self.catalog_pending_captures.discard((capture_id, profile_id))
            log_event(
                "screenshot_candidates_retried_after_catalog_sync",
                capture_id=capture_id,
                profile_id=profile_id,
                candidate_count=len(candidates),
                source_task_ids=[candidate["source_task_id"] for candidate in candidates],
            )
            if new_candidates:
                self.catalog_executor.submit(
                    self._load_screenshot_candidate_details, capture_id, profile_id
                )

    def _update_screenshot_candidate(
        self, capture_id: str, profile_id: int, source_task_id: str, updates: dict[str, Any]
    ) -> None:
        with self.lock:
            capture = self.capture_records.get(capture_id)
            if capture is not None:
                capture["task_candidates"] = [
                    {**candidate, **updates}
                    if candidate.get("source_task_id") == source_task_id
                    else candidate
                    for candidate in capture["task_candidates"]
                ]
                self._persist_capture_locked(capture)
        self.store.update_pending_task_candidate(profile_id, source_task_id, updates)

    def _load_screenshot_candidate_details(self, capture_id: str, profile_id: int) -> None:
        with self.lock:
            capture = self.capture_records.get(capture_id)
            candidates = [
                dict(candidate)
                for candidate in sorted(
                    capture["task_candidates"] if capture else [],
                    key=lambda item: (
                        item.get("image_y", item.get("image_order", 0)),
                        item.get("image_x", 0),
                    ),
                )
                if candidate.get("capture_id") == capture_id
                and candidate.get("profile_id") == profile_id
                and candidate.get("notification_status") in {"processing", "importing"}
            ]

        def load_one(candidate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
            try:
                task = self.load_catalog_task_details(
                    candidate["snapshot_id"], candidate["source_task_id"], profile_id
                )
                return candidate, task, ""
            except Exception as error:
                return candidate, None, str(error)

        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="eft-task-detail") as pool:
            results = list(pool.map(load_one, candidates))

        for candidate, task, error_message in results:
            source_task_id = candidate["source_task_id"]
            if task is None:
                self.store.delete_pending_task_candidate(profile_id, source_task_id)
                self._update_screenshot_candidate(
                    capture_id,
                    profile_id,
                    source_task_id,
                    {
                        "details_status": "error",
                        "details_error": error_message,
                        "notification_status": "failed",
                        "notification_message": f"详情读取失败：{error_message}",
                    },
                )
                log_event(
                    "screenshot_candidate_details_failed",
                    level=logging.WARNING,
                    capture_id=capture_id,
                    profile_id=profile_id,
                    source_task_id=source_task_id,
                    title=candidate.get("title", ""),
                    error=error_message,
                )
                continue

            objectives = task.get("objectives", [])
            if not objectives:
                error_message = "任务资料没有可导入的目标。"
                self.store.delete_pending_task_candidate(profile_id, source_task_id)
                self._update_screenshot_candidate(
                    capture_id,
                    profile_id,
                    source_task_id,
                    {
                        "details_status": "empty",
                        "details_error": error_message,
                        "notification_status": "failed",
                        "notification_message": error_message,
                    },
                )
                continue

            self._update_screenshot_candidate(
                capture_id,
                profile_id,
                source_task_id,
                {
                    "objectives": objectives,
                    "key_requirements": task.get("key_requirements", []),
                    "map_points": task.get("map_points", []),
                    "details_status": "ready",
                    "details_error": "",
                    "notification_status": "importing",
                    "notification_message": "详情已读取，正在加入任务清单…",
                },
            )
            try:
                self.import_catalog_task(
                    candidate["snapshot_id"], source_task_id, profile_id=profile_id
                )
            except Exception as error:
                message = str(error)
                self.store.delete_pending_task_candidate(profile_id, source_task_id)
                self._update_screenshot_candidate(
                    capture_id,
                    profile_id,
                    source_task_id,
                    {
                        "notification_status": "failed",
                        "notification_message": f"自动加入失败：{message}",
                    },
                )
                log_event(
                    "screenshot_candidate_auto_import_failed",
                    level=logging.WARNING,
                    capture_id=capture_id,
                    profile_id=profile_id,
                    source_task_id=source_task_id,
                    title=candidate.get("title", ""),
                    error=repr(error),
                )
                continue

            log_event(
                "screenshot_candidate_auto_imported",
                capture_id=capture_id,
                profile_id=profile_id,
                source_task_id=source_task_id,
                title=candidate.get("title", ""),
                image_order=candidate.get("image_order"),
            )

    def _catalog_task(
        self, snapshot_id: int, source_task_id: str, profile_id: int | None = None
    ) -> dict[str, Any]:
        task = self.store.get_catalog_task(snapshot_id, source_task_id)
        if task is None:
            raise APIError("找不到所选任务资料。", 404)
        if profile_id is None:
            with self.lock:
                profile_id = self.selected_profile_id
        profile = next((item for item in self.profiles() if item.id == profile_id), None)
        if profile is None or profile.game_mode != task["game_mode"]:
            raise APIError("任务资料与目标档案模式不一致。", 409)
        return task

    def load_catalog_task_details(
        self,
        snapshot_id: int,
        source_task_id: str,
        profile_id: int | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        task = self._catalog_task(snapshot_id, source_task_id, profile_id)
        if task.get("details_loaded") and not force_refresh:
            return {**task, "map_points": supplement_verified_point_images(
                source_task_id, task.get("map_points", []), task["game_mode"],
            )}
        try:
            details = fetch_tarkov_dev_task_detail(source_task_id, task["game_mode"])
        except CatalogError as error:
            raise APIError(str(error), 502) from error
        self.store.update_catalog_task_details(
            snapshot_id,
            source_task_id,
            details["objectives"],
            details.get("prerequisites", []),
            details.get("key_requirements", []),
            details.get("map_points", []),
        )
        updated = self.store.get_catalog_task(snapshot_id, source_task_id)
        if updated is None:
            raise APIError("任务资料读取后已不可用。", 404)
        return {**updated, "map_points": supplement_verified_point_images(
            source_task_id, updated.get("map_points", []), updated["game_mode"],
        )}

    def import_catalog_task(
        self, snapshot_id: int, source_task_id: str, profile_id: int | None = None
    ) -> Task:
        if profile_id is None:
            with self.lock:
                profile_id = self.selected_profile_id
        task = self.load_catalog_task_details(snapshot_id, source_task_id, profile_id)
        objective_lines = [item.get("text", "").strip() for item in task["objectives"] if item.get("text", "").strip()]
        if not objective_lines:
            raise APIError("任务目标为空，未加入任务清单。", 422)
        objective_requirements = [
            {
                "text": str(item.get("text", "")).strip(),
                "completed": False,
                "optional": bool(item.get("optional", False)),
                "target_count": item.get("target_count"),
                "current_count": 0,
            }
            for item in task["objectives"]
            if str(item.get("text", "")).strip()
        ]
        required_objective_count = sum(
            not item["optional"] for item in objective_requirements
        )
        key_lines = []
        required_items = filter_assault_weapon_items(
            task.get("objectives", []), task.get("key_requirements", [])
        )
        for required_item in required_items:
            name = str(required_item.get("name", "")).strip()
            is_key = is_key_item_name(name)
            if not name:
                name = "未知钥匙" if is_key else "未知物品"
            methods = required_item.get("acquisition_methods", [])
            method_entries = [
                " · ".join(
                    part
                    for part in (
                        str(method.get("trader", "")).strip(),
                        str(method.get("loyalty_level", "")).strip(),
                        str(method.get("requirements", "")).strip(),
                    )
                    if part
                )
                for method in methods
            ]
            method_text = "; ".join(entry for entry in method_entries if entry)
            key_lines.append(f"{'需要钥匙' if is_key else '需要物品'}：{name}")
            if method_text:
                key_lines.append(f"{'钥匙获取' if is_key else '获取方式'}：{method_text}")
        objective = "\n".join(objective_lines + key_lines)
        profile = next((item for item in self.profiles() if item.id == profile_id), None)
        if profile is None or profile.game_mode != task["game_mode"]:
            raise APIError("任务资料与目标档案模式不一致，任务未加入。", 409)
        imported = self.store.add_task(
            task["trader"],
            task["title"],
            objective,
            required_count=required_objective_count,
            profile_id=profile_id,
            source_task_id=task["source_task_id"],
            source_url=task["source_url"],
            source_version=task["source_version"],
            requirements=objective_requirements,
        )
        self.store.delete_pending_task_candidate(profile_id, task["source_task_id"])
        log_event(
            "task_imported_from_catalog",
            profile_id=profile_id,
            task_id=imported.id,
            source_task_id=task["source_task_id"],
            source_version=task["source_version"],
            title=task["title"],
        )
        with self.lock:
            for capture in self.capture_records.values():
                if capture["profile_id"] != profile_id:
                    continue
                updated = False
                for candidate in capture["task_candidates"]:
                    if candidate.get("source_task_id") == task["source_task_id"]:
                        candidate["notification_status"] = "added"
                        candidate["notification_message"] = "已加入任务清单"
                        updated = True
                if updated:
                    self._persist_capture_locked(capture)
        return imported

    def update_pending_candidate_details(
        self, profile_id: int, source_task_id: str, task: dict[str, Any]
    ) -> None:
        objectives = task.get("objectives", [])
        self.store.update_pending_task_candidate(
            profile_id,
            source_task_id,
            {
                "objectives": objectives,
                "key_requirements": task.get("key_requirements", []),
                "map_points": task.get("map_points", []),
                "details_status": "ready" if objectives else "empty",
                "details_error": "",
            },
        )

    def _pending_capture_count_locked(self) -> int:
        return sum(
            capture["state"] in CAPTURE_ACTIVE_STATES
            for capture in self.capture_records.values()
        )

    def _prune_capture_records_locked(self) -> None:
        while len(self.capture_records) > CAPTURE_HISTORY_LIMIT:
            removable = next(
                (
                    capture_id
                    for capture_id, capture in self.capture_records.items()
                    if capture["state"] not in CAPTURE_ACTIVE_STATES
                    and capture_id != self.selected_capture_id
                ),
                None,
            )
            if removable is None:
                break
            del self.capture_records[removable]
            self.store.delete_capture_record(removable)

    def receive_screenshot(
        self,
        jpeg: bytes,
        source: str = "screenshot_folder",
    ) -> dict[str, Any]:
        if not CAPTURE_DECODE_SLOTS.acquire(blocking=False):
            raise APIError("截图处理中，请稍后再试。", 429)
        try:
            dimensions = _jpeg_dimensions(jpeg)
            if dimensions is None:
                raise APIError("截图文件无法解码。", 422)
            image_width, image_height = dimensions
            if image_width * image_height > MAX_CAPTURE_PIXELS:
                raise APIError("截图分辨率超过 2000 万像素限制。", 413)
            image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise APIError("截图文件无法解码。", 422)
            image_height, image_width = image.shape[:2]
            if image_width < 320 or image_height < 200:
                raise APIError("截图分辨率过低，无法识别游戏界面。", 422)
            encoded_ok, encoded_image = cv2.imencode(
                ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88]
            )
            if not encoded_ok:
                raise APIError("无法编码导入的截图。", 422)
        finally:
            CAPTURE_DECODE_SLOTS.release()

        with self.capture_lock:
            with self.lock:
                if self._closed:
                    raise APIError("服务正在关闭。", 503)
                if self._pending_capture_count_locked() >= CAPTURE_PENDING_LIMIT:
                    return {
                        "accepted": False,
                        "message": f"截图队列已满（最多 {CAPTURE_PENDING_LIMIT} 张），请稍等片刻。",
                    }
                capture_id = uuid.uuid4().hex[:12]
                profile_id = self.selected_profile_id
                record = {
                    "id": capture_id,
                    "profile_id": profile_id,
                    "source": source,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    "state": "queued",
                    "error": "",
                    "jpeg": encoded_image.tobytes(),
                    "resolution": {"width": image_width, "height": image_height},
                    "analysis": None,
                    "task_candidates": [],
                }
                self.capture_records[capture_id] = record
                self.latest_capture_id = capture_id
                self.selected_capture_id = capture_id
                self.store.set_app_setting(f"selected_capture_id:{profile_id}", capture_id)
                self._persist_capture_locked(record)
                self._prune_capture_records_locked()
                self.executor.submit(self._capture_and_analyze, capture_id, profile_id, image)
        log_event(
            "screenshot_imported",
            capture_id=capture_id,
            source=source,
            source_resolution={"width": image_width, "height": image_height},
            profile_id=profile_id,
            screenshot_storage="local_sqlite_cache",
            queued=True,
        )
        return {"accepted": True, "capture_id": capture_id, "message": "截图已加入识别队列。"}

    def _capture_and_analyze(self, capture_id: str, profile_id: int, image: np.ndarray) -> None:
        with self.lock:
            record = self.capture_records.get(capture_id)
            if record is None:
                return
            record["state"] = "processing"
            self._persist_capture_locked(record)
        try:
            analysis = self.analyzer.analyze(image, capture_id=capture_id)
            task_candidates: list[dict[str, Any]] = []
            new_task_candidates: list[dict[str, Any]] = []
            if analysis.kind == ScreenKind.TRADER_TASKS and analysis.task_page_confident and analysis.trader:
                task_candidates = self.screenshot_task_candidates(analysis, profile_id, capture_id)
                if (capture_id, profile_id) in getattr(self, "catalog_pending_captures", set()):
                    diagnostics = {**analysis.diagnostics, "catalog_match_pending": True}
                    warning = analysis.warning
                    if CATALOG_MATCH_PENDING_WARNING not in warning:
                        warning = f"{warning} {CATALOG_MATCH_PENDING_WARNING}".strip()
                    analysis = replace(analysis, diagnostics=diagnostics, warning=warning)
                new_task_candidates = [
                    candidate for candidate in task_candidates
                    if not candidate.get("already_tracked")
                ]
                already_tracked_candidates = [
                    candidate for candidate in task_candidates
                    if candidate.get("already_tracked")
                ]
                for candidate in task_candidates:
                    candidate["objectives"] = []
                    candidate["key_requirements"] = []
                    candidate["map_points"] = []
                    candidate["details_error"] = ""
                    if candidate.get("already_tracked"):
                        candidate["details_status"] = "skipped"
                        candidate["notification_status"] = "already_tracked"
                        candidate["notification_message"] = "已在任务清单中；本次确认识别，不重复添加。"
                    else:
                        candidate["details_status"] = "loading"
                        candidate["notification_status"] = "processing"
                        candidate["notification_message"] = "正在查询任务详情…"
                notices: list[str] = []
                if new_task_candidates:
                    notices.append(
                        f"识别到 {len(new_task_candidates)} 个新任务，逐项处理结果见下方截图通知。"
                    )
                if already_tracked_candidates:
                    notices.append(
                        f"另外识别到 {len(already_tracked_candidates)} 个已在清单的任务，不会重复添加。"
                    )
                if notices:
                    analysis = replace(analysis, warning=f"{analysis.warning} {' '.join(notices)}".strip())
            with self.lock:
                record = self.capture_records.get(capture_id)
                if record is None:
                    return
                record["analysis"] = analysis
                record["task_candidates"] = task_candidates
                record["state"] = "done"
                self.store.save_pending_task_candidates(new_task_candidates)
                self._persist_capture_locked(record)
                self._prune_capture_records_locked()
            new_task_candidates = [
                candidate for candidate in task_candidates
                if not candidate.get("already_tracked")
            ]
            if new_task_candidates:
                log_event(
                    "screenshot_candidate_details_started",
                    capture_id=capture_id,
                    profile_id=profile_id,
                    source_task_ids=[candidate["source_task_id"] for candidate in new_task_candidates],
                )
                try:
                    self.catalog_executor.submit(
                        self._load_screenshot_candidate_details, capture_id, profile_id
                    )
                except RuntimeError as error:
                    with self.lock:
                        record = self.capture_records.get(capture_id)
                        if record is not None:
                            record["task_candidates"] = [
                                {
                                    **candidate,
                                    "details_status": "error",
                                    "details_error": "后台详情查询未能启动。",
                                    "notification_status": "failed",
                                    "notification_message": "任务详情查询未能启动。",
                                }
                                for candidate in record["task_candidates"]
                            ]
                            self._persist_capture_locked(record)
                    for candidate in new_task_candidates:
                        self.store.delete_pending_task_candidate(
                            profile_id, candidate["source_task_id"]
                        )
                    log_event(
                        "screenshot_candidate_details_failed",
                        level=logging.ERROR,
                        capture_id=capture_id,
                        profile_id=profile_id,
                        error=repr(error),
                    )
            log_event(
                "analysis_applied",
                capture_id=capture_id,
                profile_id=profile_id,
                page_kind=analysis.kind.value,
                trader=analysis.trader,
                task_page_confident=analysis.task_page_confident,
                screenshot_task_candidates=[
                    {
                        "source_task_id": candidate["source_task_id"],
                        "recognized_text": candidate["recognized_text"],
                        "title": candidate["title"],
                        "image_order": candidate.get("image_order"),
                        "match_score": candidate["match_score"],
                        "ocr_confidence": candidate["ocr_confidence"],
                        "already_tracked": bool(candidate.get("already_tracked")),
                    }
                    for candidate in task_candidates
                ],
                warning=analysis.warning,
            )
        except Exception as error:
            log_event(
                "capture_failed",
                level=logging.ERROR,
                capture_id=capture_id,
                profile_id=profile_id,
                error=repr(error),
                traceback=traceback.format_exc(),
            )
            with self.lock:
                record = self.capture_records.get(capture_id)
                if record is not None:
                    record["state"] = "failed"
                    record["error"] = str(error)
                    self._persist_capture_locked(record)
                    self._prune_capture_records_locked()

    def screenshot(self, capture_id: str | None = None) -> tuple[str, bytes] | None:
        with self.lock:
            selected_id = capture_id or self.selected_capture_id or self.latest_capture_id
            capture = self.capture_records.get(selected_id or "")
            if capture is None or capture["jpeg"] is None:
                return None
            return selected_id, capture["jpeg"]

    def add_task(self, payload: dict[str, Any]) -> Task:
        title = str(payload.get("title", "")).strip()
        if not title:
            raise APIError("任务名称不能为空。")
        required = payload.get("required_count")
        if required in (None, "", 0, "0"):
            required = None
        else:
            try:
                required = int(required)
            except (TypeError, ValueError) as error:
                raise APIError("所需数量必须是整数。") from error
            if required < 0:
                raise APIError("所需数量不能为负数。")
        with self.lock:
            profile_id = self.selected_profile_id
        task = self.store.add_task(
            str(payload.get("trader", "")),
            title,
            str(payload.get("objective", "")),
            str(payload.get("item_name", "")),
            required,
            profile_id,
        )
        log_event("task_created_or_updated", profile_id=profile_id, task_id=task.id, title=task.title)
        return task

    def set_task_requirement(self, task_id: int, requirement_index: int, completed: bool) -> Task:
        if not isinstance(completed, bool):
            raise APIError("目标进度必须是布尔值。")
        with self.lock:
            profile_id = self.selected_profile_id
        try:
            task = self.store.set_requirement(task_id, profile_id, requirement_index, completed)
        except ValueError as error:
            raise APIError(str(error)) from error
        log_event(
            "task_requirement_progress_changed",
            task_id=task.id,
            profile_id=task.profile_id,
            requirement_index=requirement_index,
            completed=completed,
            count=task.current_count,
        )
        return task

    def set_task_requirement_count(
        self, task_id: int, requirement_index: int, current_count: Any
    ) -> Task:
        with self.lock:
            profile_id = self.selected_profile_id
        try:
            task = self.store.set_requirement_count(
                task_id, profile_id, requirement_index, current_count
            )
        except ValueError as error:
            raise APIError(str(error)) from error
        log_event(
            "task_requirement_count_changed",
            task_id=task.id,
            profile_id=task.profile_id,
            requirement_index=requirement_index,
            count=current_count,
            task_progress=task.current_count,
        )
        return task

    def increment_task(self, task_id: int) -> Task:
        with self.lock:
            profile_id = self.selected_profile_id
        task = self.store.increment(task_id, profile_id)
        log_event("task_progress_incremented", task_id=task.id, profile_id=task.profile_id, count=task.current_count)
        return task

    def complete_task(self, task_id: int) -> Task:
        with self.lock:
            profile_id = self.selected_profile_id
        task = self.store.mark_complete(task_id, profile_id)
        log_event("task_marked_complete", task_id=task.id, profile_id=task.profile_id)
        return task

    def delete_task(self, task_id: int) -> Task:
        with self.lock:
            profile_id = self.selected_profile_id
        try:
            task = self.store.delete_task(task_id, profile_id)
        except ValueError as error:
            raise APIError(str(error), 404) from error
        log_event("task_deleted", task_id=task.id, profile_id=profile_id, title=task.title)
        return task

    def restore_tasks(self, snapshots: Any) -> list[Task]:
        if not isinstance(snapshots, list):
            raise APIError("撤回记录无效。")
        with self.lock:
            profile_id = self.selected_profile_id
        try:
            tasks = self.store.restore_task_snapshots(snapshots, profile_id)
        except ValueError as error:
            raise APIError(str(error)) from error
        log_event(
            "tasks_restored",
            profile_id=profile_id,
            task_ids=[task.id for task in tasks],
        )
        return tasks

    def clear_tasks(self) -> int:
        with self.lock:
            profile_id = self.selected_profile_id
        deleted_count = self.store.clear_tasks(profile_id)
        log_event("tasks_cleared", profile_id=profile_id, deleted_count=deleted_count)
        return deleted_count

    def map_index(self) -> list[dict[str, str]]:
        with self.lock:
            profile_id = self.selected_profile_id
        profile = next((item for item in self.profiles() if item.id == profile_id), None)
        if profile is None:
            raise APIError("找不到当前游戏档案", 404)
        try:
            return fetch_tarkov_dev_map_index(profile.game_mode)
        except CatalogError as error:
            raise APIError(str(error), 502) from error

    def _map_catalog_tasks(
        self, game_mode: str, tasks: list[Task]
    ) -> tuple[dict[int, dict[str, Any]], list[str]]:
        snapshot = self.store.latest_catalog_snapshot(game_mode)
        if snapshot is None:
            return {}, []
        snapshot_id = int(snapshot["id"])
        catalog_tasks: dict[int, dict[str, Any]] = {}
        warnings: list[str] = []
        for task in tasks:
            if not task.source_task_id:
                continue
            cached = self.store.get_catalog_task(snapshot_id, task.source_task_id)
            if cached is None:
                continue
            cached_points = cached.get("map_points", [])
            has_legacy_map_points = any(
                isinstance(point, dict) and point.get("source_provider") != "tarkov.dev"
                for point in cached_points
            )
            needs_map_refresh = not cached["details_loaded"] or has_legacy_map_points
            if needs_map_refresh:
                failure_key = (snapshot_id, task.source_task_id)
                with self.lock:
                    retry_after = self.map_detail_retry_after.get(failure_key, 0)
                if retry_after > time.monotonic():
                    warnings.append(task.title)
                else:
                    try:
                        cached = self.load_catalog_task_details(
                            snapshot_id,
                            task.source_task_id,
                            force_refresh=has_legacy_map_points,
                        )
                        with self.lock:
                            self.map_detail_retry_after.pop(failure_key, None)
                    except Exception as error:
                        with self.lock:
                            self.map_detail_retry_after[failure_key] = time.monotonic() + 60
                        warnings.append(task.title)
                        log_event(
                            "map_task_details_failed",
                            level=logging.WARNING,
                            task_id=task.id,
                            source_task_id=task.source_task_id,
                            title=task.title,
                            error=str(error),
                        )
                        continue
            # Supplement existing cached details at read time; no resync, task
            # progress writes or replacement of the Tarkov.dev coordinates.
            catalog_tasks[task.id] = {**cached, "map_points": supplement_verified_point_images(
                task.source_task_id, cached.get("map_points", []), game_mode,
            )}
        return catalog_tasks, warnings

    def map_overview(self) -> dict[str, Any]:
        with self.lock:
            profile_id = self.selected_profile_id
        profile = next((item for item in self.profiles() if item.id == profile_id), None)
        if profile is None:
            raise APIError("找不到当前游戏档案", 404)
        try:
            maps = fetch_tarkov_dev_map_index(profile.game_mode)
        except CatalogError as error:
            raise APIError(str(error), 502) from error
        tasks = [task for task in self.store.list_tasks(profile_id) if task.state != "complete"]
        catalog_tasks, warnings = self._map_catalog_tasks(profile.game_mode, tasks)
        map_counts = {
            entry["map_id"]: {"task_ids": set(), "point_count": 0}
            for entry in maps
        }
        map_aliases = {
            "653e6760052c01c1c805532f": ("中心区", "Ground Zero", "GroundZero"),
            "55f2d3fd4bdc2d5f408b4567": ("工厂", "Factory"),
            "56f40101d2720b2a4d8b45d6": ("海关", "Customs"),
            "5704e3c2d2720bac5b8b4567": ("森林", "伐木场码头", "Woods"),
            "5704e4dad2720bb55b8b4567": ("灯塔", "Lighthouse"),
            "5704e554d2720bac5b8b456e": ("海岸线", "Shoreline"),
            "5714dbc024597771384a510d": ("立交桥", "Interchange"),
            "5704e5fad2720bc05b8b4567": ("储备站", "Reserve"),
            "5714dc692459777137212e12": ("塔科夫街区", "Streets of Tarkov"),
            "5b0fc42d86f7744a585f9105": ("实验室", "The Lab", "Labs"),
            "69af492a4819ea4ba10a69c5": ("破冰船", "Icebreaker"),
            "6733700029c367a3d40b02af": ("迷宫", "Labyrinth"),
            "65cc8f81a9aac3e77d0cfd3e": ("码头地图", "港口地图", "港口", "Port"),
        }
        map_alias_exclusions = {
            "5b0fc42d86f7744a585f9105": (
                "实验室日志",
                "实验室的日志",
                "实验室记录",
                "化学品实验室",
                "the lab log",
                "lab log",
                "labs log",
                "laboratory log",
            ),
        }
        ambiguous_map_terms = {
            "65cc8f81a9aac3e77d0cfd3e": {"码头"},
        }
        for task in tasks:
            cached = catalog_tasks.get(task.id)
            points = [
                point for point in cached.get("map_points", [])
                if isinstance(point, dict) and point.get("source_provider") == "tarkov.dev"
            ] if cached else []
            for point in points:
                map_id = str(point.get("map_id", "")).lower()
                if map_id not in map_counts:
                    continue
                map_counts[map_id]["task_ids"].add(task.id)
                map_counts[map_id]["point_count"] += 1
            objective_lines = [
                line
                for line in task.objective.splitlines()
                if not re.match(
                    r"\s*(?:钥匙获取|获取方式|需要钥匙|需要物品|钥匙|物品)\s*[：:]",
                    line,
                    re.IGNORECASE,
                )
            ]
            objective_text = "\n".join(
                objective_lines
                + [str(item.get("text", "")) for item in task.requirements]
                + [
                    str(item.get("text", ""))
                    for item in (cached.get("objectives", []) if cached else [])
                    if isinstance(item, dict)
                ]
            ).casefold()
            for map_entry in maps:
                map_id = map_entry["map_id"]
                map_match_text = objective_text
                for excluded_phrase in map_alias_exclusions.get(map_id, ()):
                    map_match_text = map_match_text.replace(excluded_phrase.casefold(), "")
                terms = tuple(map_aliases.get(map_id, ())) + (str(map_entry.get("name", "")),)
                for term in terms:
                    if not term:
                        continue
                    if normalize_text(term) in ambiguous_map_terms.get(map_id, set()):
                        continue
                    if any("\u4e00" <= character <= "\u9fff" for character in term):
                        matches = term.casefold() in map_match_text
                    else:
                        matches = re.search(
                            rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])",
                            map_match_text,
                            re.IGNORECASE,
                        ) is not None
                    if matches:
                        map_counts[map_id]["task_ids"].add(task.id)
                        break
        for entry in maps:
            counts = map_counts[entry["map_id"]]
            entry["active_task_count"] = len(counts["task_ids"])
            entry["active_point_count"] = counts["point_count"]
            entry["task_ids"] = sorted(counts["task_ids"])
        maps_with_points = [entry for entry in maps if entry["active_point_count"]]
        preferred_map_id = max(
            maps_with_points,
            key=lambda entry: entry["active_point_count"],
            default=maps[0] if maps else None,
        )
        return {
            "maps": maps,
            "preferred_map_id": preferred_map_id["map_id"] if preferred_map_id else "",
            "detail_warnings": warnings,
        }

    def hideout_catalog(self, force_refresh: bool = False) -> dict[str, Any]:
        try:
            return get_hideout_catalog(force_refresh)
        except RuntimeError as error:
            raise APIError(str(error), 502) from error

    def map_view(self, map_id: str, floor_key: str = "") -> dict[str, Any]:
        with self.lock:
            profile_id = self.selected_profile_id
        profile = next((item for item in self.profiles() if item.id == profile_id), None)
        if profile is None:
            raise APIError("找不到当前游戏档案", 404)
        try:
            config = fetch_tarkov_dev_map_data(map_id, profile.game_mode)
        except CatalogError as error:
            raise APIError(str(error), 502) from error
        tasks = [task for task in self.store.list_tasks(profile_id) if task.state != "complete"]
        catalog_tasks, detail_warnings = self._map_catalog_tasks(profile.game_mode, tasks)
        floor_keys = {item["key"] for item in config["floors"]}
        visited_marker_ids = self.store.list_map_marker_visits(profile_id, map_id)
        task_points: list[tuple[Task, dict[str, Any]]] = []
        for task in tasks:
            cached = catalog_tasks.get(task.id)
            if cached is None:
                continue
            for point in cached.get("map_points", []):
                if not isinstance(point, dict) or point.get("source_provider") != "tarkov.dev":
                    continue
                if str(point.get("map_id", "")).lower() == map_id:
                    task_points.append((task, point))

        point_counts: dict[str, int] = {}
        for _, point in task_points:
            point_floor = str(point.get("floor_key", ""))
            if point_floor in floor_keys:
                point_counts[point_floor] = point_counts.get(point_floor, 0) + 1
        floors = [
            {**item, "active_point_count": point_counts.get(item["key"], 0)}
            for item in config["floors"]
        ]
        floor = next((item for item in config["floors"] if item["key"] == str(floor_key)), None)
        if floor is None:
            floor = next((item for item in config["floors"] if item.get("is_default")), None)
        if floor is None and config["floors"]:
            floor = config["floors"][0]
        if floor is None:
            raise APIError("该地图没有可显示的楼层底图。", 502)

        markers = []
        for task, point in task_points:
            point_floor = next(
                (item for item in config["floors"] if item["key"] == str(point.get("floor_key", ""))),
                None,
            )
            if point_floor is None:
                continue
            try:
                x_percent = float(point["x_percent"])
                y_percent = float(point["y_percent"])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(x_percent) or not math.isfinite(y_percent):
                continue
            point_id = str(point.get("id", ""))
            api_marker_id = point_id
            markers.append(
                {
                    "id": api_marker_id,
                    "x_percent": x_percent,
                    "y_percent": y_percent,
                    "title": point.get("title") or task.title,
                    "title_en": point.get("title_en") or point.get("title") or task.title,
                    "floor_key": point_floor["key"],
                    "floor_name": point_floor["name"],
                    "floor_name_en": point.get("floor_name_en") or point_floor.get("name_en", point_floor["name"]),
                    "description": point.get("description", ""),
                    "task_id": task.id,
                    "task_title": task.title,
                    "point_kind": "objective",
                    "source_url": point.get("source_url", config["source_url"]),
                    "source_image_urls": point.get("source_image_urls", []),
                    "source_image_page_url": point.get("source_image_page_url", ""),
                    "source_image_provider": point.get("source_image_provider", ""),
                    "source_image_marker_id": point.get("source_image_marker_id", ""),
                    "source_image_reviewed_at": point.get("source_image_reviewed_at", ""),
                    "source_page_url": point.get("source_page_url", config["source_url"]),
                    "visited": api_marker_id in visited_marker_ids,
                }
            )

        return {
            "map_id": config["map_id"],
            "map_name": config["name"],
            "map_name_en": config["name_en"],
            "map_author": config["map_author"],
            "map_author_url": config["map_author_url"],
            "map_license": config["map_license"],
            "map_license_url": config["map_license_url"],
            "floor": floor,
            "floors": floors,
            "image_url": f"/api/map/image?{urlencode({'map_id': config['map_id'], 'floor': floor['key']})}",
            "markers": markers,
            "annotations": config["annotations"],
            "unplaced_annotation_count": config.get("unplaced_annotation_count", 0),
            "detail_warnings": detail_warnings,
            "tasks": [
                {"id": task.id, "title": task.title, "trader": task.trader}
                for task in tasks
            ],
            "source_url": config["source_url"],
        }

    def map_floor_image(self, map_id: str, floor_key: str) -> bytes:
        with self.lock:
            profile_id = self.selected_profile_id
        profile = next((item for item in self.profiles() if item.id == profile_id), None)
        if profile is None:
            raise APIError("找不到当前游戏档案", 404)
        try:
            return fetch_tarkov_dev_map_floor_image(map_id, floor_key, profile.game_mode)
        except CatalogError as error:
            log_event(
                "map_floor_image_failed",
                level=logging.WARNING,
                map_id=map_id,
                floor_key=floor_key,
                game_mode=profile.game_mode,
                error=str(error),
            )
            raise APIError(f"无法读取地图底图：{error}", 502) from error

    def set_map_marker_visited(self, payload: dict[str, Any]) -> dict[str, Any]:
        map_id = str(payload.get("map_id", "")).strip().lower()
        marker_id = str(payload.get("marker_id", "")).strip()
        visited = payload.get("visited")
        hex_chars = set("0123456789abcdef")
        marker_suffix = marker_id.removeprefix("eftarkov-")
        is_eft_marker = (
            marker_id.startswith("eftarkov-")
            and len(marker_suffix) == 24
            and set(marker_suffix.lower()) <= hex_chars
        )
        tarkov_dev_suffix = marker_id.removeprefix("tarkovdev-")
        is_tarkov_dev_marker = (
            marker_id.startswith("tarkovdev-")
            and len(tarkov_dev_suffix) == 24
            and set(tarkov_dev_suffix.lower()) <= hex_chars
        )
        if len(map_id) != 24 or not set(map_id) <= hex_chars:
            raise APIError("地图 ID 格式无效。")
        if not (is_eft_marker or is_tarkov_dev_marker):
            raise APIError("地图点位 ID 格式无效。")
        if not isinstance(visited, bool):
            raise APIError("到访状态必须是布尔值。")
        with self.lock:
            profile_id = self.selected_profile_id
        self.store.set_map_marker_visited(profile_id, map_id, marker_id, visited)
        log_event(
            "map_marker_visit_changed",
            profile_id=profile_id,
            map_id=map_id,
            marker_id=marker_id,
            visited=visited,
        )
        return {"map_id": map_id, "marker_id": marker_id, "visited": visited}

    def close(self) -> None:
        with self.lock:
            self._closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.catalog_executor.shutdown(wait=False, cancel_futures=True)
        log_event("application_stopped")


class PlayerStateManager:
    def __init__(self, data_root: Path | None = None) -> None:
        self.auth = PlayerAuthStore(data_root)
        self.local_player = self.auth.local_player()
        self._states: dict[str, AssistantState] = {}
        self._lock = threading.RLock()

    def state_for(self, player: Player) -> AssistantState:
        with self._lock:
            assistant = self._states.get(player.id)
            if assistant is None:
                database_path = self.auth.database_path(player)
                database_existed = database_path.exists()
                store = TaskStore(database_path)
                profile_name_setup = store.get_app_setting("profile_name_setup_complete")
                if profile_name_setup is None:
                    profiles = store.list_profiles()
                    is_unnamed_default_profile = (
                        len(profiles) == 1
                        and profiles[0].name == "PvE 默认档"
                        and not store.list_tasks(profiles[0].id)
                    )
                    require_profile_name = not database_existed or is_unnamed_default_profile
                    store.set_app_setting(
                        "profile_name_setup_complete",
                        "0" if require_profile_name else "1",
                    )
                else:
                    require_profile_name = profile_name_setup != "1"
                shared_catalog_path = default_database_path()
                recover_empty_capture_candidates = False
                if store.path.resolve() != shared_catalog_path.resolve():
                    had_catalog = any(
                        store.latest_catalog_snapshot(game_mode) for game_mode in GAME_MODES
                    )
                    had_tracked_tasks = any(
                        store.list_tasks(profile.id) for profile in store.list_profiles()
                    )
                    imported_snapshots = store.sync_catalog_from(shared_catalog_path)
                    recover_empty_capture_candidates = (
                        bool(imported_snapshots) and not had_catalog and not had_tracked_tasks
                    )
                    if imported_snapshots:
                        log_event(
                            "player_public_catalog_synced",
                            player_id=player.id,
                            snapshots=imported_snapshots,
                        )
                assistant = AssistantState(
                    store=store,
                    player=player,
                    recover_empty_capture_candidates=recover_empty_capture_candidates,
                    require_profile_name=require_profile_name,
                )
                self._states[player.id] = assistant
            return assistant

    def close(self) -> None:
        with self._lock:
            assistants = list(self._states.values())
            self._states.clear()
        for assistant in assistants:
            assistant.close()


def _make_handler(
    state: PlayerStateManager,
    mobile_access_info: dict[str, Any] | None = None,
    mobile_only: bool = False,
) -> type[BaseHTTPRequestHandler]:
    mobile_network = mobile_access_info if mobile_access_info is not None else {}
    mobile_get_paths = {
        "/api/mobile/state",
        "/api/maps",
        "/api/map",
        "/api/map/image",
    }
    mobile_static_paths = {
        "/mobile",
        "/assets/mobile.js",
        "/assets/mobile.css",
        "/favicon.ico",
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = "EFTTaskAssistant/0.1"

        def log_message(self, format_string: str, *args: Any) -> None:
            path = urlparse(self.path).path
            if path in {
                "/api/state",
                "/api/screenshot",
                "/api/logs",
                "/favicon.ico",
            }:
                return
            log_event("http_request", client=self.client_address[0], message=format_string % args)

        def _send(
            self,
            status: int,
            body: bytes,
            content_type: str,
            extra_headers: tuple[tuple[str, str], ...] = (),
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for name, value in extra_headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_json(
            self,
            status: int,
            data: dict[str, Any],
            extra_headers: tuple[tuple[str, str], ...] = (),
        ) -> None:
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8", extra_headers)

        def _session_token(self) -> str | None:
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except CookieError:
                return None
            session = cookie.get("eft_player_session")
            return session.value if session else None

        def _is_loopback_client(self) -> bool:
            try:
                address = ipaddress.ip_address(self.client_address[0].split("%", 1)[0])
            except ValueError:
                return False
            return address.is_loopback or bool(address.ipv4_mapped and address.ipv4_mapped.is_loopback)

        def _require_player(self) -> Player:
            token = self._session_token()
            scope = state.auth.session_scope(token)
            player = state.auth.authenticate(token)
            if mobile_only:
                if player is None or scope != "mobile":
                    raise APIError("请从本机扫描二维码连接手机地图。", 401)
                if not self._mobile_api_allowed():
                    raise APIError("手机端仅可读取地图和任务信息。", 403)
                return player
            if self._is_loopback_client():
                if player is not None and scope == "mobile":
                    if not self._mobile_api_allowed():
                        raise APIError("手机端仅可读取地图和任务信息。", 403)
                    return player
                return state.local_player
            if player is None or scope != "mobile":
                raise APIError("局域网入口仅提供已配对手机的只读地图。", 403)
            if scope == "mobile" and not self._mobile_api_allowed():
                raise APIError("手机端仅可读取地图和任务信息。", 403)
            return player

        def _mobile_api_allowed(self) -> bool:
            return self.command == "GET" and urlparse(self.path).path in mobile_get_paths

        def _session_cookie(self, token: str, max_age: int) -> tuple[str, str]:
            cookie = SimpleCookie()
            cookie_name = "eft_player_session"
            cookie[cookie_name] = token
            cookie[cookie_name]["path"] = "/"
            cookie[cookie_name]["httponly"] = True
            cookie[cookie_name]["samesite"] = "Strict"
            cookie[cookie_name]["max-age"] = str(max_age)
            return "Set-Cookie", cookie[cookie_name].OutputString()

        def _enforce_same_origin(self) -> None:
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if origin and host and urlparse(origin).netloc.casefold() != host.casefold():
                raise APIError("跨站请求已拒绝。", 403)

        def _read_json(self) -> dict[str, Any]:
            length_text = self.headers.get("Content-Length", "0")
            try:
                length = int(length_text)
            except ValueError as error:
                raise APIError("请求长度无效。") from error
            if length <= 0 or length > 1_000_000:
                raise APIError("请求内容为空或超过限制。")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise APIError("请求 JSON 格式无效。") from error
            if not isinstance(payload, dict):
                raise APIError("请求内容必须是 JSON 对象。")
            return payload

        def _read_capture_jpeg(self) -> bytes:
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "image/jpeg":
                raise APIError("导入的截图必须使用 JPEG 格式。", 415)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise APIError("截图长度无效。") from error
            if length <= 0 or length > MAX_CAPTURE_BYTES:
                raise APIError("截图为空或超过 16 MB。", 413)
            image_bytes = self.rfile.read(length)
            if len(image_bytes) != length:
                raise APIError("截图上传不完整。", 400)
            return image_bytes

        def _dispatch_error(self, error: Exception) -> None:
            if isinstance(error, APIError):
                status = error.status
                message = str(error)
            elif isinstance(error, ValueError):
                status = 404 if "找不到" in str(error) else 400
                message = str(error)
            else:
                status = 500
                message = "本地处理失败，请查看诊断日志。"
                log_event(
                    "http_handler_failed",
                    level=logging.ERROR,
                    path=self.path,
                    error=repr(error),
                    traceback=traceback.format_exc(),
                )
            self._send_json(status, {"error": message})

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            try:
                if mobile_only and path == "/":
                    self.send_response(302)
                    self.send_header("Location", "/mobile")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
                if mobile_only and path not in mobile_static_paths | mobile_get_paths:
                    raise APIError("局域网入口仅提供手机地图页面和只读接口。", 403)
                if path == "/":
                    self._send_static("index.html")
                elif path == "/mobile":
                    self._send_static("mobile.html")
                elif path == "/assets/app.js":
                    self._send_static("app.js")
                elif path == "/assets/styles.css":
                    self._send_static("styles.css")
                elif path == "/assets/mobile.js":
                    self._send_static("mobile.js")
                elif path == "/assets/mobile.css":
                    self._send_static("mobile.css")
                elif path == "/favicon.ico":
                    self.send_response(204)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                else:
                    player = self._require_player()
                    assistant = state.state_for(player)
                    if path == "/api/mobile/info":
                        self._send_json(200, mobile_network)
                    elif path == "/api/mobile/state":
                        snapshot = assistant.snapshot()
                        selected_profile = next(
                            (
                                profile
                                for profile in snapshot["profiles"]
                                if profile["id"] == snapshot["selected_profile_id"]
                            ),
                            None,
                        )
                        self._send_json(
                            200,
                            {
                                "profiles": [selected_profile] if selected_profile else [],
                                "selected_profile_id": snapshot["selected_profile_id"],
                                "tasks": snapshot["tasks"],
                            },
                        )
                    elif path == "/api/state":
                        self._send_json(200, assistant.snapshot())
                    elif path == "/api/screenshot":
                        query = parse_qs(urlparse(self.path).query)
                        requested_id = query.get("capture", [None])[0]
                        screenshot = assistant.screenshot(requested_id)
                        if screenshot is None:
                            self._send_json(404, {"error": "当前没有可显示的截图。"})
                        else:
                            self.send_response(200)
                            self.send_header("Content-Type", "image/jpeg")
                            self.send_header("Content-Length", str(len(screenshot[1])))
                            self.send_header("Cache-Control", "no-store")
                            self.send_header("X-Capture-Id", screenshot[0])
                            self.end_headers()
                            self.wfile.write(screenshot[1])
                    elif path == "/api/logs":
                        if not player.is_admin:
                            raise APIError("只有本机管理员账号可以查看运行日志。", 403)
                        try:
                            lines = log_path().read_text(encoding="utf-8").splitlines()[-120:]
                        except FileNotFoundError:
                            lines = []
                        self._send_json(200, {"path": str(log_path()), "lines": lines})
                    elif path == "/api/catalog/tasks":
                        query = parse_qs(urlparse(self.path).query)
                        search_text = query.get("q", [""])[0][:120]
                        trader = query.get("trader", [""])[0][:80]
                        try:
                            limit = int(query.get("limit", ["60"])[0])
                        except ValueError as error:
                            raise APIError("目录结果数量无效。") from error
                        self._send_json(200, {"tasks": assistant.catalog_tasks(search_text, trader, limit)})
                    elif path == "/api/maps":
                        self._send_json(200, assistant.map_overview())
                    elif path == "/api/map/image":
                        query = parse_qs(urlparse(self.path).query)
                        map_id = query.get("map_id", [""])[0]
                        floor_key = query.get("floor", [""])[0]
                        image = assistant.map_floor_image(map_id, floor_key)
                        self._send(200, image, "image/svg+xml; charset=utf-8")
                    elif path == "/api/hideout":
                        query = parse_qs(urlparse(self.path).query)
                        force_refresh = query.get("refresh", [""])[0] == "1"
                        self._send_json(200, assistant.hideout_catalog(force_refresh))
                    elif path == "/api/map":
                        query = parse_qs(urlparse(self.path).query)
                        map_id = query.get("map_id", [""])[0]
                        floor_key = query.get("floor", [""])[0]
                        self._send_json(200, assistant.map_view(map_id, floor_key))
                    else:
                        self._send_json(404, {"error": "路径不存在。"})
            except Exception as error:
                self._dispatch_error(error)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                if mobile_only and path not in {"/api/auth/mobile-pair", "/api/auth/logout"}:
                    raise APIError("局域网入口仅提供手机地图只读访问。", 403)
                self._enforce_same_origin()
                if path == "/api/capture/upload":
                    player = self._require_player()
                    assistant = state.state_for(player)
                    image_bytes = self._read_capture_jpeg()
                    self._send_json(
                        202,
                        assistant.receive_screenshot(image_bytes, source="screenshot_folder"),
                    )
                    return
                payload = self._read_json()
                if path == "/api/auth/mobile-pair":
                    result = state.auth.consume_mobile_pairing_token(
                        str(payload.get("token", ""))
                    )
                    if result is None:
                        raise APIError("二维码已过期或已使用，请从电脑重新生成。", 401)
                    player, token = result
                    state.state_for(player)
                    log_event("mobile_device_paired", player_id=player.id)
                    self._send_json(
                        200,
                        {"player": player.public_data()},
                        (self._session_cookie(token, SESSION_LIFETIME_SECONDS),),
                    )
                    return
                if path == "/api/auth/logout":
                    token = self._session_token()
                    if state.auth.session_scope(token) != "mobile":
                        raise APIError("没有可退出的手机会话。", 401)
                    state.auth.logout(token)
                    self._send_json(
                        200,
                        {"logged_out": True},
                        (self._session_cookie("", 0),),
                    )
                    return
                player = self._require_player()
                assistant = state.state_for(player)
                if path == "/api/profiles/name":
                    profile = assistant.name_initial_profile(str(payload.get("name", "")))
                    self._send_json(200, {"profile": _profile_json(profile)})
                elif path == "/api/mobile/pairing":
                    network = mobile_network
                    if not network.get("lan_enabled"):
                        raise APIError(
                            "手机地图服务未能启动；请检查端口占用和 Windows 防火墙。",
                            409,
                        )
                    try:
                        address = str(ipaddress.IPv4Address(str(payload.get("address", ""))))
                    except ipaddress.AddressValueError as error:
                        raise APIError("请选择有效的局域网 IPv4 地址。") from error
                    if address not in network["addresses"]:
                        raise APIError("所选地址不属于当前服务的局域网地址。", 403)
                    token, expires_at = state.auth.create_mobile_pairing_token(player.id)
                    mobile_url = f"http://{address}:{network['port']}/mobile#pair={token}"
                    qr_code = qrcode.QRCode(
                        error_correction=qrcode.constants.ERROR_CORRECT_M,
                        border=4,
                    )
                    qr_code.add_data(mobile_url)
                    qr_code.make(fit=True)
                    matrix = [[bool(module) for module in row] for row in qr_code.get_matrix()]
                    self._send_json(
                        201,
                        {
                            "url": mobile_url,
                            "matrix": matrix,
                            "expires_at": expires_at,
                            "expires_in": network["pairing_lifetime_seconds"],
                        },
                    )
                elif path == "/api/mobile/pairing/cancel":
                    state.auth.cancel_mobile_pairing_tokens(player.id)
                    self._send_json(200, {"cancelled": True})
                elif path == "/api/captures/select":
                    assistant.select_capture(str(payload.get("capture_id", "")))
                    self._send_json(200, {"selected": payload.get("capture_id")})
                elif path == "/api/tasks/restore":
                    tasks = assistant.restore_tasks(payload.get("tasks"))
                    self._send_json(200, {"tasks": [_task_json(task) for task in tasks]})
                elif path == "/api/profiles":
                    profile = assistant.create_profile(
                        str(payload.get("name", "")),
                        str(payload.get("game_mode", "pve")),
                        str(payload.get("season_id", "")),
                    )
                    self._send_json(201, {"profile": _profile_json(profile)})
                elif path == "/api/profiles/select":
                    try:
                        profile_id = int(payload.get("profile_id"))
                    except (TypeError, ValueError) as error:
                        raise APIError("档案 ID 无效。") from error
                    profile = assistant.select_profile(profile_id)
                    self._send_json(200, {"profile": _profile_json(profile)})
                elif path == "/api/tasks":
                    task = assistant.add_task(payload)
                    self._send_json(201, {"task": _task_json(task)})
                elif path == "/api/tasks/clear":
                    deleted_count = assistant.clear_tasks()
                    self._send_json(200, {"cleared_count": deleted_count})
                elif path == "/api/catalog/refresh":
                    self._send_json(202, assistant.request_catalog_refresh())
                elif path == "/api/catalog/details":
                    try:
                        snapshot_id = int(payload.get("snapshot_id"))
                    except (TypeError, ValueError) as error:
                        raise APIError("任务资料快照 ID 无效。") from error
                    source_task_id = str(payload.get("source_task_id", ""))
                    with assistant.lock:
                        profile_id = assistant.selected_profile_id
                    task = assistant.load_catalog_task_details(snapshot_id, source_task_id)
                    assistant.update_pending_candidate_details(
                        profile_id, source_task_id, task
                    )
                    self._send_json(200, {"task": task})
                elif path == "/api/catalog/import":
                    try:
                        snapshot_id = int(payload.get("snapshot_id"))
                    except (TypeError, ValueError) as error:
                        raise APIError("任务资料快照 ID 无效。") from error
                    source_task_id = str(payload.get("source_task_id", ""))
                    task = assistant.import_catalog_task(snapshot_id, source_task_id)
                    self._send_json(201, {"task": _task_json(task)})
                elif path == "/api/map/markers/visit":
                    self._send_json(200, assistant.set_map_marker_visited(payload))
                elif path.startswith("/api/tasks/"):
                    parts = path.strip("/").split("/")
                    if len(parts) not in {4, 5, 6}:
                        raise APIError("任务操作路径无效。", 404)
                    try:
                        task_id = int(parts[2])
                    except ValueError as error:
                        raise APIError("任务 ID 无效。") from error
                    if len(parts) == 5 and parts[3] == "requirements":
                        try:
                            requirement_index = int(parts[4])
                        except ValueError as error:
                            raise APIError("任务要求编号无效。") from error
                        task = assistant.set_task_requirement(
                            task_id, requirement_index, payload.get("completed")
                        )
                    elif len(parts) == 6 and parts[3] == "requirements" and parts[5] == "count":
                        try:
                            requirement_index = int(parts[4])
                        except ValueError as error:
                            raise APIError("任务要求编号无效。") from error
                        task = assistant.set_task_requirement_count(
                            task_id, requirement_index, payload.get("current_count")
                        )
                    elif len(parts) == 4 and parts[3] == "increment":
                        task = assistant.increment_task(task_id)
                    elif len(parts) == 4 and parts[3] == "complete":
                        task = assistant.complete_task(task_id)
                    elif len(parts) == 4 and parts[3] == "delete":
                        task = assistant.delete_task(task_id)
                        self._send_json(200, {"deleted_task": _task_json(task)})
                        return
                    else:
                        raise APIError("任务操作不存在。", 404)
                    self._send_json(200, {"task": _task_json(task)})
                else:
                    self._send_json(404, {"error": "路径不存在。"})
            except Exception as error:
                self._dispatch_error(error)

        def _send_static(self, filename: str) -> None:
            path = (WEB_ROOT / filename).resolve()
            if path.parent != WEB_ROOT.resolve() or not path.is_file():
                self._send_json(404, {"error": "静态资源不存在。"})
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in {"application/javascript"}:
                content_type += "; charset=utf-8"
            self._send(200, path.read_bytes(), content_type)

    return Handler


class _ApplicationHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can bind an existing listener and misdirect requests.
    # Never let another app instance share either application's listening port.
    allow_reuse_address = False

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _port_unavailable(error: OSError) -> bool:
    return error.errno == errno.EADDRINUSE or getattr(error, "winerror", None) in (10048, 10013)


def _bind_server(
    state: PlayerStateManager,
    handler: type[BaseHTTPRequestHandler] | None = None,
    *, port: int | None = None,
) -> ThreadingHTTPServer:
    request_handler = handler or _make_handler(state)
    last_error: OSError | None = None
    host = "127.0.0.1"
    for candidate_port in ([port] if port is not None else range(8765, 8786)):
        try:
            server = _ApplicationHTTPServer((host, candidate_port), request_handler)
            server.daemon_threads = True
            return server
        except OSError as error:
            if not _port_unavailable(error):
                raise
            last_error = error
    ports = str(port) if port is not None else "8765-8785"
    raise RuntimeError(f"无法在 {host}:{ports} 启动桌面本地服务：{last_error}")


def _bind_mobile_server(
    handler: type[BaseHTTPRequestHandler],
    *, port: int | None = None,
) -> ThreadingHTTPServer:
    last_error: OSError | None = None
    host = "0.0.0.0"
    for candidate_port in ([port] if port is not None else range(8766, 8787)):
        try:
            server = _ApplicationHTTPServer((host, candidate_port), handler)
            server.daemon_threads = True
            return server
        except OSError as error:
            if not _port_unavailable(error):
                raise
            last_error = error
    ports = str(port) if port is not None else "8766-8786"
    raise RuntimeError(f"无法启动手机只读服务（{host}:{ports}）：{last_error}")


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _tcp_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("端口必须是 0-65535 的整数。") from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("端口必须是 0-65535 的整数。")
    return port


def _startup_options(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EFT Task Assistant local web app")
    parser.add_argument("--port", type=_tcp_port, help="指定桌面回环服务端口（0 为自动分配）")
    parser.add_argument("--mobile-port", type=_tcp_port, help="指定手机只读服务端口（0 为自动分配）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    options = parser.parse_args(argv)
    if options.port not in (None, 0) and options.port == options.mobile_port:
        parser.error("桌面与手机服务不能使用同一个固定端口。")
    return options


def main(argv: list[str] | None = None) -> int:
    options = _startup_options(argv)
    _configure_console_encoding()
    configure_logging()
    state = PlayerStateManager()
    mobile_access_info: dict[str, Any] = {}
    handler = _make_handler(state, mobile_access_info)
    try:
        server = _bind_server(state, handler, port=options.port)
    except Exception:
        state.close()
        raise
    url = f"http://127.0.0.1:{server.server_port}/"
    mobile_server: ThreadingHTTPServer | None = None
    mobile_thread: threading.Thread | None = None
    try:
        mobile_handler = _make_handler(state, mobile_access_info, mobile_only=True)
        mobile_server = _bind_mobile_server(mobile_handler, port=options.mobile_port)
        mobile_access_info.update(_mobile_lan_info(mobile_server))
        mobile_thread = threading.Thread(
            target=mobile_server.serve_forever,
            name="eft-task-assistant-mobile",
            daemon=True,
        )
        mobile_thread.start()
    except Exception as error:
        log_event("mobile_lan_start_failed", level=logging.ERROR, error=repr(error))
        print(f"手机局域网只读服务未能启动：{error}", flush=True)
    log_event("web_server_started", url=url, bind_host="127.0.0.1", local_only=True)
    print(f"EFT 任务助手网页已启动：{url}", flush=True)
    if mobile_server is not None:
        addresses = mobile_access_info.get("addresses", [])
        print("手机只读地图局域网入口（扫码配对后可访问）：", flush=True)
        for address in addresses:
            print(f"  http://{address}:{mobile_server.server_port}/mobile", flush=True)
        if not addresses:
            print("未检测到可用的局域网 IPv4 地址。", flush=True)
    print(f"诊断日志：{log_path()}", flush=True)
    if not options.no_browser:
        webbrowser.open(url, new=2)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if mobile_server is not None:
            mobile_server.shutdown()
            mobile_server.server_close()
        if mobile_thread is not None:
            mobile_thread.join(timeout=2)
        server.shutdown()
        server.server_close()
        state.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
