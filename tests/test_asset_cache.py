import hashlib
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from asset_cache import (
    AssetValidationError, DiskAssetCache, FetchError, FetchResult,
    make_asset_key, validate_image,
)


SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><path d="M0 0L1 1"/></svg>'


def make_cache(tmp_path, **options):
    return DiskAssetCache(tmp_path, fetch_timeout=options.pop("fetch_timeout", 0.3),
                          retry_backoff=0.01, **options)


def test_version_provider_mode_and_floor_are_isolated(tmp_path):
    cache = make_cache(tmp_path)
    try:
        keys = [make_asset_key(*parts) for parts in [
            ("a", "pve", "map", "1", "v1"), ("b", "pve", "map", "1", "v1"),
            ("a", "pvp", "map", "1", "v1"), ("a", "pve", "map", "2", "v1"),
            ("a", "pve", "map", "1", "v2")]]
        assert len(set(keys)) == 5
        for key in keys:
            assert cache.get_or_fetch(key, lambda: SVG) == SVG
        assert cache.status()["entries"] == 5
    finally:
        cache.close()


def test_restart_hash_validation_and_offline_fallback(tmp_path):
    key = make_asset_key("a", "pve", "map", "1", "version")
    cache = make_cache(tmp_path)
    assert cache.get_or_fetch(key, lambda: SVG) == SVG
    cache.close()
    cache = make_cache(tmp_path, ttl=0)
    calls = []

    def offline():
        calls.append(time.monotonic())
        raise OSError("offline")

    try:
        assert cache.get_or_fetch(key, offline) == SVG
        assert len(calls) == 2
        assert "offline" in cache.status()["warnings"][key]
        with pytest.raises(OSError):
            cache.get_or_fetch("another-provider", offline)
    finally:
        cache.close()


def test_conditional_etag_and_no_fabricated_validator(tmp_path):
    cache = make_cache(tmp_path, ttl=0)
    try:
        cache.get_or_fetch("etag-key", lambda: FetchResult(SVG, "image/svg+xml", '"v1"'))
        received = []

        def revalidate(etag=None, last_modified=None, timeout=None):
            received.append((etag, last_modified, timeout))
            return FetchResult(status=304)

        assert cache.get_or_fetch("etag-key", revalidate) == SVG
        assert received == [('"v1"', None, 0.3)]
        cache.get_or_fetch("no-etag", lambda: SVG)
        metadata = next(json.loads(path.read_text()) for path in tmp_path.glob("*.json")
                        if json.loads(path.read_text())["key"] == "no-etag")
        assert metadata["etag"] is None
        assert metadata["validation"] == "download-hash"
        assert cache.get_or_fetch("no-etag", revalidate) == SVG
        assert "prior validator" in cache.status()["warnings"]["no-etag"]
        with pytest.raises(FetchError):
            cache.get_or_fetch("no-cache", revalidate)
    finally:
        cache.close()


@pytest.mark.parametrize("same_size", [False, True])
def test_corrupt_and_truncated_cache_never_used(tmp_path, same_size):
    cache = make_cache(tmp_path, retries=0)
    cache.get_or_fetch("key", lambda: SVG)
    cache.close()
    blob = next(tmp_path.glob("*.data"))
    blob.write_bytes(b"x" * len(SVG) if same_size else SVG[:20])
    cache = make_cache(tmp_path, retries=0)
    try:
        def offline():
            raise OSError("offline")

        with pytest.raises(OSError):
            cache.get_or_fetch("key", offline)
        assert cache.status()["entries"] == 0
        assert not list(tmp_path.glob("*.data"))
    finally:
        cache.close()


def test_restart_checks_image_even_when_manifest_hash_matches(tmp_path):
    cache = make_cache(tmp_path)
    cache.get_or_fetch("key", lambda: SVG)
    cache.close()
    manifest = next(tmp_path.glob("*.json"))
    metadata = json.loads(manifest.read_text())
    invalid = b"x" * len(SVG)
    (tmp_path / metadata["file"]).write_bytes(invalid)
    metadata["sha256"] = hashlib.sha256(invalid).hexdigest()
    manifest.write_text(json.dumps(metadata))
    cache = make_cache(tmp_path)
    try:
        assert cache.get_or_fetch("key", lambda: SVG) == SVG
        assert cache.status()["entries"] == 1
    finally:
        cache.close()


def test_inflight_dedup_and_foreground_reserved_slot(tmp_path):
    cache = make_cache(tmp_path, workers=2, fetch_timeout=2)
    started = threading.Event()
    release = threading.Event()
    calls = []

    def background():
        calls.append("background")
        started.set()
        release.wait(2)
        return SVG

    try:
        first = cache.submit("background", background)
        assert started.wait(0.5)
        assert cache.submit("background", background) is first
        queued = cache.submit("queued", lambda: calls.append("queued") or SVG)
        beginning = time.perf_counter()
        assert cache.get_or_fetch("foreground", lambda: calls.append("foreground") or SVG) == SVG
        elapsed = time.perf_counter() - beginning
        assert elapsed < 0.5
        assert calls == ["background", "foreground"]
        assert not queued.done()
        print(f"reserved foreground slot: {elapsed:.4f}s while background blocked")
        release.set()
        assert first.result(1) == queued.result(1) == SVG
        assert calls.count("background") == 1
    finally:
        release.set()
        cache.close()


def test_priority_promotion_overtakes_unstarted_background(tmp_path):
    cache = make_cache(tmp_path, workers=1, fetch_timeout=2)
    started = threading.Event()
    release = threading.Event()
    order = []

    def blocking():
        started.set()
        release.wait(2)
        return SVG

    try:
        first = cache.submit("first", blocking)
        assert started.wait(0.5)
        low = cache.submit("low", lambda: order.append("low") or SVG)
        promoted = cache.submit("promote", lambda: order.append("promoted") or SVG)
        assert cache.submit("promote", lambda: b"unused", priority=0) is promoted
        release.set()
        for future in (first, promoted, low):
            assert future.result(1) == SVG
        assert order == ["promoted", "low"]
    finally:
        release.set()
        cache.close()


def test_actual_parallel_fetches_are_bounded_and_not_globally_locked(tmp_path):
    cache = make_cache(tmp_path, workers=2, fetch_timeout=2)
    barrier = threading.Barrier(2)
    intervals = []
    lock = threading.Lock()

    def fetch():
        start = time.perf_counter()
        barrier.wait(1)
        time.sleep(0.06)
        with lock:
            intervals.append((start, time.perf_counter()))
        return SVG

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(cache.get_or_fetch, key, fetch) for key in ("one", "two")]
            assert [future.result(2) for future in futures] == [SVG, SVG]
        overlap = min(end for _, end in intervals) - max(start for start, _ in intervals)
        assert overlap >= 0.05
        print(f"two loader intervals overlap: {overlap:.4f}s; workers=2")
    finally:
        cache.close()


def test_timeout_keeps_callback_threads_bounded_and_close_is_bounded(tmp_path):
    cache = make_cache(tmp_path, workers=2, fetch_timeout=0.05, retries=0)
    release = threading.Event()
    calls = []

    def stuck():
        calls.append(1)
        release.wait(3)
        return SVG

    try:
        beginning = time.monotonic()
        for key in range(5):
            with pytest.raises(TimeoutError):
                cache.get_or_fetch(str(key), stuck)
        assert len(calls) == 2
        assert time.monotonic() - beginning < 0.8
        beginning = time.monotonic()
        cache.close(timeout=0.2)
        assert time.monotonic() - beginning < 0.3
        assert not list(tmp_path.glob("*.json"))
    finally:
        release.set()
        cache.close()


@pytest.mark.parametrize("error", [FetchError("forbidden", 403), OSError("robots denied"),
                                 FetchError("not found", 404)])
def test_denied_assets_are_not_retried(tmp_path, error):
    cache = make_cache(tmp_path)
    attempts = []

    def fetch():
        attempts.append(1)
        raise error

    try:
        with pytest.raises(OSError):
            cache.get_or_fetch("key", fetch)
        assert attempts == [1]
    finally:
        cache.close()


def test_http_transient_retry_and_warning_clears_after_success(tmp_path):
    cache = make_cache(tmp_path, ttl=0)
    attempts = []

    def fetch():
        attempts.append(time.perf_counter())
        return FetchResult(status=503) if len(attempts) == 1 else {"data": SVG}

    try:
        assert cache.get_or_fetch("key", fetch) == SVG
        assert len(attempts) == 2
        assert attempts[1] - attempts[0] >= 0.01
        assert cache.status()["warnings"] == {}
    finally:
        cache.close()


@pytest.mark.parametrize("payload", [
    b'<svg viewBox="0 0 10 10"><script>alert(1)</script></svg>',
    b'<svg viewBox="0 0 10 10" onload="alert(1)"/>',
    b'<svg viewBox="0 0 10 10"><image href="https://bad/a"/></svg>',
    b'<svg viewBox="0 0 10 10"><style>@import "https://bad";</style></svg>',
    b'<svg viewBox="0 0 10 10"><path fill="url(https://bad)"/></svg>',
    b'<!DOCTYPE svg [<!ENTITY x "bad">]><svg viewBox="0 0 1 1"/>',
    b'<?xml-stylesheet href="https://bad"?><svg viewBox="0 0 1 1"/>',
    b'<svg viewBox="0 0 10 10"><foreignObject/></svg>',
    b'<svg viewBox="0 0 10 10"><set attributeName="href" to="https://bad"/></svg>',
    b'<svg viewBox="0 0 0 5"/>', b'<svg viewBox="0 0 nan 5"/>', SVG[:-8],
])
def test_unsafe_svg_and_bad_dimensions_rejected(payload):
    with pytest.raises(AssetValidationError):
        validate_image(payload)


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_local_raster_assets_verified_and_truncations_rejected(image_format):
    stream = io.BytesIO()
    Image.new("RGB", (64, 32), "green").save(stream, format=image_format)
    data = stream.getvalue()
    assert validate_image(data)["width"] == 64
    with pytest.raises(AssetValidationError):
        validate_image(data[:len(data) // 2])
    with pytest.raises(AssetValidationError):
        validate_image(data, max_pixels=10)
    with pytest.raises(AssetValidationError):
        validate_image(data, "image/svg+xml")


def test_lru_budget_pins_current_and_active_floors_and_cleans_orphans(tmp_path):
    cache = make_cache(tmp_path, max_bytes=1800)
    try:
        cache.get_or_fetch("active", lambda: SVG)
        cache.set_active_keys({"active"})
        cache.get_or_fetch("old", lambda: SVG)
        cache.max_bytes = cache.status()["bytes"] + 64
        cache.get_or_fetch("current", lambda: SVG)
        keys = {json.loads(path.read_text())["key"] for path in tmp_path.glob("*.json")}
        assert "active" in keys and "current" in keys and "old" not in keys
        assert cache.status()["bytes"] <= cache.max_bytes
        cache.set_active_keys(set())
        cache.get_or_fetch("next", lambda: SVG)
        assert cache.status()["bytes"] <= cache.max_bytes
    finally:
        cache.close()
    orphan = tmp_path / ("a" * 64 + "." + "b" * 32 + ".data")
    temporary = tmp_path / ("a" * 64 + "." + "c" * 32 + ".tmp")
    orphan.write_bytes(b"orphan")
    temporary.write_bytes(b"partial")
    cache = make_cache(tmp_path, max_bytes=1800)
    try:
        assert not orphan.exists() and not temporary.exists()
        assert cache.status()["bytes"] == sum(path.stat().st_size for path in tmp_path.iterdir())
    finally:
        cache.close()


def test_close_cancels_queued_and_rejects_new_work(tmp_path):
    cache = make_cache(tmp_path, workers=1, fetch_timeout=2)
    release = threading.Event()
    started = threading.Event()

    def fetch():
        started.set()
        release.wait(2)
        return SVG

    first = cache.submit("first", fetch)
    assert started.wait(0.5)
    queued = cache.submit("queued", lambda: SVG)
    cache.close(timeout=0.2)
    try:
        assert queued.cancelled()
        with pytest.raises(RuntimeError):
            first.result(0.3)
        with pytest.raises(RuntimeError):
            cache.submit("new", lambda: SVG)
    finally:
        release.set()


def test_budget_never_deletes_pinned_floor_to_store_new_asset(tmp_path):
    cache = make_cache(tmp_path)
    try:
        cache.get_or_fetch("pinned", lambda: SVG)
        cache.max_bytes = cache.status()["bytes"] + 32
        cache.set_active_keys({"pinned"})
        assert cache.get_or_fetch("new", lambda: SVG) == SVG
        assert cache.status()["entries"] == 1
        assert not cache.status()["over_budget"]
        assert "without persisting" in cache.status()["warnings"]["new"]
        metadata = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert metadata["key"] == "pinned"
        assert sum(path.stat().st_size for path in tmp_path.iterdir()) <= cache.max_bytes
    finally:
        cache.close()


def test_failed_manifest_commit_preserves_previous_verified_generation(tmp_path, monkeypatch):
    cache = make_cache(tmp_path, ttl=0, retries=0)
    try:
        cache.get_or_fetch("key", lambda: FetchResult(SVG, etag="original"))
        original_manifest = next(tmp_path.glob("*.json")).read_bytes()
        newer = SVG.replace(b"100 50", b"200 50")

        def fail(metadata):
            raise OSError("simulated full disk")

        monkeypatch.setattr(cache, "_write_manifest", fail)
        assert cache.get_or_fetch("key", lambda: FetchResult(newer, etag="new")) == SVG
        assert next(tmp_path.glob("*.json")).read_bytes() == original_manifest
        assert len(list(tmp_path.glob("*.data"))) == 1
        assert next(tmp_path.glob("*.data")).read_bytes() == SVG
        assert not list(tmp_path.glob("*.tmp"))
        assert "full disk" in cache.status()["warnings"]["key"]
    finally:
        cache.close()


def test_fresh_cache_does_not_fetch_and_lru_access_survives_restart(tmp_path):
    cache = make_cache(tmp_path)
    cache.get_or_fetch("first", lambda: SVG)
    cache.get_or_fetch("second", lambda: SVG)
    time.sleep(0.01)
    assert cache.get_or_fetch("first", lambda: pytest.fail("fresh cache fetched")) == SVG
    cache.close()
    cache = make_cache(tmp_path)
    try:
        cache.max_bytes = cache.status()["bytes"] + 32
        cache.get_or_fetch("third", lambda: SVG)
        keys = {json.loads(path.read_text())["key"] for path in tmp_path.glob("*.json")}
        assert keys == {"first", "third"}
        assert cache.status()["bytes"] <= cache.max_bytes
    finally:
        cache.close()


def test_late_timeout_callback_never_commits_and_slots_recover(tmp_path):
    cache = make_cache(tmp_path, workers=1, fetch_timeout=0.05, retries=0)
    release = threading.Event()
    finished = threading.Event()

    def late():
        release.wait(1)
        finished.set()
        return SVG

    try:
        with pytest.raises(TimeoutError):
            cache.get_or_fetch("late", late)
        release.set()
        assert finished.wait(0.5)
        assert cache.get_or_fetch("next", lambda: SVG) == SVG
        keys = {json.loads(path.read_text())["key"] for path in tmp_path.glob("*.json")}
        assert keys == {"next"}
    finally:
        release.set()
        cache.close()


def test_denied_status_cannot_claim_conditional_validation(tmp_path):
    cache = make_cache(tmp_path, ttl=0)
    calls = []
    try:
        cache.get_or_fetch("key", lambda: FetchResult(SVG, etag="original"))

        def denied(etag=None):
            calls.append(etag)
            return FetchResult(status=403, not_modified=True)

        with pytest.raises(FetchError, match="403"):
            cache.get_or_fetch("key", denied)
        assert calls == ["original"]
        assert "403" in cache.status()["warnings"]["key"]
        metadata = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert metadata["validation"] == "download-hash"
    finally:
        cache.close()


def test_last_modified_only_condition_never_fabricates_etag(tmp_path):
    cache = make_cache(tmp_path, ttl=0)
    try:
        cache.get_or_fetch("key", lambda: FetchResult(SVG, last_modified="Wed, 01 Jan 2025 00:00:00 GMT"))

        def revalidate(etag=None, last_modified=None):
            assert etag is None
            assert last_modified == "Wed, 01 Jan 2025 00:00:00 GMT"
            return FetchResult(status=304)

        assert cache.get_or_fetch("key", revalidate) == SVG
        metadata = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert metadata["etag"] is None
        assert metadata["validation"] == "conditional"
    finally:
        cache.close()
