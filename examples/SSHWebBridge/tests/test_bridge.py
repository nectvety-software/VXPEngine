import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sshwebbridge as app


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / "known_hosts").write_text("", encoding="utf-8")
        (root / "id_key").write_text("test-key-placeholder", encoding="utf-8")
        cls.config_path = root / "config.json"
        cls.config_path.write_text(json.dumps({
            "known_hosts": str(root / "known_hosts"),
            "targets": [{"id": "test", "label": "Test host", "host": "127.0.0.1", "username": "ops", "key_file": str(root / "id_key"), "services": ["nginx"],
                         "macros": [{"id": "lights_on", "label": "All lights ON", "kind": "mqtt", "topic": "home/lights/all", "payload": "ON"}] }],
        }), encoding="utf-8")
        cls.config = app.load_config(cls.config_path)
        cls.server = app.BridgeServer(("127.0.0.1", 0), "x" * 40, cls.config)
        cls.server.pair_code = "12345678"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.tmp.cleanup()

    def request(self, path, token=None, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = Request(self.base + path, data=data, headers=headers)
        try:
            with urlopen(req, timeout=2) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_dashboard_serves_without_auth(self):
        with urlopen(self.base + "/", timeout=2) as response:
            page = response.read().decode()
        self.assertIn("SSH WEB BRIDGE", page)
        self.assertIn("maximum-scale=1", page)

    def test_static_client_has_separate_csp_safe_assets(self):
        with urlopen(self.base + "/", timeout=2) as response:
            self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        with urlopen(self.base + "/app.js", timeout=2) as response:
            script = response.read().decode()
        self.assertIn("XMLHttpRequest", script)
        self.assertNotIn("fetch(", script)

    def test_api_requires_bearer_token(self):
        status, data = self.request("/api/targets")
        self.assertEqual(status, 401)
        self.assertIn("Authorization", data["error"])

    def test_pairing_issues_short_lived_session_token(self):
        status, data = self.request("/api/pair", payload={"code": "12345678"})
        self.assertEqual(status, 200)
        self.assertEqual(data["expires_in"], 1800)
        status, targets = self.request("/api/targets", data["token"])
        self.assertEqual(status, 200)
        self.server.sessions[data["token"]] = 0
        status, _ = self.request("/api/targets", data["token"])
        self.assertEqual(status, 401)

    def test_wrong_pair_code_is_rejected(self):
        status, data = self.request("/api/pair", payload={"code": "87654321"})
        self.assertEqual(status, 401)
        self.assertEqual(data["error"], "Pairing failed")

    def test_targets_are_returned_without_ssh_secrets(self):
        status, data = self.request("/api/targets", "x" * 40)
        self.assertEqual(status, 200)
        self.assertEqual(data["targets"][0]["id"], "test")
        self.assertNotIn("host", data["targets"][0])
        self.assertNotIn("key_file", data["targets"][0])

    def test_commands_are_fixed_and_restart_is_confirmed(self):
        target = self.config["targets"]["test"]
        self.assertEqual(app.build_command("health", None, target, None), "uptime")
        with self.assertRaises(app.BridgeError):
            app.build_command("health; rm -rf /", None, target, None)
        with self.assertRaises(app.BridgeError):
            app.build_command("restart_service", "nginx", target, None)
        self.assertEqual(app.build_command("restart_service", "nginx", target, "RESTART"), "systemctl restart -- nginx")
        with self.assertRaises(app.BridgeError):
            app.build_command("restart_service", "nginx;id", target, "RESTART")

    def test_mqtt_macro_uses_validated_topic_payload_only(self):
        target = self.config["targets"]["test"]
        self.assertEqual(app.build_command("lights_on", None, target, None), "mosquitto_pub -h localhost -t home/lights/all -m ON")
        with self.assertRaises(app.BridgeError):
            app.build_command("lights_on;id", None, target, None)

    def test_api_rejects_unknown_action_without_opening_ssh(self):
        status, data = self.request("/api/run", "x" * 40, {"target": "test", "action": "uptime; id"})
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "Unknown action")

    def test_configuration_requires_existing_host_key_database(self):
        bad = self.config_path.parent / "bad.json"
        bad.write_text(json.dumps({"known_hosts": str(self.config_path.parent / "absent_hosts"), "targets": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "known_hosts"):
            app.load_config(bad)

    def test_rate_limiter_bounds_requests(self):
        limiter = app.SlidingRateLimit()
        self.assertTrue(all(limiter.allow("peer", now=10) for _ in range(app.RATE_LIMIT)))
        self.assertFalse(limiter.allow("peer", now=10))
        self.assertTrue(limiter.allow("peer", now=10 + app.RATE_WINDOW + 1))


if __name__ == "__main__":
    unittest.main()
