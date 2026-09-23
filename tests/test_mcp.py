"""Contract checks through the real MCP client, using synthetic data only."""
import json
import unittest
from pathlib import Path

from mcp import Client
from mio_memory.retrieval import VaultReader
from mio_memory.server import create_server

DEMO = Path(__file__).resolve().parents[1] / "examples/demo.json"


class MCPContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_schema_annotations_and_full_search_fetch(self):
        reader = VaultReader(DEMO, 60)
        try:
            async with Client(create_server(reader)) as client:
                listed = await client.list_tools()
                self.assertEqual({t.name for t in listed.tools}, {"search", "fetch"})
                for tool in listed.tools:
                    self.assertTrue(tool.annotations.read_only_hint)
                    self.assertFalse(tool.annotations.destructive_hint)
                    self.assertFalse(tool.annotations.open_world_hint)
                    self.assertTrue(tool.output_schema)
                result = await client.call_tool("search", {"query": "纸船"})
                self.assertFalse(result.is_error)
                self.assertEqual(json.loads(result.content[0].text), result.structured_content)
                self.assertEqual(len(result.structured_content["results"]), 1)
                hit = result.structured_content["results"][0]
                fetched = await client.call_tool("fetch", {"id": hit["id"]})
                self.assertFalse(fetched.is_error)
                self.assertEqual(json.loads(fetched.content[0].text), fetched.structured_content)
                self.assertIn("小禾：「", fetched.structured_content["text"])
                self.assertIn("同伴：「", fetched.structured_content["text"])
                self.assertNotIn("密码文件", fetched.structured_content["text"])
                self.assertNotIn(str(reader.root), json.dumps(fetched.structured_content))
                invalid = await client.call_tool("fetch", {"id": "../../secret.md"})
                self.assertTrue(invalid.is_error)
                missing = await client.call_tool("search", {})
                self.assertTrue(missing.is_error)
        finally:
            reader.close()

    async def test_locked_tools_return_errors_but_discovery_works(self):
        reader = VaultReader(DEMO)
        try:
            async with Client(create_server(reader)) as client:
                self.assertEqual(len((await client.list_tools()).tools), 2)
                for name, arguments in [("search", {"query": "Python"}), ("fetch", {"id": "0" * 64})]:
                    result = await client.call_tool(name, arguments)
                    self.assertTrue(result.is_error)
                    self.assertIn("READS_LOCKED", result.content[0].text)
                    self.assertNotIn("小禾", result.content[0].text)
        finally:
            reader.close()


if __name__ == "__main__":
    unittest.main()
