"""Synthetic fixtures only; live source observations belong in docs/reemr-usage.md."""
import io
import json
import time
from unittest.mock import patch

import pytest
from PIL import Image

import reemr_maps as maps
from catalog import CatalogError


PNG_URL = "https://www.re3mr.com/maps/Factory/synthetic-original.png"
WEBP_URL = "https://reemr.se/maps/Factory/synthetic-basement.webp"
LICENSE = '<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode">CC BY-NC-SA 4.0</a>'
HOME = f'<a href="/Factory/">FACTORY</a><a href="/customs/">CUSTOMS</a><footer>{LICENSE}</footer>'


def raster(image_format="PNG", size=(12, 8)):
    stream = io.BytesIO()
    Image.new("RGB", size, (43, 65, 87)).save(stream, format=image_format)
    return stream.getvalue()


def anchor(url, label, size=(12000, 8000)):
    return (f'<a href="{url}" data-lbwps-width="{size[0]}" '
            f'data-lbwps-height="{size[1]}"><b>{label}</b></a>')


PAGE = (
    '<h1>FACTORY</h1>'
    + anchor("https://www.re3mr.com/maps/Factory/synthetic-mobile.jpg", "")
    + anchor(PNG_URL, "TOP-DOWN") + anchor(PNG_URL, "Version 1.7C")
    + anchor(WEBP_URL, "BASEMENT [OLD]") + anchor(WEBP_URL, "Version 0.1")
    + anchor("https://www.re3mr.com/maps/Customs/wrong-version.png", "Version 9")
    + anchor("https://www.re3mr.com/maps/Factory/synthetic-french.png", "🇫🇷")
    + anchor("https://ads.example/advert.png", "ADVERT")
    + anchor("https://maps.reemr.se/Advertisements/advert.png", "ADVERT")
    + anchor("https://www.re3mr.com/maps/Factory/source.psd", "PSD")
    + anchor("https://www.re3mr.com/maps/Factory/source.zip", "ZIP")
    + '<script>' + anchor("https://www.re3mr.com/maps/Factory/script.png", "SCRIPT") + '</script>'
    + '<svg>' + anchor("https://www.re3mr.com/maps/Factory/vector.png", "SVG") + '</svg>'
    + '<img src="https://www.re3mr.com/maps/Factory/thumbnail.png">'
    + '<a href="https://www.re3mr.com/maps/Factory/logo.png">LOGO</a>'
    + '<a href="https://creativecommons.org/licenses/by-nc-sa/2.0/deed.en">Copyright</a>'
    + '<footer>' + LICENSE + '</footer>'
)


class FixtureHTTP:
    def __init__(self, page=PAGE):
        self.requests = []
        self.responses = {
            maps.ROOT: ("text/html", HOME.encode()),
            maps.ROOT + "Factory/": ("text/html", page.encode()),
            maps.ROOT + "customs/": ("text/html", page.encode()),
            PNG_URL: ("image/png", raster()), WEBP_URL: ("image/webp", raster("WEBP")),
        }

    def __call__(self, url, limit, accept):
        self.requests.append(url)
        if url in self.responses:
            value = self.responses[url]
            if isinstance(value, maps.FetchResponse):
                return value
            content_type, body = value
        elif url.endswith("/robots.txt"):
            content_type, body = "text/plain", b"User-agent: *\nDisallow:\n"
        else:
            pytest.fail("Unexpected fixture request: " + url)
        return maps.FetchResponse(body, content_type, url, {
            "status": 200, "fetched_at": "2026-10-19T00:00:00+00:00", "etag": '"fixture-etag"',
        })


@pytest.fixture
def provider():
    http = FixtureHTTP()
    return maps.ReemrMaps(fetcher=http), http


def test_live_html_index_handles_case_and_slashes_without_static_fallback(provider):
    client, http = provider
    entries = client.map_index()
    assert [entry["map_id"] for entry in entries] == ["factory", "customs"]
    assert {key: entries[0][key] for key in ("map_id", "name", "name_en", "source_url")} == {
        "map_id": "factory", "name": "工厂", "name_en": "Factory", "source_url": maps.ROOT + "Factory/"}
    assert http.requests[0] == maps.ROOT + "robots.txt"
    assert not any(url.endswith(".png") for url in http.requests)


def test_variants_are_real_named_links_not_guessed_floors_or_thumbnails(provider):
    client, http = provider
    config = client.map_data("factory")
    assert not config["reference_only"] and config["reference_material"]
    assert config["annotations"] == []
    assert [floor["image_url"] for floor in config["floors"]] == [PNG_URL, WEBP_URL]
    assert [floor["version"] for floor in config["floors"]] == ["Version 1.7C", "Version 0.1"]
    assert config["floors"][1]["deprecated"]
    assert config["floors"][0]["width"] is None
    assert config["floors"][0]["html_width_hint"] == 12000
    assert not config["floors"][0]["dimensions_verified"]
    assert config["unmatched_version_links"] == ["https://www.re3mr.com/maps/Customs/wrong-version.png"]
    assert len(config["license_evidence"]["page_license_urls"]) == 2
    assert not any(url.endswith((".png", ".webp")) for url in http.requests)


def test_only_selected_original_is_decoded_and_metadata_is_cache_ready(provider):
    client, http = provider
    floor = client.map_data("factory")["floors"][0]
    response = client.floor_image("factory", floor["key"])
    assert response.body == raster()
    assert response.content_type == "image/png"
    assert response.metadata["width"] == 12 and response.metadata["height"] == 8
    assert response.metadata["byte_length"] == len(response.body)
    assert response.metadata["dimensions_verified"]
    assert response.metadata["sha256"] == maps.hashlib.sha256(response.body).hexdigest()
    assert response.metadata["cache_scope"] == "local-user-only"
    assert not response.metadata["license_evidence"]["separate_author_permission"]
    assert not response.metadata["license_evidence"]["redistribution_enabled"]
    assert response.metadata["etag"] == '"fixture-etag"'
    assert WEBP_URL not in http.requests
    updated = client.map_data("factory")["floors"][0]
    assert updated["width"] == 12 and updated["dimensions_basis"] == "pillow-full-decode"
    updated["name"] = "caller changed"
    assert client.map_data("factory")["floors"][0]["name"] == "TOP-DOWN"


@pytest.mark.parametrize("location", ["https://attacker.example/maps/f.png", "http://reemr.se/maps/f.png",
                                      "https://127.0.0.1/private.png", "https://reemr.se/wp-admin/"])
def test_redirect_is_rejected_before_target_is_contacted(provider, location):
    client, http = provider
    key = client.map_data("factory")["floors"][0]["key"]
    http.responses[PNG_URL] = maps.FetchResponse(b"", "", PNG_URL, {"status": 302, "location": location})
    with pytest.raises(CatalogError):
        client.floor_image("factory", key)
    assert location not in http.requests


def test_cross_host_redirect_checks_new_origin_robots_before_image(provider):
    client, http = provider
    key = client.map_data("factory")["floors"][0]["key"]
    target = "https://reemr.se/maps/Factory/canonical.png"
    http.responses[PNG_URL] = maps.FetchResponse(b"", "", PNG_URL, {"status": 302, "location": target})
    http.responses[maps.ROOT + "robots.txt"] = ("text/plain", b"User-agent: *\nDisallow: /maps/\n")
    client._robots.clear()
    with pytest.raises(CatalogError, match="robots"):
        client.floor_image("factory", key)
    assert target not in http.requests


def test_canonical_directory_redirect_keeps_real_source_url(provider):
    client, http = provider
    canonical = maps.ROOT + "factory/"
    http.responses[maps.ROOT + "Factory/"] = maps.FetchResponse(
        b"", "", maps.ROOT + "Factory/", {"status": 301, "location": canonical})
    http.responses[canonical] = ("text/html", PAGE.encode())
    assert client.map_data("factory")["source_url"] == canonical


@pytest.mark.parametrize("robots", [
    ("text/html", b"<html>homepage</html>"),
    ("text/plain", b"<!doctype html><html>homepage</html>"),
    ("text/plain", b"User-agent: *\nDisallow: /maps/"),
])
def test_missing_or_disallowed_image_robots_never_downloads_or_sets_metadata(provider, robots):
    client, http = provider
    key = client.map_data("factory")["floors"][0]["key"]
    http.responses["https://www.re3mr.com/robots.txt"] = robots
    with pytest.raises(CatalogError, match="robots"):
        client.floor_image("factory", key)
    assert PNG_URL not in http.requests
    assert not client._metadata


def test_observed_maps_host_robots_home_redirect_is_not_an_allow_rule(provider):
    client, http = provider
    target = "https://maps.reemr.se/Customs/synthetic.png"
    http.responses[maps.ROOT + "customs/"] = ("text/html", (anchor(target, "CUSTOMS") + LICENSE).encode())
    robots_url = "https://maps.reemr.se/robots.txt"
    http.responses[robots_url] = maps.FetchResponse(b"", "", robots_url, {"status": 301, "location": maps.ROOT})
    key = client.map_data("customs")["floors"][0]["key"]
    with pytest.raises(CatalogError):
        client.floor_image("customs", key)
    assert target not in http.requests
    assert not any(url.replace("maps.reemr.se", "reemr.se") in http.requests for url in [target])


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_errors_stop_after_one_attempt(provider, status):
    client, http = provider
    key = client.map_data("factory")["floors"][0]["key"]
    http.responses[PNG_URL] = maps.FetchResponse(b"", "text/html", PNG_URL, {"status": status})
    with pytest.raises(CatalogError, match=str(status)):
        client.floor_image("factory", key)
    assert http.requests.count(PNG_URL) == 1
    assert not client._metadata


def test_fetcher_cannot_silently_follow_redirects(provider):
    client, http = provider
    key = client.map_data("factory")["floors"][0]["key"]
    http.responses[PNG_URL] = maps.FetchResponse(raster(), "image/png", "https://other.example/asset.png")
    with pytest.raises(CatalogError, match="传输层"):
        client.floor_image("factory", key)


@pytest.mark.parametrize("missing", ["site", "page", "script-only"])
def test_no_current_license_no_image_download(provider, missing):
    client, http = provider
    if missing == "site":
        http.responses[maps.ROOT] = ("text/html", b'<a href="/Factory/">FACTORY</a>')
    else:
        page = anchor(PNG_URL, "TOP-DOWN")
        if missing == "script-only":
            page += "<script>" + LICENSE + "</script>"
        http.responses[maps.ROOT + "Factory/"] = ("text/html", page.encode())
    with pytest.raises(CatalogError, match="许可|声明"):
        client.map_data("factory")
    assert PNG_URL not in http.requests


@pytest.mark.parametrize("text,url,allowed", [
    ("User-agent: *\nDisallow:\n", PNG_URL, True),
    ("User-agent: *\nAllow: /\nDisallow: /maps/", PNG_URL, False),
    ("User-agent: *\nDisallow: /maps/\nAllow: /maps/Factory/", PNG_URL, True),
    ("User-agent: *\nDisallow: /*.png$", PNG_URL, False),
    ("User-agent: *\nDisallow: /maps/%46actory/", PNG_URL, False),
    ("User-agent: *\nDisallow: /\nUser-agent: EFTTaskAssistant\nAllow: /maps/", PNG_URL, True),
    ("User-agent: *\nAllow: /maps/\nDisallow: /maps/", PNG_URL, True),
])
def test_robots_longest_path_specific_agent_and_wildcards(text, url, allowed):
    assert maps._robots_allows(text, url) == allowed


@pytest.mark.parametrize("url", [
    "http://reemr.se/maps/a.png", "https://reemr.se:443/maps/a.png",
    "https://user@reemr.se/maps/a.png", "https://reemr.se.evil/maps/a.png",
    "https://reemr.se/maps/../admin.png", "https://reemr.se/maps/%2e%2e/admin.png",
    "https://reemr.se/maps/%252e%252e/admin.png", "https://reemr.se/maps/a.png?redirect=x",
    "https://reemr.se/maps/a.png#x", "https://reemr.se/maps/a.svg",
    "https://reemr.se/maps/a.psd", "https://reemr.se/wp-content/uploads/ad.png",
    "https://maps.reemr.se/wp-content/uploads/ad.png", "https://reemr.se/maps/Advertisements/ad.png",
    "https://reemr.se/maps/a.png\n", "file:///tmp/a.png",
])
def test_strict_resource_whitelist(url):
    with pytest.raises(CatalogError):
        maps._validate_url(url, "image")


@pytest.mark.parametrize("image_format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
def test_real_pillow_decode_of_synthetic_formats(image_format, mime):
    info = maps.validate_image(raster(image_format), mime)
    assert (info["width"], info["height"], info["content_type"]) == (12, 8, mime)


@pytest.mark.parametrize("body,mime", [(b"<svg><script>bad()</script></svg>", "image/png"),
                                      (b"<html>403 denied</html>", "image/png"),
                                      (raster(), "image/jpeg"), (raster()[:32], "image/png"),
                                      (raster(), "application/octet-stream"), (b"", "image/png")])
def test_invalid_or_mime_mismatched_images(body, mime):
    with pytest.raises(CatalogError):
        maps.validate_image(body, mime)


def test_size_and_pixel_limits_are_enforced_without_large_test_allocations():
    with patch.object(maps, "MAX_IMAGE_BYTES", 2):
        with pytest.raises(CatalogError, match="50 MB"):
            maps.validate_image(raster())
    with patch.object(maps, "MAX_PIXELS", 95):
        with pytest.raises(CatalogError, match="160 MP"):
            maps.validate_image(raster())
    assert maps.MAX_PIXELS <= 200_000_000 and maps.MAX_IMAGE_BYTES <= 50_000_000


def test_animated_images_are_rejected():
    stream = io.BytesIO()
    Image.new("RGB", (12, 8), "red").save(stream, format="WEBP", save_all=True,
                                        append_images=[Image.new("RGB", (12, 8), "blue")], duration=100)
    with pytest.raises(CatalogError, match="静态"):
        maps.validate_image(stream.getvalue(), "image/webp")


def test_bad_image_never_populates_validated_metadata(provider):
    client, http = provider
    key = client.map_data("factory")["floors"][0]["key"]
    http.responses[PNG_URL] = ("image/png", b"not an image")
    with pytest.raises(CatalogError):
        client.floor_image("factory", key)
    assert not client._metadata


def test_changed_page_does_not_reuse_dimensions_from_an_older_image_version(provider):
    client, http = provider
    key = client.map_data("factory")["floors"][0]["key"]
    client.floor_image("factory", key)
    http.responses[maps.ROOT + "Factory/"] = ("text/html", PAGE.replace("Version 1.7C", "Version 1.8").encode())
    client._documents.pop(maps.ROOT + "Factory/")
    floor = client.map_data("factory")["floors"][0]
    assert floor["version"] == "Version 1.8"
    assert floor["width"] is None and not floor["dimensions_verified"]


def test_local_import_can_be_indexed_viewed_and_decoded_without_any_network(tmp_path):
    def no_network(*args):
        pytest.fail("Local import must not access the network")
    client = maps.ReemrMaps(fetcher=no_network)
    path = tmp_path / "selected.png"
    path.write_bytes(raster())
    floor = client.import_image("factory", path, name="My local map", rights_confirmed=True,
                                license_evidence="User-supplied permission/source evidence")
    assert client.map_index(local_only=True)[0]["map_id"] == "factory"
    config = client.map_data("factory")
    assert config["floors"][0]["width"] == 12 and config["annotations"] == []
    assert not config["reference_only"]
    assert str(path) not in str(config)
    response = client.floor_image("factory", floor["key"])
    assert response.body == raster() and response.metadata["license_evidence"]["user_rights_confirmed"]
    assert list(tmp_path.iterdir()) == [path]
    path.write_bytes(raster(size=(13, 8)))
    with pytest.raises(CatalogError, match="改变"):
        client.floor_image("factory", floor["key"])


@pytest.mark.parametrize("confirmed,evidence", [(False, "some evidence"), (True, ""), (True, "  ")])
def test_import_requires_explicit_rights_and_source_evidence(tmp_path, confirmed, evidence):
    client = maps.ReemrMaps()
    with pytest.raises(CatalogError, match="确认"):
        client.import_image("factory", tmp_path / "missing.png", name="map", rights_confirmed=confirmed,
                            license_evidence=evidence)


def test_public_hosting_mode_and_invalid_floor_are_not_enabled(provider):
    with pytest.raises(CatalogError, match="再托管"):
        maps.ReemrMaps(usage="public-hosting")
    client, http = provider
    with pytest.raises(CatalogError):
        client.map_data("../factory")
    with pytest.raises(CatalogError):
        client.floor_image("factory", "invented-floor")
    assert PNG_URL not in http.requests


def test_transport_rejects_content_length_before_reading():
    class Headers:
        def get(self, key, default=None):
            return "50000001" if key == "Content-Length" else default
    class Response:
        headers = Headers()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, length):
            pytest.fail("Oversized response body must not be read")
    class Opener:
        def open(self, *args, **kwargs):
            return Response()
    with patch.object(maps, "build_opener", return_value=Opener()):
        with pytest.raises(CatalogError, match="长度"):
            maps._transport(PNG_URL, maps.MAX_IMAGE_BYTES, "image/png")


def test_stream_limit_without_content_length():
    class Headers:
        def get(self, key, default=None):
            return default
    class Response:
        headers = Headers()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, length):
            assert length == 9
            return b"x" * 9
    class Opener:
        def open(self, *args, **kwargs):
            return Response()
    with patch.object(maps, "build_opener", return_value=Opener()):
        with pytest.raises(CatalogError, match="大小"):
            maps._transport(PNG_URL, 8, "image/png")


def test_directory_json_survives_restart_and_offline_expiry_with_versions_and_failure(tmp_path):
    http = FixtureHTTP()
    client = maps.ReemrMaps(cache_root=tmp_path, fetcher=http)
    config = client.map_data("factory")
    assert client.cache_path.is_file()
    state = json.loads(client.cache_path.read_text(encoding="utf-8"))
    assert state["source_provider"] == "reemr"
    assert state["directories"]["map:factory"]["payload"]["floors"][0]["version"] == "Version 1.7C"
    assert state["documents"][maps.ROOT]["sha256"]
    assert state["robots"][maps.ROOT.rstrip("/")]["state"] == "valid"
    attempted = []
    def offline(url, *args):
        attempted.append(url)
        raise maps.ReemrNetworkError("fixture network unavailable")
    future = time.time() + maps.DOCUMENT_TTL + 5
    with patch.object(maps.time, "time", return_value=future):
        restarted = maps.ReemrMaps(cache_root=tmp_path, fetcher=offline)
        cached = restarted.map_data("factory")
        assert cached["floors"][0]["key"] == config["floors"][0]["key"]
        assert cached["floors"][0]["version"] == "Version 1.7C"
        assert cached["cache_status"]["stale"]
        assert cached["license_evidence"]["source_page_sha256"] == config["license_evidence"]["source_page_sha256"]
        assert restarted.map_index()[0]["cache_status"]["state"] == "offline"
        with pytest.raises(maps.ReemrPolicyError):
            restarted.check_floor_access("factory", cached["floors"][0]["key"])
    saved = json.loads(client.cache_path.read_text(encoding="utf-8"))
    assert saved["operations"]["document:" + maps.ROOT]["state"] == "failed"
    assert "unavailable" in saved["operations"]["document:" + maps.ROOT]["last_failure"]["message"]
    assert saved["directories"]["map:factory"]["payload"]["cache_status"]["stale"]
    assert not any(url.endswith((".png", ".webp")) for url in attempted)


def test_blocked_seven_domain_stays_blocked_after_restart_without_retry_or_cache_bypass(tmp_path):
    http = FixtureHTTP()
    target = "https://maps.reemr.se/Customs/synthetic.png"
    http.responses[maps.ROOT + "customs/"] = ("text/html", (anchor(target, "CUSTOMS") + LICENSE).encode())
    robots_url = "https://maps.reemr.se/robots.txt"
    http.responses[robots_url] = maps.FetchResponse(b"", "", robots_url, {"status": 301, "location": maps.ROOT})
    client = maps.ReemrMaps(cache_root=tmp_path, fetcher=http)
    floor = client.map_data("customs")["floors"][0]
    with pytest.raises(maps.ReemrPolicyError):
        client.floor_image("customs", floor["key"])
    assert target not in http.requests
    state = json.loads(client.cache_path.read_text(encoding="utf-8"))
    assert state["robots"]["https://maps.reemr.se"]["state"] == "blocked"
    assert state["operations"]["image:" + target]["last_failure"]
    requests = []
    def no_network(url, *args):
        requests.append(url)
        pytest.fail("Persisted denial must not retry requests inside its TTL")
    restarted = maps.ReemrMaps(cache_root=tmp_path, fetcher=no_network)
    config = restarted.map_data("customs")
    assert config["floors"][0]["robots"]["state"] == "blocked"
    cache_read = []
    with pytest.raises(maps.ReemrPolicyError):
        restarted.check_floor_access("customs", floor["key"])
        cache_read.append(b"previously cached bytes must not be used")
    assert not cache_read and not requests


def test_new_robots_disallow_replaces_previous_allow_on_disk(tmp_path):
    http = FixtureHTTP()
    client = maps.ReemrMaps(cache_root=tmp_path, fetcher=http)
    key = client.map_data("factory")["floors"][0]["key"]
    client.floor_image("factory", key)
    origin = "https://www.re3mr.com"
    http.responses[origin + "/robots.txt"] = ("text/plain", b"User-agent: *\nDisallow: /maps/\n")
    client._robots.pop(origin)
    with pytest.raises(maps.ReemrPolicyError):
        client.check_floor_access("factory", key)
    restarted = maps.ReemrMaps(cache_root=tmp_path, fetcher=http)
    before = list(http.requests)
    with pytest.raises(maps.ReemrPolicyError):
        restarted.check_floor_access("factory", key)
    assert http.requests == before
    state = json.loads(client.cache_path.read_text(encoding="utf-8"))
    assert "/maps/" in state["robots"][origin]["text"]
    assert state["operations"]["robots-resource:" + PNG_URL]["state"] == "failed"
    assert state["directories"]["image:" + PNG_URL]["payload"]["width"] == 12
    assert list(tmp_path.rglob("*.png")) == []


def test_image_failure_status_and_success_metadata_are_persisted_without_image_bytes(tmp_path):
    http = FixtureHTTP()
    client = maps.ReemrMaps(cache_root=tmp_path, fetcher=http)
    key = client.map_data("factory")["floors"][0]["key"]
    http.responses[PNG_URL] = maps.FetchResponse(b"", "", PNG_URL, {"status": 403})
    with pytest.raises(CatalogError, match="403"):
        client.floor_image("factory", key)
    state = json.loads(client.cache_path.read_text(encoding="utf-8"))
    operation = state["operations"]["image:" + PNG_URL]
    assert operation["last_failure"]["http_status"] == 403
    assert "image:" + PNG_URL not in state["directories"]
    with pytest.raises(maps.ReemrPolicyError, match="401/403"):
        client.check_floor_access("factory", key)
    http.responses[PNG_URL] = ("image/png", raster())
    response = client.floor_image("factory", key)
    state = json.loads(client.cache_path.read_text(encoding="utf-8"))
    assert state["operations"]["image:" + PNG_URL]["state"] == "ok"
    assert state["operations"]["image:" + PNG_URL]["last_failure"]["http_status"] == 403
    assert state["directories"]["image:" + PNG_URL]["payload"]["sha256"] == response.metadata["sha256"]
    assert response.metadata["robots"]["state"] == "allowed"
    assert not list(tmp_path.rglob("*.png"))


@pytest.mark.parametrize("corruption", ["other-provider", "bad-sha", "invalid-json"])
def test_invalid_or_cross_provider_disk_directory_cannot_be_used_offline(tmp_path, corruption):
    http = FixtureHTTP()
    client = maps.ReemrMaps(cache_root=tmp_path, fetcher=http)
    client.map_data("factory")
    state = json.loads(client.cache_path.read_text(encoding="utf-8"))
    if corruption == "other-provider":
        state["source_provider"] = "other-source"
    elif corruption == "bad-sha":
        state["documents"][maps.ROOT]["sha256"] = "0" * 64
    client.cache_path.write_text("{" if corruption == "invalid-json" else json.dumps(state), encoding="utf-8")
    def offline(*args):
        raise CatalogError("offline")
    restarted = maps.ReemrMaps(cache_root=tmp_path, fetcher=offline)
    with pytest.raises(CatalogError):
        restarted.map_data("factory")


def test_atomic_failed_write_preserves_previous_json_and_removes_temporary(tmp_path):
    client = maps.ReemrMaps(cache_root=tmp_path, fetcher=FixtureHTTP())
    client.map_data("factory")
    original = client.cache_path.read_bytes()
    with patch.object(type(client.cache_path), "replace", side_effect=OSError("fixture interrupted write")):
        with pytest.raises(CatalogError, match="写入"):
            client._operation("fixture", CatalogError("failed"))
    assert client.cache_path.read_bytes() == original
    assert not list(client.cache_path.parent.glob("*.tmp"))


def test_local_import_permission_and_identity_survive_restart_without_network(tmp_path):
    path = tmp_path / "selected.png"
    path.write_bytes(raster())
    def no_network(*args):
        pytest.fail("Local imports cannot access network")
    cache_root = tmp_path / "isolated-cache"
    client = maps.ReemrMaps(cache_root=cache_root, fetcher=no_network)
    floor = client.import_image("factory", path, name="Lawful selection", rights_confirmed=True,
                                license_evidence="User's personal use evidence; no publishing grant")
    restarted = maps.ReemrMaps(cache_root=cache_root, fetcher=no_network)
    config = restarted.map_data("factory")
    assert str(path) not in str(config)
    assert config["floors"][0]["license_evidence"]["user_rights_confirmed"]
    assert config["floors"][0]["license_evidence"]["confirmed_at"]
    assert config["map_license_url"] == ""
    assert restarted.check_floor_access("factory", floor["key"])["local_import"]
    assert restarted.floor_image("factory", floor["key"]).body == raster()
    state = json.loads(restarted.cache_path.read_text(encoding="utf-8"))
    state["imports"]["factory"][floor["key"]]["license_evidence"]["user_rights_confirmed"] = False
    restarted.cache_path.write_text(json.dumps(state), encoding="utf-8")
    denied = maps.ReemrMaps(cache_root=cache_root, fetcher=no_network)
    assert denied.map_index(local_only=True) == []


def test_fetch_response_wires_into_real_asset_cache_and_denial_blocks_a_hot_cache(tmp_path):
    from asset_cache import DiskAssetCache, FetchResult, make_asset_key

    http = FixtureHTTP()
    client = maps.ReemrMaps(cache_root=tmp_path / "directories", fetcher=http)
    floor = client.map_data("factory")["floors"][0]
    key = make_asset_key("reemr", "reference", "factory", floor["key"], floor["version"])
    cache = DiskAssetCache(tmp_path / "images", workers=1, retries=0, fetch_timeout=5,
                           max_asset_bytes=maps.MAX_IMAGE_BYTES, max_pixels=maps.MAX_PIXELS)
    def fetch_selected(**validators):
        response = client.floor_image("factory", floor["key"])
        return FetchResult(data=response.body, content_type=response.content_type,
                           etag=response.metadata.get("etag"),
                           last_modified=response.metadata.get("last_modified"))
    def read_selected():
        client.check_floor_access("factory", floor["key"])
        return cache.get_or_fetch(key, fetch_selected)
    try:
        assert read_selected() == raster()
        assert read_selected() == raster()
        assert http.requests.count(PNG_URL) == 1
        origin = "https://www.re3mr.com"
        http.responses[origin + "/robots.txt"] = ("text/plain", b"User-agent: *\nDisallow: /maps/\n")
        client._robots.pop(origin)
        with pytest.raises(maps.ReemrPolicyError):
            read_selected()
        assert http.requests.count(PNG_URL) == 1
    finally:
        cache.close()
