"""Persistent, validated image cache with bounded, priority-aware fetching.

Adapters own URL policy and resource versions. This module never opens a URL.
Callbacks may accept ``etag``, ``last_modified`` and ``timeout`` keyword arguments.
Callbacks must set their transport timeout; non-cooperative callbacks are bounded
by a fixed number of daemon execution slots and never block process shutdown.
"""
from __future__ import annotations

import hashlib
import heapq
import inspect
import io
import json
import math
import os
import re
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


IMAGE_DECODE_LOCK = threading.RLock()


@dataclass(frozen=True)
class FetchResult:
    data: bytes = b""
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    status: int = 200


class AssetValidationError(ValueError):
    pass


class FetchError(OSError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class AssetBudgetError(RuntimeError):
    pass


def make_asset_key(provider: str, mode: str, map_id: str, floor: str,
                   version: str = "unversioned") -> str:
    """Use the upstream version/asset URL digest when available; otherwise use TTL."""
    parts = (provider, mode, map_id, floor, version)
    if not all(isinstance(part, str) and part for part in parts):
        raise ValueError("Asset key components must be nonempty strings")
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


class BoundedCallbacks:
    """Bound caller wait AND the number of live non-cooperative callbacks."""

    def __init__(self, workers: int) -> None:
        self._slots = threading.BoundedSemaphore(workers)
        self._closed = threading.Event()

    def call(self, callback: Callable[[], Any], timeout: float,
             cancel: threading.Event | None = None) -> Any:
        deadline = time.monotonic() + timeout
        while not self._slots.acquire(timeout=min(0.02, max(0, deadline - time.monotonic()))):
            self._check(deadline, cancel)
        try:
            self._check(deadline, cancel)
        except BaseException:
            self._slots.release()
            raise
        result: Future = Future()

        def execute() -> None:
            try:
                result.set_result(callback())
            except BaseException as error:
                result.set_exception(error)
            finally:
                self._slots.release()

        threading.Thread(target=execute, name="asset-callback", daemon=True).start()
        while not result.done():
            self._check(deadline, cancel)
            threading.Event().wait(min(0.02, max(0, deadline - time.monotonic())))
        return result.result()

    def _check(self, deadline: float, cancel: threading.Event | None) -> None:
        if self._closed.is_set() or (cancel is not None and cancel.is_set()):
            raise RuntimeError("Callback cancelled")
        if time.monotonic() >= deadline:
            raise TimeoutError("Asset callback deadline exceeded")

    def close(self) -> None:
        self._closed.set()


def _dimensions(width: float, height: float, max_pixels: int) -> tuple[float, float]:
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise AssetValidationError("Invalid image dimensions")
    if width * height > max_pixels:
        raise AssetValidationError("Image exceeds pixel limit")
    return width, height


def validate_image(data: bytes, content_type: str | None = None,
                   max_pixels: int = 100_000_000) -> dict[str, Any]:
    with IMAGE_DECODE_LOCK:
        return _validate_image(data, content_type, max_pixels)


def _validate_image(data: bytes, content_type: str | None = None,
                    max_pixels: int = 100_000_000) -> dict[str, Any]:
    if not isinstance(data, bytes) or not data:
        raise AssetValidationError("Empty or non-byte image")
    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if data.lstrip().startswith(b"<"):
        try:
            source = data.decode("utf-8-sig")
            if re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?(?!xml\s)", source, re.I):
                raise AssetValidationError("SVG declarations are forbidden")
            root = ET.fromstring(source)
            if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
                raise AssetValidationError("Expected SVG root")
            if declared and declared != "image/svg+xml":
                raise AssetValidationError("Image content type mismatch")
            for element in root.iter():
                tag = element.tag.rsplit("}", 1)[-1].lower()
                if tag in {"script", "foreignobject", "iframe", "object", "embed",
                           "animate", "animatetransform", "animatemotion", "set"}:
                    raise AssetValidationError("Active SVG elements are forbidden")
                values = list(element.attrib.values())
                if tag == "style":
                    values.append(element.text or "")
                for attribute, value in element.attrib.items():
                    name = attribute.rsplit("}", 1)[-1].lower()
                    if name.startswith("on") or name == "base":
                        raise AssetValidationError("Active SVG attributes are forbidden")
                    if name in {"href", "src"} and value.strip() and not value.strip().startswith("#"):
                        raise AssetValidationError("External SVG references are forbidden")
                for value in values:
                    if re.search(r"@import|javascript:|expression\s*\(|\\|/\*", value, re.I):
                        raise AssetValidationError("Unsafe SVG style")
                    for reference in re.findall(r"url\s*\((.*?)\)", value, re.I | re.S):
                        if not reference.strip(" \t\r\n\"'").startswith("#"):
                            raise AssetValidationError("External SVG styles are forbidden")
            viewbox = root.get("viewBox")
            if viewbox:
                values = [float(value) for value in re.split(r"[\s,]+", viewbox.strip())]
                if len(values) != 4 or not all(math.isfinite(value) for value in values):
                    raise AssetValidationError("Invalid SVG viewBox")
                width, height = values[2:]
            else:
                width = float(re.sub(r"px$", "", root.get("width", "")))
                height = float(re.sub(r"px$", "", root.get("height", "")))
            _dimensions(width, height, max_pixels)
            return {"content_type": "image/svg+xml", "width": width, "height": height}
        except (ET.ParseError, UnicodeError, ValueError) as error:
            raise AssetValidationError(str(error)) from error
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as picture:
            image_format = picture.format
            if image_format not in {"PNG", "JPEG", "WEBP"}:
                raise AssetValidationError("Unsupported image format")
            width, height = _dimensions(*picture.size, max_pixels)
            picture.verify()
        with Image.open(io.BytesIO(data)) as picture:
            picture.load()
        detected = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image_format]
        if declared and declared != detected:
            raise AssetValidationError("Image content type mismatch")
        return {"content_type": detected, "width": width, "height": height}
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise AssetValidationError(str(error)) from error


def _invoke_fetch(fetch: Callable, metadata: dict[str, Any], timeout: float) -> Any:
    try:
        parameters = inspect.signature(fetch).parameters
    except (TypeError, ValueError):
        return fetch()
    values = {"etag": metadata.get("etag"),
              "last_modified": metadata.get("last_modified"), "timeout": timeout}
    accepts_keywords = any(parameter.kind == inspect.Parameter.VAR_KEYWORD
                           for parameter in parameters.values())
    arguments = {name: value for name, value in values.items()
                 if accepts_keywords or (name in parameters and
                 parameters[name].kind != inspect.Parameter.POSITIONAL_ONLY)}
    return fetch(**arguments)


def _retryable(error: BaseException) -> bool:
    if policy_denied(error):
        return False
    status = getattr(error, "status", None) or getattr(error, "code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    if status is not None and 400 <= int(status) < 500 and int(status) not in (408, 429):
        return False
    if isinstance(error, (AssetValidationError, TypeError, ValueError, RuntimeError)):
        return False
    message = str(error).lower()
    return "robots" not in message and "forbidden" not in message and "403" not in message


def policy_denied(error: BaseException) -> bool:
    """Adapters may mark non-HTTP policy failures with asset_access_denied=True."""
    status = getattr(error, "status", None) or getattr(error, "code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    message = str(error).lower()
    return (isinstance(error, PermissionError) or getattr(error, "asset_access_denied", False) or
            status in (401, 403)) or any(word in message for word in
                                      ("robots", "forbidden", "401", "403"))


@dataclass
class _Job:
    key: str
    fetch: Callable
    priority: int
    future: Future
    revision: int = 0
    running: bool = False
    allow_eviction: bool = True


class DiskAssetCache:
    def __init__(self, root: str | Path, max_bytes: int = 512 * 1024 * 1024,
                 workers: int = 2, *, ttl: float = 12 * 3600,
                 fetch_timeout: float = 15, retries: int = 1,
                 retry_backoff: float = 0.1, max_asset_bytes: int = 64 * 1024 * 1024,
                 max_pixels: int = 100_000_000) -> None:
        if workers < 1 or max_bytes < 1 or fetch_timeout <= 0 or ttl < 0:
            raise ValueError("Invalid cache limits")
        if retries not in (0, 1, 2) or retry_backoff < 0 or max_asset_bytes < 1 or max_pixels < 1:
            raise ValueError("Invalid validation/retry limits")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.ttl = ttl
        self.fetch_timeout = fetch_timeout
        self.retries = retries
        self.retry_backoff = retry_backoff
        self.max_asset_bytes = max_asset_bytes
        self.max_pixels = max_pixels
        self._condition = threading.Condition(threading.RLock())
        self._stop = threading.Event()
        self._queue: list[tuple[int, int, str, int]] = []
        self._sequence = 0
        self._jobs: dict[str, _Job] = {}
        self._entries: dict[str, dict[str, Any]] = {}
        self._warnings: dict[str, str] = {}
        self._active: set[str] = set()
        self._current: str | None = None
        self._completed = 0
        self._failed = 0
        self._evicted: dict[str, int] = {}
        self._callbacks = BoundedCallbacks(workers)
        self._recover()
        self._threads = [threading.Thread(target=self._worker,
                         args=(workers > 1 and index == 0,),
                         name=f"asset-worker-{index}", daemon=True) for index in range(workers)]
        for thread in self._threads:
            thread.start()

    @staticmethod
    def _digest(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _recover(self) -> None:
        referenced = set()
        for path in self.root.glob("*.json"):
            if not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
                continue
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
                key = metadata["key"]
                filename = metadata["file"]
                if (not isinstance(key, str) or self._digest(key) != path.stem or
                    not re.fullmatch(path.stem + r"\.[0-9a-f]{32}\.data", filename) or
                    metadata["schema"] != 1 or
                    not re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]) or
                    not 0 < metadata["size"] <= self.max_asset_bytes or
                    not isinstance(metadata["content_type"], str) or
                    any(not math.isfinite(metadata[field]) for field in
                        ("accessed_at", "validated_at", "fetched_at")) or
                    (self.root / filename).stat().st_size != metadata["size"]):
                    raise ValueError("Invalid cache manifest")
                manifest_stat = path.stat()
                metadata["accessed_at"] = max(metadata["accessed_at"], manifest_stat.st_mtime)
                metadata["disk_bytes"] = metadata["size"] + manifest_stat.st_size
                self._entries[key] = metadata
                referenced.add(filename)
            except (OSError, ValueError, KeyError, TypeError):
                self._unlink(path)
        for path in self.root.iterdir():
            if re.fullmatch(r"[0-9a-f]{64}\.[0-9a-f]{32}\.(?:data|tmp)", path.name) and path.name not in referenced:
                self._unlink(path)
        self._evict()

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _write_manifest(self, metadata: dict[str, Any]) -> None:
        digest = self._digest(metadata["key"])
        temporary = self.root / f"{digest}.{uuid.uuid4().hex}.tmp"
        payload = {key: value for key, value in metadata.items() if key != "disk_bytes"}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        try:
            with temporary.open("wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.root / f"{digest}.json")
            metadata["disk_bytes"] = metadata["size"] + len(encoded)
        finally:
            self._unlink(temporary)

    def _read(self, key: str) -> tuple[bytes | None, dict[str, Any]]:
        with self._condition:
            metadata = dict(self._entries.get(key, {}))
        if not metadata:
            return None, {}
        try:
            path = self.root / metadata["file"]
            if path.stat().st_size != metadata["size"]:
                raise AssetValidationError("Cached image size mismatch")
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != metadata["sha256"]:
                raise AssetValidationError("Cached image hash mismatch")
            validate_image(data, metadata["content_type"], self.max_pixels)
            metadata["accessed_at"] = time.time()
            os.utime(self.root / (self._digest(key) + ".json"), None)
            with self._condition:
                self._entries[key] = metadata
            return data, metadata
        except (OSError, ValueError) as error:
            with self._condition:
                self._warnings[key] = f"Corrupt cache discarded: {error}"
                self._remove(key)
            return None, {}

    def _remove(self, key: str) -> None:
        metadata = self._entries.pop(key, None)
        if metadata:
            self._unlink(self.root / metadata["file"])
        self._unlink(self.root / (self._digest(key) + ".json"))

    def entry_status(self, keys: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Inspect residency/TTL without decoding media or making network requests."""
        with self._condition:
            result = {}
            for key in keys:
                metadata = self._entries.get(key)
                try:
                    present = bool(metadata and (self.root / metadata["file"]).stat().st_size == metadata["size"])
                except OSError:
                    present = False
                result[key] = {"present": present,
                               "fresh": present and 0 <= time.time() - metadata["validated_at"] < self.ttl,
                               "size": metadata["size"] if present else 0}
            return result

    def fresh_entry(self, key: str) -> bool:
        """Verify fresh encoded bytes without loading a raster into memory."""
        with self._condition:
            metadata = self._entries.get(key)
            if not metadata or not 0 <= time.time() - metadata["validated_at"] < self.ttl:
                return False
            try:
                with (self.root / metadata["file"]).open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if digest == metadata["sha256"]:
                    return True
            except OSError:
                pass
            self._remove(key)
            return False

    def reprioritize(self, priorities: dict[str, int]) -> None:
        """Reorder queued background jobs while retaining foreground promotions."""
        with self._condition:
            for key, priority in priorities.items():
                job = self._jobs.get(key)
                if job is None or job.running or job.priority <= 0 or job.priority == priority:
                    continue
                job.priority = priority
                job.revision += 1
                self._sequence += 1
                heapq.heappush(self._queue, (priority, self._sequence, key, job.revision))
            self._condition.notify_all()

    def _evict(self) -> None:
        total = sum(metadata["disk_bytes"] for metadata in self._entries.values())
        protected = self._active | set(self._jobs)
        if self._current:
            protected.add(self._current)
        for key, metadata in sorted(self._entries.items(), key=lambda item: item[1]["accessed_at"]):
            if total <= self.max_bytes:
                break
            if key not in protected:
                total -= metadata["disk_bytes"]
                self._evicted[key] = metadata["size"]
                self._remove(key)

    def _make_room(self, key: str, required: int, allow_eviction: bool = True) -> bool:
        total = sum(metadata["disk_bytes"] for metadata in self._entries.values())
        old_size = self._entries.get(key, {}).get("disk_bytes", 0)
        if not allow_eviction:
            return total - old_size + required <= self.max_bytes
        protected = self._active | set(self._jobs) | {self._current}
        candidates = sorted(self._entries.items(), key=lambda item: item[1]["accessed_at"])
        available = sum(metadata["disk_bytes"] for candidate, metadata in candidates if candidate not in protected)
        if total - old_size + required - available > self.max_bytes:
            return False
        for candidate, metadata in candidates:
            if total - old_size + required <= self.max_bytes:
                break
            if candidate not in protected:
                total -= metadata["disk_bytes"]
                self._evicted[candidate] = metadata["size"]
                self._remove(candidate)
        return True

    def set_active_keys(self, keys: list[str] | set[str]) -> None:
        """Pin all floors currently displayed; call again to release old floors."""
        with self._condition:
            self._active = set(keys)
            self._evict()

    def get_or_fetch(self, key: str, fetch: Callable, priority: int = 0) -> bytes:
        with self._condition:
            self._current = key
        return self.submit(key, fetch, priority).result()

    def submit(self, key: str, fetch: Callable, priority: int = 10, *,
               allow_eviction: bool = True) -> Future:
        """Return a shared Future[bytes], promoting queued duplicate requests."""
        if not isinstance(key, str) or not key or not callable(fetch):
            raise ValueError("A nonempty versioned key and callable are required")
        with self._condition:
            if self._stop.is_set():
                raise RuntimeError("Asset cache is closed")
            job = self._jobs.get(key)
            if job is None:
                job = _Job(key, fetch, priority, Future(), allow_eviction=allow_eviction)
                self._jobs[key] = job
            elif job.running or priority >= job.priority:
                return job.future
            else:
                job.priority = priority
                job.revision += 1
                if priority <= 0 and not job.allow_eviction:
                    job.fetch = fetch
                    job.allow_eviction = True
            self._sequence += 1
            heapq.heappush(self._queue, (priority, self._sequence, key, job.revision))
            self._condition.notify_all()
            return job.future

    def _worker(self, foreground_only: bool) -> None:
        while True:
            with self._condition:
                while True:
                    if self._stop.is_set():
                        return
                    if not self._queue or (foreground_only and self._queue[0][0] > 0):
                        self._condition.wait()
                        continue
                    _, _, key, revision = heapq.heappop(self._queue)
                    job = self._jobs.get(key)
                    if job is None or job.running or job.revision != revision:
                        continue
                    if not job.future.set_running_or_notify_cancel():
                        self._jobs.pop(key, None)
                        continue
                    job.running = True
                    break
            try:
                value = self._fetch(job)
                error = None
            except BaseException as caught:
                value, error = None, caught
            with self._condition:
                self._jobs.pop(key, None)
                if error is None:
                    self._completed += 1
                else:
                    self._failed += 1
                    self._warnings[key] = str(error)
                self._evict()
            if error is None:
                job.future.set_result(value)
            else:
                job.future.set_exception(error)

    def _fetch(self, job: _Job) -> bytes:
        cached, metadata = self._read(job.key)
        if cached is not None and 0 <= time.time() - metadata["validated_at"] < self.ttl:
            return cached
        for attempt in range(self.retries + 1):
            try:
                raw = self._callbacks.call(
                    lambda: _invoke_fetch(job.fetch, metadata, self.fetch_timeout),
                    self.fetch_timeout, self._stop)
                if self._stop.is_set():
                    raise RuntimeError("Asset cache is closed")
                result = raw if isinstance(raw, FetchResult) else FetchResult(**raw) if isinstance(raw, dict) else FetchResult(data=raw)
                if result.status not in (200, 304):
                    raise FetchError(f"Asset fetch HTTP {result.status}", result.status)
                if result.not_modified or result.status == 304:
                    if cached is None or not (metadata.get("etag") or metadata.get("last_modified")):
                        raise FetchError("304 requires a verified cached image and a prior validator")
                    metadata.update(validated_at=time.time(), accessed_at=time.time())
                    if result.etag is not None:
                        metadata["etag"] = result.etag
                    if result.last_modified is not None:
                        metadata["last_modified"] = result.last_modified
                    metadata["validation"] = "conditional"
                    required = metadata["size"] + len(json.dumps(
                        {name: value for name, value in metadata.items() if name != "disk_bytes"},
                        ensure_ascii=False, sort_keys=True).encode("utf-8"))
                    with self._condition:
                        if not self._make_room(job.key, required, job.allow_eviction or job.priority <= 0):
                            if not job.allow_eviction and job.priority > 0:
                                raise AssetBudgetError("Disk budget prevents background validator refresh")
                            self._warnings[job.key] = "Disk budget prevents persisting refreshed validators"
                            return cached
                        self._write_manifest(metadata)
                        self._entries[job.key] = metadata
                else:
                    if not isinstance(result.data, bytes) or len(result.data) > self.max_asset_bytes:
                        raise AssetValidationError("Asset exceeds byte limit or is not bytes")
                    image_info = validate_image(result.data, result.content_type, self.max_pixels)
                    filename = f"{self._digest(job.key)}.{uuid.uuid4().hex}.data"
                    destination = self.root / filename
                    temporary = destination.with_suffix(".tmp")
                    previous = metadata.get("file")
                    new_metadata = {"schema": 1, "key": job.key, "file": filename,
                                    "size": len(result.data), "sha256": hashlib.sha256(result.data).hexdigest(),
                                    "etag": result.etag, "last_modified": result.last_modified,
                                    "fetched_at": time.time(), "validated_at": time.time(),
                                    "accessed_at": time.time(), "validation": "download-hash", **image_info}
                    required = len(result.data) + len(json.dumps(new_metadata, ensure_ascii=False,
                                                                sort_keys=True).encode("utf-8"))
                    with self._condition:
                        if self._stop.is_set():
                            raise RuntimeError("Asset cache is closed")
                        if not self._make_room(job.key, required, job.allow_eviction or job.priority <= 0):
                            if not job.allow_eviction and job.priority > 0:
                                raise AssetBudgetError("Disk budget exhausted; background preload paused without eviction")
                            self._warnings[job.key] = "Disk budget exhausted by active assets; image served without persisting"
                            return result.data
                        try:
                            with temporary.open("wb") as stream:
                                stream.write(result.data)
                                stream.flush()
                                os.fsync(stream.fileno())
                            temporary.replace(destination)
                            self._write_manifest(new_metadata)
                        except BaseException:
                            self._unlink(destination)
                            raise
                        finally:
                            self._unlink(temporary)
                        if previous:
                            self._unlink(self.root / previous)
                        metadata = new_metadata
                        self._entries[job.key] = metadata
                    cached = result.data
                with self._condition:
                    self._entries[job.key] = metadata
                    self._warnings.pop(job.key, None)
                return cached
            except Exception as error:
                if self._stop.is_set():
                    raise RuntimeError("Asset cache is closed") from error
                if attempt < self.retries and _retryable(error):
                    self._stop.wait(self.retry_backoff * (2 ** attempt))
                    continue
                if cached is not None and not isinstance(error, AssetBudgetError) and not policy_denied(error):
                    with self._condition:
                        self._warnings[job.key] = f"Offline/stale cache fallback: {error}"
                    return cached
                raise
        raise AssertionError("Unreachable retry state")

    def cancel_pending(self, keys: set[str]) -> int:
        futures = []
        with self._condition:
            for key in keys:
                job = self._jobs.get(key)
                if job is not None and not job.running and job.priority > 0:
                    self._jobs.pop(key)
                    futures.append(job.future)
            self._evict()
        for future in futures:
            future.cancel()
        return len(futures)

    def status(self) -> dict[str, Any]:
        with self._condition:
            size = sum(metadata["disk_bytes"] for metadata in self._entries.values())
            return {"entries": len(self._entries), "bytes": size, "max_bytes": self.max_bytes,
                    "over_budget": size > self.max_bytes, "queued": sum(not job.running for job in self._jobs.values()),
                    "running": [key for key, job in self._jobs.items() if job.running],
                    "done": self._completed, "failed": self._failed,
                    "evicted": dict(self._evicted), "evicted_count": len(self._evicted),
                    "warnings": dict(self._warnings), "closed": self._stop.is_set()}

    def close(self, timeout: float = 0.5) -> None:
        self._stop.set()
        self._callbacks.close()
        with self._condition:
            pending = [job.future for job in self._jobs.values() if not job.running]
            self._jobs = {key: job for key, job in self._jobs.items() if job.running}
            self._queue.clear()
            self._condition.notify_all()
        for future in pending:
            future.cancel()
        deadline = time.monotonic() + max(0, timeout)
        for thread in self._threads:
            if thread is not threading.current_thread():
                thread.join(max(0, deadline - time.monotonic()))
