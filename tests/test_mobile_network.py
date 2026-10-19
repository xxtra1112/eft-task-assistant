import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

from network_candidates import rank_network_candidates
from web_server import AssistantState, PlayerStateManager, _make_handler


@pytest.fixture
def network_server(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "data"))
    monkeypatch.setattr("web_server.log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(AssistantState, "request_catalog_refresh", lambda self: None)
    ranked = rank_network_candidates([
        {"interface_name": "Wi-Fi", "interface_type": "wifi", "addresses": ["192.168.123.13"], "is_up": True, "has_gateway": True},
        {"interface_name": "VPN", "interface_type": "vpn", "addresses": ["172.20.1.1"], "is_up": True},
    ])
    network = {**ranked, "addresses": [entry["address"] for entry in ranked["candidates"]],
               "lan_enabled": True, "port": 19886, "pairing_lifetime_seconds": 120}
    manager = PlayerStateManager(tmp_path / "isolated-app")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(manager, network))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield manager, server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    manager.close()


def request(server, path, payload=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request("POST" if payload is not None else "GET", path,
                           json.dumps(payload) if payload is not None else None,
                           {"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_network_recommendation_and_explicit_choice_persist_but_auto_choice_does_not(network_server):
    manager, server = network_server
    status, info = request(server, "/api/mobile/info")
    assert status == 200
    assert info["preferred_address"] == "192.168.123.13"
    assert "Wi-Fi" in info["candidates"][0]["display_name"]
    assert request(server, "/api/mobile/pairing", {"address": "172.20.1.1"})[0] == 201
    assert request(server, "/api/mobile/info")[1]["preferred_address"] == "192.168.123.13"
    status, pairing = request(server, "/api/mobile/pairing", {"address": "172.20.1.1", "remember_selection": True})
    assert status == 201
    assert pairing["url"].startswith("http://172.20.1.1:19886/mobile#pair=")
    info = request(server, "/api/mobile/info")[1]
    assert info["preferred_address"] == "172.20.1.1"
    assert info["saved_address_valid"]
    assistant = manager.state_for(manager.local_player)
    assert assistant.store.get_app_setting(f"mobile_pairing_address:{assistant.selected_profile_id}") == "172.20.1.1"


def test_invalid_or_expired_saved_network_does_not_redirect_pairing(network_server):
    manager, server = network_server
    assistant = manager.state_for(manager.local_player)
    assistant.store.set_app_setting(f"mobile_pairing_address:{assistant.selected_profile_id}", "10.99.99.99")
    assert request(server, "/api/mobile/info")[1]["preferred_address"] == "192.168.123.13"
    for address in ("10.99.99.99", "8.8.8.8", "127.0.0.1", "169.254.1.1", "192.168.123.13/path"):
        assert request(server, "/api/mobile/pairing", {"address": address, "remember_selection": True})[0] in {400, 403}
