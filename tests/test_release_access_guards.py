import io
import json
import threading
from types import SimpleNamespace
from pathlib import Path
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser

import pytest
from PIL import Image

import catalog
import reemr_maps
from catalog import CatalogError
from data_sources import SourceAdapters
from web_server import AssistantState, _make_handler


MAP = "55f2d3fd4bdc2d5f408b4567"
IMAGE_URL = "https://www.re3mr.com/maps/Factory/release-fixture.png"
PAGE_URL = reemr_maps.ROOT + "factory/"
LICENSE = '<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">License</a>'
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10"/>'


class SyntheticHTTP:
    def __init__(self):
        buffer = io.BytesIO()
        Image.new("RGB", (20, 10), "blue").save(buffer, format="PNG")
        self.image = buffer.getvalue()
        self.calls = []
        self.overrides = {}

    def __call__(self, url, *arguments):
        self.calls.append(url)
        override = self.overrides.get(url)
        if isinstance(override, BaseException):
            raise override
        if override is not None:
            return override
        if url.endswith("/robots.txt"):
            body, mime = b"User-agent: *\nDisallow:\n", "text/plain"
        elif url == reemr_maps.ROOT:
            body, mime = ('<a href="/factory/">Factory</a>' + LICENSE).encode(), "text/html"
        elif url == PAGE_URL:
            body = (f'<a href="{IMAGE_URL}" data-lbwps-width="20" data-lbwps-height="10">Original</a>' + LICENSE).encode()
            mime = "text/html"
        elif url == IMAGE_URL:
            body, mime = self.image, "image/png"
        else:
            pytest.fail("Unexpected synthetic request: " + url)
        return reemr_maps.FetchResponse(body, mime, url, {"status": 200})


@pytest.fixture
def remote(tmp_path):
    http = SyntheticHTTP()
    client = reemr_maps.ReemrMaps(cache_root=tmp_path, fetcher=http)
    adapters = SourceAdapters(tmp_path, reemr_client=client)
    floor = adapters._raw_map_data("reemr", "factory", "pve")["floors"][0]["key"]
    yield http, client, adapters, floor
    adapters.close()


@pytest.mark.parametrize("url", [reemr_maps.ROOT, PAGE_URL])
@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.parametrize("hot", [False, True])
def test_html_rejection_blocks_metadata_hot_assets_and_raw_original(remote, url, status, hot):
    http, client, adapters, floor = remote
    if hot:
        assert adapters.floor_image("reemr", "factory", floor, "pve") == http.image
    downloads = http.calls.count(IMAGE_URL)
    checked, response = client._documents[url]
    client._documents[url] = (checked - reemr_maps.DOCUMENT_TTL - 1, response)
    http.overrides[url] = reemr_maps.FetchResponse(b"", "text/html", url, {"status": status})
    before = http.calls.count(url)
    with pytest.raises(CatalogError, match=str(status)):
        adapters._raw_map_data("reemr", "factory", "pve")
    assert http.calls.count(url) == before + 1
    assert url not in json.loads(client.cache_path.read_text(encoding="utf-8"))["documents"]
    for operation in (
        lambda: client.check_floor_access("factory", floor),
        lambda: adapters.floor_image("reemr", "factory", floor, "pve"),
        lambda: adapters.raw_floor_image("reemr", "factory", floor, "pve"),
    ):
        with pytest.raises(CatalogError):
            operation()
    assert http.calls.count(IMAGE_URL) == downloads
    http.overrides[url] = TimeoutError("synthetic timeout after denial")
    restarted = reemr_maps.ReemrMaps(cache_root=client.cache_path.parents[1], fetcher=http)
    with pytest.raises((CatalogError, OSError)):
        restarted.map_data("factory")


@pytest.mark.parametrize("target", ["site", "image"])
@pytest.mark.parametrize("kind", ["disallow", "invalid", "malformed", "401", "403"])
def test_robots_rejection_cannot_be_overridden_by_warm_html_or_image(remote, target, kind):
    http, client, adapters, floor = remote
    assert adapters.floor_image("reemr", "factory", floor, "pve") == http.image
    origin = reemr_maps.ROOT.rstrip("/") if target == "site" else "https://www.re3mr.com"
    url = origin + "/robots.txt"
    if kind == "disallow":
        override = reemr_maps.FetchResponse(b"User-agent: *\nDisallow: /\n", "text/plain", url)
    elif kind == "invalid":
        override = reemr_maps.FetchResponse(b"<html>blocked</html>", "text/html", url)
    elif kind == "malformed":
        override = reemr_maps.FetchResponse(b"upstream invalid response", "text/plain", url)
    else:
        override = reemr_maps.FetchResponse(b"", "text/plain", url, {"status": int(kind)})
    http.overrides[url] = override
    client._robots.pop(origin)
    downloads = http.calls.count(IMAGE_URL)
    for operation in (
        lambda: client.check_floor_access("factory", floor),
        lambda: adapters.floor_image("reemr", "factory", floor, "pve"),
        lambda: adapters.raw_floor_image("reemr", "factory", floor, "pve"),
    ):
        with pytest.raises(CatalogError):
            operation()
    assert http.calls.count(IMAGE_URL) == downloads
    assert http.calls.count(url) == 2


def test_temporary_html_outage_keeps_warned_offline_original(remote):
    http, client, adapters, floor = remote
    assert adapters.floor_image("reemr", "factory", floor, "pve") == http.image
    for url in (reemr_maps.ROOT, PAGE_URL):
        checked, response = client._documents[url]
        client._documents[url] = (checked - reemr_maps.DOCUMENT_TTL - 1, response)
        http.overrides[url] = TimeoutError("synthetic timeout")
    config = adapters._raw_map_data("reemr", "factory", "pve")
    assert config["cache_status"]["stale"]
    assert all(item["last_failure"] for item in config["cache_status"]["documents"])
    assert adapters.floor_image("reemr", "factory", floor, "pve") == http.image
    assert http.calls.count(IMAGE_URL) == 1


@pytest.mark.parametrize("status", [401, 403])
def test_reemr_original_denial_never_retries_or_returns_stale_bytes(remote, status):
    http, client, adapters, floor = remote
    assert adapters.floor_image("reemr", "factory", floor, "pve") == http.image
    adapters.asset_cache.ttl = 0
    http.overrides[IMAGE_URL] = reemr_maps.FetchResponse(b"", "text/html", IMAGE_URL, {"status": status})
    before = http.calls.count(IMAGE_URL)
    with pytest.raises(CatalogError):
        adapters.floor_image("reemr", "factory", floor, "pve")
    assert http.calls.count(IMAGE_URL) == before + 1
    with pytest.raises(CatalogError):
        adapters.floor_image("reemr", "factory", floor, "pve")
    assert http.calls.count(IMAGE_URL) == before + 1


@pytest.fixture
def eft(tmp_path, monkeypatch):
    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Disallow:"])
    monkeypatch.setattr(catalog, "_robots_parser", lambda: parser)
    config = {"map_id": MAP, "name": "Synthetic", "markers": [], "floors": [
        {"key": "1", "src": f"{catalog.EFTARKOV_ROOT}/assets/maps/{MAP}/1.svg", "width": 20, "height": 10}]}
    calls = []
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_data", lambda *args: config)
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_index", lambda *args: [{"map_id": MAP}])

    def image(*arguments):
        calls.append(arguments)
        return SVG

    monkeypatch.setattr(catalog, "fetch_eftarkov_map_floor_image", image)
    adapters = SourceAdapters(tmp_path)
    yield adapters, parser, calls
    adapters.close()


@pytest.mark.parametrize("rule", ["/map", "/assets/", "invalid"])
def test_eft_robots_changes_block_fresh_metadata_and_hot_original(eft, rule):
    adapters, parser, calls = eft
    adapters.map_index("eftarkov", "pve")
    assert adapters.floor_image("eftarkov", MAP, "1", "pve") == SVG
    if rule == "invalid":
        parser.default_entry = None
        parser.entries = []
    else:
        parser.default_entry = None
        parser.parse(["User-agent: *", "Disallow: " + rule])
    if rule != "/assets/":
        for operation in (
            lambda: adapters.map_index("eftarkov", "pve"),
            lambda: adapters._raw_map_data("eftarkov", MAP, "pve"),
        ):
            with pytest.raises(CatalogError):
                operation()
    for operation in (
        lambda: adapters.floor_image("eftarkov", MAP, "1", "pve"),
        lambda: adapters.raw_floor_image("eftarkov", MAP, "1", "pve"),
    ):
        with pytest.raises(CatalogError):
            operation()
    assert len(calls) == 1


@pytest.mark.parametrize("status", [401, 403])
def test_eft_html_rejection_cannot_fall_back_to_config_or_hot_asset(eft, monkeypatch, status):
    adapters, parser, calls = eft
    assert adapters.floor_image("eftarkov", MAP, "1", "pve") == SVG
    adapters.ttl = 0
    attempts = []

    def denied(*arguments):
        attempts.append(arguments)
        failure = CatalogError("upstream rejected")
        failure.__cause__ = HTTPError(catalog.EFTARKOV_ROOT + "/map/" + MAP, status, "denied", {}, None)
        raise failure

    monkeypatch.setattr(catalog, "fetch_eftarkov_map_data", denied)
    with pytest.raises(CatalogError):
        adapters._raw_map_data("eftarkov", MAP, "pve")
    assert len(attempts) == 1
    for operation in (
        lambda: adapters.floor_image("eftarkov", MAP, "1", "pve"),
        lambda: adapters.raw_floor_image("eftarkov", MAP, "1", "pve"),
    ):
        with pytest.raises(CatalogError):
            operation()
    assert len(calls) == 1

    def offline(*arguments):
        raise TimeoutError("synthetic offline after denial")

    monkeypatch.setattr(catalog, "fetch_eftarkov_map_data", offline)
    with pytest.raises((CatalogError, OSError)):
        adapters.floor_image("eftarkov", MAP, "1", "pve")


@pytest.mark.parametrize("status", [401, 403])
def test_eft_original_denial_never_retries_or_returns_stale_bytes(eft, monkeypatch, status):
    adapters, parser, calls = eft
    assert adapters.floor_image("eftarkov", MAP, "1", "pve") == SVG
    adapters.asset_cache.ttl = 0
    attempts = []

    def denied(*arguments):
        attempts.append(arguments)
        failure = CatalogError("upstream original rejected")
        failure.__cause__ = HTTPError("https://www.eftarkov.com/assets/maps/fixture.svg", status, "denied", {}, None)
        raise failure

    monkeypatch.setattr(catalog, "fetch_eftarkov_map_floor_image", denied)
    with pytest.raises(CatalogError):
        adapters.floor_image("eftarkov", MAP, "1", "pve")
    assert len(attempts) == 1
    adapters.asset_cache.ttl = 3600
    with pytest.raises(CatalogError):
        adapters.floor_image("eftarkov", MAP, "1", "pve")
    assert len(attempts) == 1
    restarted = SourceAdapters(adapters.root)
    try:
        with pytest.raises(CatalogError):
            restarted.floor_image("eftarkov", MAP, "1", "pve")
        assert len(attempts) == 1
    finally:
        restarted.close()
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_floor_image", lambda *arguments: SVG)
    assert adapters.raw_floor_image("eftarkov", MAP, "1", "pve") == SVG
    assert adapters.floor_image("eftarkov", MAP, "1", "pve") == SVG


def test_eft_temporary_outage_keeps_warned_metadata_and_original(eft, monkeypatch):
    adapters, parser, calls = eft
    assert adapters.floor_image("eftarkov", MAP, "1", "pve") == SVG
    adapters.ttl = adapters.asset_cache.ttl = 0

    def unavailable(*arguments):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(catalog, "fetch_eftarkov_map_data", unavailable)
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_floor_image", unavailable)
    assert adapters.floor_image("eftarkov", MAP, "1", "pve") == SVG
    assert "eftarkov" in adapters.cache_status()["warnings"]


@pytest.mark.parametrize("source", ["reemr", "eftarkov", "tarkov.dev"])
@pytest.mark.parametrize("reason", ["HTTP 401", "HTTP 403", "robots invalid", "permission denied while offline", "invalid document", "offline"])
def test_metadata_fallback_is_only_for_temporary_network_failures(eft, source, reason):
    adapters, parser, calls = eft
    assert adapters.cached(source, "fixture", lambda: {"previous": True}) == {"previous": True}
    adapters.ttl = 0

    def rejected():
        raise CatalogError(reason)

    with pytest.raises(CatalogError):
        adapters.cached(source, "fixture", rejected)


@pytest.mark.parametrize("source", ["reemr", "eftarkov", "tarkov.dev"])
def test_metadata_timeout_still_returns_warned_cache(eft, source):
    adapters, parser, calls = eft
    adapters.cached(source, "fixture", lambda: {"previous": True})
    adapters.ttl = 0

    def unavailable():
        raise TimeoutError("synthetic timeout")

    assert adapters.cached(source, "fixture", unavailable) == {"previous": True}
    assert "离线缓存" in adapters.warnings[source]


def handler_for(assistant, mobile_only=True, mobile_session=True):
    player = SimpleNamespace(is_admin=True)
    manager = SimpleNamespace(
        runtime_root=None,
        auth=SimpleNamespace(session_scope=lambda token: "mobile" if mobile_session else None,
                             root=Path(__file__).resolve().parent / "synthetic-handler",
                             authenticate=lambda token: player),
        local_player=player, state_for=lambda selected: assistant)
    handler = object.__new__(_make_handler(manager, mobile_only=mobile_only))
    handler.command = "GET"
    handler.headers = {}
    handler.client_address = ("127.0.0.1", 12345)
    responses = []
    handler._send = lambda status, body, mime, *headers: responses.append((status, body))
    return handler, responses


@pytest.mark.parametrize("mobile_only", [True, False])
@pytest.mark.parametrize("source", [None, "", "tarkov.dev", "eftarkov"])
def test_mobile_source_is_pinned_before_desktop_switch_at_image_call(mobile_only, source):
    assistant = object.__new__(AssistantState)
    assistant.lock = threading.RLock()
    assistant.selected_profile_id = 1
    assistant.profiles = lambda: [SimpleNamespace(id=1, game_mode="pve")]
    selected = {"source": "tarkov.dev"}
    resolutions, reads = [], []
    entered, switched = threading.Event(), threading.Event()
    originals = {"reemr": b"RE3MR-ORIGINAL-HOT-CACHE", "tarkov.dev": SVG, "eftarkov": SVG}

    def resolve(profile_id):
        resolutions.append(profile_id)
        return selected["source"]

    def image(provider, *arguments):
        reads.append(provider)
        return originals[provider]

    def switch_desktop():
        assert entered.wait(2)
        with assistant.lock:
            selected["source"] = "reemr"
        switched.set()

    def boundary(map_id, floor, provider=None):
        entered.set()
        assert switched.wait(2)
        return AssistantState.map_floor_image(assistant, map_id, floor, provider)

    assistant.source_for_profile = resolve
    assistant.sources = SimpleNamespace(floor_image=image)
    assistant.map_floor_image = boundary
    handler, responses = handler_for(assistant, mobile_only)
    handler.path = "/api/map/image?map_id=factory&floor=1" + ("&source=" + source if source is not None else "")
    desktop = threading.Thread(target=switch_desktop)
    desktop.start()
    try:
        handler.do_GET()
    finally:
        entered.set()
        desktop.join(3)
    assert not desktop.is_alive()
    assert selected["source"] == "reemr"
    assert responses == [(200, SVG)]
    assert reads == [source or "tarkov.dev"]
    assert len(resolutions) == (0 if source else 1)
    assert all(b"RE3MR-ORIGINAL" not in body for _, body in responses)


@pytest.mark.parametrize("mobile_only", [True, False])
@pytest.mark.parametrize("explicit", [True, False])
def test_mobile_reemr_is_denied_before_any_image_access(mobile_only, explicit):
    assistant = SimpleNamespace(lock=threading.RLock(), selected_profile_id=1,
                                source_for_profile=lambda profile: "reemr")
    assistant.map_floor_image = lambda *arguments: pytest.fail("Mobile must never touch the RE3MR cache")
    handler, responses = handler_for(assistant, mobile_only)
    handler.path = "/api/map/image?map_id=factory&floor=1" + ("&source=reemr" if explicit else "")
    handler.do_GET()
    assert responses[0][0] == 403


def test_desktop_personal_original_remains_available():
    assistant = SimpleNamespace(lock=threading.RLock(), selected_profile_id=1,
                                source_for_profile=lambda profile: "reemr",
                                map_floor_image=lambda *arguments: b"RE3MR-DESKTOP-ORIGINAL")
    handler, responses = handler_for(assistant, mobile_only=False, mobile_session=False)
    handler.path = "/api/map/image?map_id=factory&floor=1"
    handler.do_GET()
    assert responses == [(200, b"RE3MR-DESKTOP-ORIGINAL")]


@pytest.mark.parametrize("mobile_only", [True, False])
def test_mobile_reference_map_never_exposes_image_endpoint(mobile_only):
    assistant = SimpleNamespace(lock=threading.RLock(), selected_profile_id=1,
                                source_for_profile=lambda profile: "reemr",
                                map_view=lambda *arguments: {"reference_material": True, "image_url": "/api/map/image?source=reemr"})
    handler, responses = handler_for(assistant, mobile_only)
    handler.path = "/api/map?map_id=factory"
    handler.do_GET()
    status, body = responses[0]
    assert status == 200
    assert json.loads(body)["image_url"] == ""


@pytest.mark.parametrize("path", ["/api/maps", "/api/map"])
def test_related_map_boundaries_receive_resolved_source(path):
    resolutions, providers = [], []

    def resolve(profile):
        resolutions.append(profile)
        return "tarkov.dev"

    def view(*arguments):
        providers.append(arguments[-1])
        return {"source_provider": arguments[-1]}

    assistant = SimpleNamespace(lock=threading.RLock(), selected_profile_id=1,
                                source_for_profile=resolve, map_view=view, map_overview=view)
    handler, responses = handler_for(assistant)
    handler.path = path + "?map_id=factory&floor=1"
    handler.do_GET()
    assert responses[0][0] == 200
    assert providers == ["tarkov.dev"]
    assert resolutions == [1]


def test_nonexistent_mapdata_alias_remains_unavailable_to_mobile():
    handler, responses = handler_for(SimpleNamespace())
    handler.path = "/api/map/mapdata?source=reemr"
    handler.do_GET()
    assert responses[0][0] == 403
