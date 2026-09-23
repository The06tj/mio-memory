"""Exercise the packaged CLI against disposable, fictional notes only."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import unittest

from mcp import Client
from mio_memory.runtime import write_json


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mio-cli-test-")
        self.root = Path(self.temporary.name)
        self.vault = self.root / "fictional vault"
        self.vault.mkdir()
        self.note = self.vault / "Fiction.md"
        self.note.write_text("# Fictional test only\n\n## Study\nRiver studies the cobalt lantern.\n", encoding="utf-8")
        self.before = hashlib.sha256(self.note.read_bytes()).hexdigest()
        self.state = self.root / "private state"
        self.command("init", "--vault", str(self.vault), "--vault-name", "Fiction only", "--scope", "vault_markdown")

    def tearDown(self):
        try:
            self.command("stop")
            self.assertEqual(self.before, hashlib.sha256(self.note.read_bytes()).hexdigest())
        finally:
            self.temporary.cleanup()

    def command(self, name, *args, ok=True):
        result = subprocess.run([sys.executable, "-m", "mio_memory.cli", name,
                                 "--state-dir", str(self.state), *args],
                                capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stdout)
        self.assertEqual(data["ok"], ok)
        return data

    def test_locked_continuous_restart_and_orphan_cleanup(self):
        started = self.command("start", "--port", "0")
        self.assertTrue(started["local_service"])
        self.assertFalse(started["degraded"])
        self.assertEqual(started["read_mode"], "locked")

        async def locked():
            async with Client(f"http://127.0.0.1:{started['port']}/mcp") as client:
                tools = (await client.list_tools()).tools
                self.assertEqual({tool.name for tool in tools}, {"search", "fetch"})
                self.assertTrue(all(tool.annotations.read_only_hint for tool in tools))
                result = await client.call_tool("search", {"query": "cobalt"})
                self.assertTrue(result.is_error)
                self.assertIn("READS_LOCKED", str(result.content))
        asyncio.run(locked())

        unchanged = self.command("start", "--port", "0", "--continuous-read")
        self.assertTrue(unchanged["already_running"])
        self.assertEqual(unchanged["read_mode"], "locked")
        self.command("stop")
        self.assert_port_closed(started["port"])
        continuous = self.command("start", "--port", "0", "--continuous-read")
        self.assertEqual(continuous["read_mode"], "continuous")

        async def opened():
            async with Client(f"http://127.0.0.1:{continuous['port']}/mcp") as client:
                found = await client.call_tool("search", {"query": "cobalt"})
                self.assertFalse(found.is_error)
                hit = found.structured_content["results"][0]
                fetched = await client.call_tool("fetch", {"id": hit["id"]})
                self.assertFalse(fetched.is_error)
                self.assertIn("cobalt lantern", fetched.structured_content["text"])
        asyncio.run(opened())

        state = json.loads((self.state / "state.json").read_text())
        os.kill(state["supervisor"]["pid"], signal.SIGKILL)
        orphan = self.command("status")
        self.assertFalse(orphan["running"])
        self.assertTrue(orphan["degraded"])
        self.assertTrue(orphan["local_service"])
        self.assertNotEqual(orphan["read_mode"], "stopped")
        self.command("stop")
        self.assert_port_closed(continuous["port"])

    def test_private_setup_and_invalid_arguments(self):
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        config = self.state / "config.json"
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        original = config.read_bytes()
        self.command("init", "--vault", str(self.vault), "--vault-name", "No overwrite",
                     "--scope", "vault_markdown", ok=False)
        self.assertEqual(config.read_bytes(), original)
        self.command("start", "--port", "0", "--continuous-read", "--open-seconds", "60", ok=False)
        self.command("start", "--port", "0", "--tunnel-id", "tunnel_EXAMPLE_ONLY", ok=False)
        fake_key = "sk-" + "FAKE_FOR_TEST_ONLY" * 2
        error = self.command("start", "--api-key", fake_key, ok=False)
        self.assertNotIn(fake_key, json.dumps(error))
        self.assertFalse(self.command("status")["running"])
        self.assertFalse(self.command("inspect")["notes_read"])
        self.assertTrue(self.command("doctor")["checks"]["configuration_valid"])

    def test_private_state_cannot_live_in_source_vault(self):
        intended = self.state
        self.state = self.vault / "runtime"
        try:
            self.command("init", "--vault", str(self.vault), "--vault-name", "Fiction only",
                         "--scope", "vault_markdown", ok=False)
            self.assertFalse(self.state.exists())
        finally:
            self.state = intended

    def test_stop_does_not_claim_success_or_close_unknown_listener(self):
        with socket.socket() as unrelated:
            unrelated.bind(("127.0.0.1", 0))
            unrelated.listen()
            port = unrelated.getsockname()[1]
            write_json(self.state / "state.json", {"port": port, "mode": "continuous"})
            result = self.command("stop", ok=False)
            self.assertFalse(result["stopped"])
            self.assertTrue(result["unmanaged_listener"])
            self.assertTrue((self.state / "state.json").exists())
            self.assertEqual(unrelated.getsockname()[1], port)
            status = self.command("status")
            self.assertEqual(status["read_mode"], "unknown")
            self.assertTrue(status["degraded"])

    def assert_port_closed(self, port):
        with self.assertRaises(OSError):
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                pass


if __name__ == "__main__":
    unittest.main()
