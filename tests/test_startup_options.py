from http.server import BaseHTTPRequestHandler
from types import SimpleNamespace
import os
import socket

import pytest
import web_server


def test_explicit_busy_port_does_not_fall_through_to_another_service():
    first = web_server._bind_server(None, BaseHTTPRequestHandler, port=0)
    try:
        assert first.server_address[0] == "127.0.0.1"
        if os.name == "nt":
            assert first.socket.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE) == 1
        with pytest.raises(RuntimeError, match=str(first.server_port)):
            web_server._bind_server(None, BaseHTTPRequestHandler, port=first.server_port)
    finally:
        first.server_close()


@pytest.mark.parametrize("args", [["--port", "-1"], ["--port", "65536"],
                                 ["--mobile-port", "not-a-port"],
                                 ["--port", "18765", "--mobile-port", "18765"]])
def test_invalid_or_conflicting_ports_are_rejected(args):
    with pytest.raises(SystemExit) as error:
        web_server._startup_options(args)
    assert error.value.code == 2


@pytest.mark.parametrize("no_browser", [False, True])
def test_browser_option_and_explicit_ports_reach_the_real_startup_path(tmp_path, monkeypatch, no_browser):
    calls = []
    class Server:
        def __init__(self, port):
            self.server_port = port
            self.server_address = ("127.0.0.1", port)
        def serve_forever(self):
            return None
        def shutdown(self):
            pass
        def server_close(self):
            pass
    monkeypatch.setattr(web_server, "configure_logging", lambda: None)
    monkeypatch.setattr(web_server, "log_event", lambda *a, **k: None)
    monkeypatch.setattr(web_server.AssistantState, "request_catalog_refresh", lambda *_args: None)
    monkeypatch.setattr(web_server.SourceAdapters, "preload", lambda *_args, **_kwargs: calls.append(("preload_all", _kwargs.get("all_sources"))))
    monkeypatch.setattr(web_server, "_mobile_lan_info", lambda *_args: {"addresses": []})
    monkeypatch.setattr(web_server, "_make_handler", lambda *a, **k: BaseHTTPRequestHandler)
    monkeypatch.setattr(web_server, "_bind_server", lambda *a, port=None: calls.append(("desktop", port)) or Server(port))
    monkeypatch.setattr(web_server, "_bind_mobile_server", lambda *a, port=None: calls.append(("mobile", port)) or Server(port))
    monkeypatch.setattr(web_server.webbrowser, "open", lambda *a, **k: calls.append(("browser", a[0])))
    args = ["--data-dir", str(tmp_path / "isolated-root"), "--port", "18765", "--mobile-port", "18766"] + (["--no-browser"] if no_browser else [])
    assert web_server.main(args) == 0
    assert ("desktop", 18765) in calls and ("mobile", 18766) in calls
    assert ("preload_all", True) in calls
    assert any(c[0] == "browser" for c in calls) is not no_browser
