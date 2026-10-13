import json
import logging
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from web_server import PlayerStateManager, _make_handler


class LocalAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.environment = patch.dict(
            os.environ,
            {"LOCALAPPDATA": str(self.root / "windows-local-app-data")},
        )
        self.environment.start()
        self.managers = []
        self.servers = []

    def tearDown(self):
        for server, thread in reversed(self.servers):
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        for manager in self.managers:
            manager.close()
        logger = logging.getLogger("eft_task_assistant")
        for handler in list(logger.handlers):
            if str(getattr(handler, "baseFilename", "")).startswith(str(self.root)):
                handler.close()
                logger.removeHandler(handler)
        self.environment.stop()
        self.temp_dir.cleanup()

    def start_service(self, mobile_only=False):
        manager = PlayerStateManager(self.root / "app-data")
        handler = _make_handler(manager, {}, mobile_only=mobile_only)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.managers.append(manager)
        self.servers.append((server, thread))
        return manager, server

    @staticmethod
    def request(server, path, payload=None, cookie=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        request = Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            data=body,
            headers=headers,
        )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read()), response.headers
        except HTTPError as error:
            return error.code, json.loads(error.read()), error.headers

    def test_first_profile_name_prompt_survives_restart_without_login(self):
        manager, server = self.start_service()
        status, snapshot, _ = self.request(server, "/api/state")
        self.assertEqual(status, 200)
        self.assertTrue(snapshot["profile_name_required"])
        self.assertEqual(snapshot["profiles"][0]["game_mode"], "pve")

        for path in ("/api/auth/login", "/api/auth/register", "/api/auth/status"):
            if path.endswith("/status"):
                status, _, _ = self.request(server, path)
            else:
                status, _, _ = self.request(server, path, {})
            self.assertEqual(status, 404, path)

        manager.close()
        second_manager, second_server = self.start_service()
        status, snapshot, _ = self.request(second_server, "/api/state")
        self.assertEqual(status, 200)
        self.assertTrue(snapshot["profile_name_required"])

        status, result, _ = self.request(
            second_server,
            "/api/profiles/name",
            {"name": "本机存档"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["profile"]["name"], "本机存档")
        status, snapshot, _ = self.request(second_server, "/api/state")
        self.assertEqual(status, 200)
        self.assertFalse(snapshot["profile_name_required"])
        self.assertEqual(snapshot["profiles"][0]["name"], "本机存档")

    def test_phone_listener_allows_pairing_and_reads_but_cannot_write(self):
        manager, server = self.start_service(mobile_only=True)
        status, _, _ = self.request(server, "/api/state")
        self.assertEqual(status, 403)
        status, _, _ = self.request(server, "/api/mobile/state")
        self.assertEqual(status, 401)

        token, _ = manager.auth.create_mobile_pairing_token(manager.local_player.id)
        status, _, headers = self.request(
            server,
            "/api/auth/mobile-pair",
            {"token": token},
        )
        self.assertEqual(status, 200)
        cookie = headers.get("Set-Cookie").split(";", 1)[0]

        status, snapshot, _ = self.request(server, "/api/mobile/state", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(len(snapshot["profiles"]), 1)
        self.assertIn("tasks", snapshot)

        status, _, _ = self.request(
            server,
            "/api/tasks",
            {"title": "不应被手机创建"},
            cookie=cookie,
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
