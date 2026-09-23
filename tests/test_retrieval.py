"""Boundary checks using isolated, synthetic notes only.

Run: python -m unittest -v test_retrieval
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mio_memory.retrieval import RetrievalError, VaultReader


class RetrievalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mio-memory-synthetic-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "allowed"
        self.root.mkdir()
        self.config = self.base / "config.json"
        self.now = 1000.0
        self.clock = patch("mio_memory.retrieval.time.monotonic", side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def write(self, relative, body):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return target

    def reader(self, files=("note.md",), seconds=60, root=None):
        self.config.write_text(json.dumps({
            "root": str(root or self.root),
            "vault_name": "Synthetic Test Vault",
            "files": list(files),
        }), encoding="utf-8")
        return VaultReader(self.config, open_seconds=seconds)

    def test_default_locked_does_not_read_note(self):
        self.write("note.md", "# Demo\n\n## One\nSYNTHETIC_PRIVATE_TEXT\n")
        reader = self.reader(seconds=0)
        with patch.object(reader, "_read", wraps=reader._read) as read:
            with self.assertRaisesRegex(RetrievalError, "READS_LOCKED"):
                reader.search("PRIVATE")
            with self.assertRaisesRegex(RetrievalError, "READS_LOCKED"):
                reader.fetch("a" * 64)
            read.assert_not_called()

    def test_expiry_revokes_previously_issued_id(self):
        self.write("note.md", "# Demo\n\n## One\nSynthetic sapphire\n")
        reader = self.reader()
        identifier = reader.search("sapphire")["results"][0]["id"]
        self.now += 60
        with self.assertRaisesRegex(RetrievalError, "READS_LOCKED"):
            reader.fetch(identifier)
        self.assertEqual(reader.issued, {})

    def test_expiry_during_read_does_not_return_content(self):
        self.write("note.md", "# Demo\n\n## One\nSynthetic sapphire\n")
        reader = self.reader()
        original = reader._read

        def expire_after_read(relative):
            body = original(relative)
            self.now += 61
            return body

        with patch.object(reader, "_read", side_effect=expire_after_read):
            with self.assertRaisesRegex(RetrievalError, "READS_LOCKED"):
                reader.search("sapphire")
        self.assertEqual(reader.issued, {})

    def test_search_is_metadata_only_and_fetch_is_one_section(self):
        self.write("note.md", "# Demo\n\n## First\nSAPPHIRE_BODY_ONLY\n\n## Second\nOTHER_SECTION_SECRET\n")
        reader = self.reader()
        result = reader.search("SAPPHIRE_BODY_ONLY")
        encoded = json.dumps(result)
        self.assertNotIn("SAPPHIRE_BODY_ONLY", encoded)
        self.assertNotIn("OTHER_SECTION_SECRET", encoded)
        self.assertNotIn(str(self.base), encoded)
        item = reader.fetch(result["results"][0]["id"])
        self.assertIn("SAPPHIRE_BODY_ONLY", item["text"])
        self.assertNotIn("OTHER_SECTION_SECRET", json.dumps(item))
        self.assertNotIn(str(self.base), json.dumps(item))

    def test_only_explicitly_allowlisted_files_are_read(self):
        self.write("note.md", "# Demo\n## First\nALLOWED_ONLY\n")
        self.write("unlisted.md", "# Unlisted\n## Hidden\nUNLISTED_SECRET\n")
        reader = self.reader()
        with patch.object(reader, "_read", wraps=reader._read) as read:
            self.assertEqual(reader.search("UNLISTED_SECRET"), {"results": []})
            self.assertEqual([c.args[0] for c in read.call_args_list], ["note.md"])
        with self.assertRaisesRegex(RetrievalError, "allowlisted"):
            reader._read("unlisted.md")

    def test_fetch_rejects_paths_and_ids_from_another_instance(self):
        self.write("note.md", "# Demo\n## One\nSynthetic sapphire\n")
        first = self.reader()
        identifier = first.search("sapphire")["results"][0]["id"]
        second = self.reader()
        for value in ("note.md", "../note.md", str(self.root / "note.md"), identifier):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RetrievalError, "Search first"):
                    second.fetch(value)

    def test_next_successful_search_revokes_previous_results(self):
        self.write("note.md", "# Demo\n## First\nSAPPHIRE\n## Second\nTOPAZ\n")
        reader = self.reader()
        identifier = reader.search("SAPPHIRE")["results"][0]["id"]
        reader.search("TOPAZ")
        with self.assertRaisesRegex(RetrievalError, "Search first"):
            reader.fetch(identifier)

    def test_empty_result_search_revokes_previous_results(self):
        self.write("note.md", "# Demo\n## First\nSAPPHIRE\n")
        reader = self.reader()
        identifier = reader.search("SAPPHIRE")["results"][0]["id"]
        self.assertEqual(reader.search("ABSENT_TERM"), {"results": []})
        with self.assertRaisesRegex(RetrievalError, "Search first"):
            reader.fetch(identifier)

    def test_result_limit_and_chinese_literal_and_search(self):
        self.write("note.md", "# Demo\n" + "".join(
            f"## 项目 {i}\n虚构的蓝色转椅，第 {i} 条\n" for i in range(9)))
        reader = self.reader()
        self.assertEqual(len(reader.search("蓝色 转椅")["results"]), 5)
        self.assertEqual(reader.search("蓝色 红色"), {"results": []})

    def test_source_body_change_requires_search_again(self):
        target = self.write("note.md", "# Demo\n## First\nSAPPHIRE old\n")
        reader = self.reader()
        identifier = reader.search("SAPPHIRE")["results"][0]["id"]
        target.write_text("# Demo\n## First\nSAPPHIRE new\n", encoding="utf-8")
        with self.assertRaisesRegex(RetrievalError, "Source changed"):
            reader.fetch(identifier)
        self.assertNotIn(identifier, reader.issued)

    def test_source_frontmatter_change_requires_search_again(self):
        target = self.write("note.md", "---\nstatus: active\n---\n# Demo\n## First\nSAPPHIRE\n")
        reader = self.reader()
        identifier = reader.search("SAPPHIRE")["results"][0]["id"]
        target.write_text(target.read_text().replace("active", "superseded"), encoding="utf-8")
        with self.assertRaisesRegex(RetrievalError, "Source changed"):
            reader.fetch(identifier)

    def test_source_title_change_requires_search_again(self):
        target = self.write("note.md", "# Original provenance\n## First\nSAPPHIRE\n")
        reader = self.reader()
        identifier = reader.search("SAPPHIRE")["results"][0]["id"]
        target.write_text("# Changed provenance\n## First\nSAPPHIRE\n", encoding="utf-8")
        with self.assertRaisesRegex(RetrievalError, "Source changed"):
            reader.fetch(identifier)

    def test_rejects_traversal_absolute_hidden_and_reserved_paths(self):
        names = ["../outside.md", "/tmp/outside.md", "a/../../outside.md", "a//b.md",
                 "./note.md", ".secret.md", "a/.hidden.md", "a\\b.md", "a\0b.md",
                 "a.txt"]
        for name in names:
            with self.subTest(name=name):
                with self.assertRaises(RetrievalError):
                    self.reader(files=[name])

    def test_explicit_system_archive_and_attachment_markdown_scope(self):
        for name in ("00_System/a.md", "90_Archive/a.md", "Attachments/a.md"):
            with self.subTest(name=name):
                self.write(name, "# Synthetic\n## Entry\nSAPPHIRE\n")
                reader = self.reader(files=[name])
                hit = reader.search("SAPPHIRE")["results"][0]
                self.assertEqual(reader.fetch(hit["id"])["metadata"]["relative_path"], name)
                reader.close()

    def test_file_symlink_is_rejected_without_leaking_target(self):
        outside = self.base / "outside.md"
        outside.write_text("OUTSIDE_SYNTHETIC_SECRET", encoding="utf-8")
        (self.root / "note.md").symlink_to(outside)
        reader = self.reader()
        with self.assertRaises(RetrievalError) as error:
            reader.search("SECRET")
        self.assertNotIn(str(self.base), str(error.exception))
        self.assertNotIn("OUTSIDE_SYNTHETIC_SECRET", str(error.exception))

    def test_allowlisted_parent_symlink_is_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "note.md").write_text("OUTSIDE_SYNTHETIC_SECRET", encoding="utf-8")
        (self.root / "sub").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(RetrievalError):
            self.reader(files=["sub/note.md"]).search("SECRET")

    def test_root_ancestor_replaced_by_symlink_does_not_escape_original_root(self):
        parent = self.base / "parent"
        original_root = parent / "vault"
        original_root.mkdir(parents=True)
        (original_root / "note.md").write_text("# Original\n## One\nHARMLESS\n", encoding="utf-8")
        reader = self.reader(root=original_root)
        outside_parent = self.base / "outside-parent"
        (outside_parent / "vault").mkdir(parents=True)
        (outside_parent / "vault" / "note.md").write_text(
            "# Outside\n## One\nOUTSIDE_SYNTHETIC_SECRET\n", encoding="utf-8")
        parent.rename(self.base / "original-parent")
        parent.symlink_to(outside_parent, target_is_directory=True)
        try:
            result = reader.search("OUTSIDE_SYNTHETIC_SECRET")
        except RetrievalError:
            return  # Failing closed is also safe.
        self.assertEqual(result, {"results": []})

    def test_hardlink_fifo_and_directory_are_rejected(self):
        outside = self.base / "outside.md"
        outside.write_text("OUTSIDE_SYNTHETIC_SECRET", encoding="utf-8")
        target = self.root / "note.md"
        os.link(outside, target)
        with self.assertRaises(RetrievalError):
            self.reader().search("SECRET")
        target.unlink()
        os.mkfifo(target)
        with self.assertRaises(RetrievalError):
            self.reader().search("SECRET")
        target.unlink()
        target.mkdir()
        with self.assertRaises(RetrievalError):
            self.reader().search("SECRET")

    def test_invalid_utf8_and_oversize_file_fail_without_echoing_bytes(self):
        target = self.root / "note.md"
        target.write_bytes(b"SYNTHETIC_SECRET\xff")
        with self.assertRaises(RetrievalError) as error:
            self.reader().search("SECRET")
        self.assertNotIn("SYNTHETIC_SECRET", str(error.exception))
        target.write_bytes(b"x" * (VaultReader.MAX_BYTES + 1))
        with self.assertRaisesRegex(RetrievalError, "bounded regular"):
            self.reader().search("x")

    def test_fenced_headings_do_not_split_a_section(self):
        self.write("note.md", "# Demo\n## First\nSAPPHIRE\n```md\n## Fake\ninside code\n```\n## Second\nTOPAZ\n")
        reader = self.reader()
        result = reader.search("SAPPHIRE")["results"][0]
        item = reader.fetch(result["id"])
        self.assertIn("## Fake\ninside code", item["text"])
        self.assertNotIn("TOPAZ", item["text"])

    def test_fenced_h1_does_not_leak_into_an_unrelated_result_title(self):
        self.write("note.md", "## Code sample\n```md\n# UNRELATED_CODE_SECRET\n```\n## Target\nSAPPHIRE\n")
        reader = self.reader()
        result = reader.search("SAPPHIRE")
        self.assertEqual(len(result["results"]), 1)
        self.assertNotIn("UNRELATED_CODE_SECRET", json.dumps(result))
        item = reader.fetch(result["results"][0]["id"])
        self.assertNotIn("UNRELATED_CODE_SECRET", json.dumps(item))

    def test_substantive_preamble_is_searchable_without_other_section(self):
        self.write("note.md", "---\nstatus: active\n---\n# Demo\n\nPREAMBLE_SAPPHIRE\n\n## Later\nUNRELATED_SECTION\n")
        reader = self.reader()
        result = reader.search("PREAMBLE_SAPPHIRE")
        self.assertEqual(len(result["results"]), 1)
        item = reader.fetch(result["results"][0]["id"])
        self.assertIn("PREAMBLE_SAPPHIRE", item["text"])
        self.assertNotIn("UNRELATED_SECTION", item["text"])

    def test_frontmatter_cannot_bypass_returned_section_size_limit(self):
        frontmatter = "---\nsynthetic: " + "x" * VaultReader.MAX_SECTION + "\n---\n"
        self.write("note.md", frontmatter + "# Demo\n## Target\nSAPPHIRE\n")
        reader = self.reader()
        with self.assertRaisesRegex(RetrievalError, "size limit"):
            result = reader.search("SAPPHIRE")
            reader.fetch(result["results"][0]["id"])

    def test_expiry_during_fetch_does_not_return_content(self):
        self.write("note.md", "# Demo\n## One\nSAPPHIRE\n")
        reader = self.reader()
        identifier = reader.search("SAPPHIRE")["results"][0]["id"]
        original = reader._read

        def expire_after_read(relative):
            body = original(relative)
            self.now += 61
            return body

        with patch.object(reader, "_read", side_effect=expire_after_read):
            with self.assertRaisesRegex(RetrievalError, "READS_LOCKED"):
                reader.fetch(identifier)

    def test_file_replaced_by_symlink_after_search_fails_closed(self):
        target = self.write("note.md", "# Demo\n## One\nSAPPHIRE\n")
        reader = self.reader()
        identifier = reader.search("SAPPHIRE")["results"][0]["id"]
        outside = self.base / "outside.md"
        outside.write_text("# Secret\n## One\nOUTSIDE_SYNTHETIC_SECRET\n", encoding="utf-8")
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaises(RetrievalError) as error:
            reader.fetch(identifier)
        self.assertNotIn("OUTSIDE_SYNTHETIC_SECRET", str(error.exception))

    def test_invalid_window_is_rejected(self):
        for value in (-1, 601):
            with self.subTest(seconds=value):
                with self.assertRaises(RetrievalError):
                    self.reader(seconds=value)


if __name__ == "__main__":
    unittest.main()
