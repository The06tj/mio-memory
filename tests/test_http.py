"""Real loopback Streamable HTTP test, with process cleanup and no external calls."""
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
import urllib.request

from mcp import Client

BASE = Path(__file__).resolve().parents[1]


class HTTPTests(unittest.TestCase):
    def test_loopback_round_trip_and_legacy_initialization(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (BASE / "examples/demo-vault").glob("*.md")}
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, "-m", "mio_memory.server", "--config", str(BASE / "examples/demo.json"), "--port", str(port), "--open-seconds", "30"],
            cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                if process.poll() is not None:
                    self.fail("Server exited before accepting requests")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                self.fail("Server did not start")
            url = f"http://127.0.0.1:{port}/mcp"

            async def exercise():
                async with Client(url) as client:
                    self.assertEqual({x.name for x in (await client.list_tools()).tools}, {"search", "fetch"})
                    result = await client.call_tool("search", {"query": "纸船"})
                    self.assertFalse(result.is_error)
                    hit = result.structured_content["results"][0]
                    fetched = await client.call_tool("fetch", {"id": hit["id"]})
                    self.assertFalse(fetched.is_error)
                    self.assertIn("蓝色纸", fetched.structured_content["text"])
            asyncio.run(exercise())

            # The dice test used this protocol revision. Keep this separate from
            # the current SDK client's automatically negotiated revision.
            message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "local-compatibility-test", "version": "1"}}}
            request = urllib.request.Request(url, data=json.dumps(message).encode(), headers={
                "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
            with urllib.request.urlopen(request, timeout=5) as response:
                raw = response.read().decode()
            if raw.startswith("event:") or raw.startswith("data:"):
                raw = next(line[6:] for line in raw.splitlines() if line.startswith("data: "))
            result = json.loads(raw)["result"]
            self.assertEqual(result["protocolVersion"], "2025-03-26")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (BASE / "examples/demo-vault").glob("*.md")}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
