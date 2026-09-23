"""Local, scoped Markdown retrieval. No network, writes, or background jobs."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode


class RetrievalError(ValueError):
    """Safe error text: never include local absolute paths or source contents."""


@dataclass(frozen=True)
class Item:
    id: str
    title: str
    text: str
    url: str
    metadata: dict


class VaultReader:
    MAX_BYTES = 256 * 1024
    MAX_SECTION = 12000
    MAX_FILES = 2048
    MAX_SCAN_ENTRIES = 10000
    MAX_TOTAL_BYTES = 16 * 1024 * 1024
    ISSUED_TTL = 600

    def __init__(self, config_path: Path, open_seconds: int = 0, *, continuous_read: bool = False):
        if not 0 <= open_seconds <= 600:
            raise RetrievalError("Read window must be between 0 and 600 seconds.")
        if type(continuous_read) is not bool or (continuous_read and open_seconds):
            raise RetrievalError("Continuous reads and a timed read window are mutually exclusive.")
        config_path = config_path.resolve()
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.root = (config_path.parent / config["root"]).resolve(strict=True)
        if not self.root.is_dir():
            raise RetrievalError("Invalid source directory.")
        self.vault_name = config["vault_name"]
        self.scope = config.get("scope", "explicit_files")
        if self.scope not in {"explicit_files", "vault_markdown"}:
            raise RetrievalError("Unknown source scope.")
        if self.scope == "vault_markdown":
            if "files" in config:
                raise RetrievalError("Whole-vault scope and explicit files are mutually exclusive.")
            files = []
        else:
            files = config.get("files")
            if not isinstance(files, list) or not 1 <= len(files) <= 128:
                raise RetrievalError("Configure between 1 and 128 explicit note paths.")
        for name in files:
            if not isinstance(name, str):
                raise RetrievalError("Invalid allowlist.")
            parts = name.split("/")
            if (PurePosixPath(name).is_absolute() or "\\" in name or "\x00" in name
                    or any(not p or p.startswith(".") for p in parts)
                    or not name.endswith(".md")):
                raise RetrievalError("Allowlist must contain regular Markdown note paths only.")
        self.files = tuple(dict.fromkeys(files))
        self.deadline = None if continuous_read else (time.monotonic() + open_seconds if open_seconds else 0)
        self.issued: dict[str, tuple[str, str]] = {}
        self.issued_deadline = 0
        self.lock = threading.RLock()
        # Pin the reviewed source directory for this process. Later ancestor
        # renames/symlink swaps cannot redirect reads to a different vault.
        self.root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        if getattr(self, "root_fd", None) is not None:
            os.close(self.root_fd)
            self.root_fd = None

    def __del__(self):
        self.close()

    def _gate(self):
        if self.root_fd is None or (self.deadline is not None and time.monotonic() >= self.deadline):
            self.issued.clear()
            raise RetrievalError("READS_LOCKED: Ask the user to enable local reading. Do not retry automatically.")

    def _refresh_files(self):
        """Discover only inside the pinned root; never follow a symlink or read bodies."""
        if self.scope != "vault_markdown":
            return
        found = []
        scanned = 0
        total_bytes = 0

        def visit(directory_fd, prefix=(), depth=0):
            nonlocal scanned, total_bytes
            if depth > 32:
                raise RetrievalError("Vault directory depth exceeds the limit.")
            self._gate()
            with os.scandir(directory_fd) as entries:
                for entry in entries:
                    scanned += 1
                    if scanned > self.MAX_SCAN_ENTRIES:
                        raise RetrievalError("Vault directory scan exceeds the entry limit.")
                    if entry.name.startswith(".") or "\\" in entry.name:
                        continue
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                        dir_fd=directory_fd)
                        try:
                            visit(child, prefix + (entry.name,), depth + 1)
                        finally:
                            os.close(child)
                    elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and entry.name.endswith(".md"):
                        if info.st_size > self.MAX_BYTES:
                            raise RetrievalError("A Markdown note exceeds the size limit.")
                        total_bytes += info.st_size
                        found.append("/".join(prefix + (entry.name,)))
                        if len(found) > self.MAX_FILES or total_bytes > self.MAX_TOTAL_BYTES:
                            raise RetrievalError("Vault note count or total size exceeds the limit.")

        try:
            visit(self.root_fd)
        except OSError:
            raise RetrievalError("Vault contents changed or are unavailable; review locally.") from None
        self.files = tuple(sorted(found))

    def _read(self, relative: str) -> str:
        if relative not in self.files:
            raise RetrievalError("Note is not allowlisted.")
        descriptors = []
        try:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            parent = os.dup(self.root_fd)
            descriptors.append(parent)
            for part in relative.split("/")[:-1]:
                parent = os.open(part, flags, dir_fd=parent)
                descriptors.append(parent)
            fd = os.open(relative.split("/")[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=parent)
            descriptors.append(fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > self.MAX_BYTES:
                raise RetrievalError("Note must be a bounded regular file without hard links.")
            data = bytearray()
            while len(data) <= self.MAX_BYTES:
                block = os.read(fd, min(65536, self.MAX_BYTES + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
            if len(data) > self.MAX_BYTES:
                raise RetrievalError("Note exceeds the size limit.")
            return data.decode("utf-8")
        except (OSError, UnicodeError):
            raise RetrievalError("An allowlisted note is unavailable or unsafe to read.") from None
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    def _items(self, relative: str, text: str) -> list[Item]:
        lines = text.splitlines(keepends=True)
        front = re.match(r"\A---\r?\n.*?\r?\n---(?:\r?\n|$)", text, re.S)
        frontmatter = front[0] if front else ""
        front_lines = len(frontmatter.splitlines())
        note_title = Path(relative).stem
        found_title = False
        # Only level-two Markdown headings split records. Nested headings and
        # paired quotations stay together. Ignore headings inside fenced code.
        starts = [0]
        fence = None
        for number, line in enumerate(lines):
            if number < front_lines:
                continue
            match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
            if match:
                marker = match[1]
                if fence is None:
                    fence = marker
                elif marker[0] == fence[0] and len(marker) >= len(fence):
                    fence = None
            elif fence is None and line.startswith("## "):
                starts.append(number)
            elif fence is None and line.startswith("# ") and len(starts) == 1 and not found_title:
                note_title = line[2:].strip()
                found_title = True
        starts = sorted(set(starts)) + [len(lines)]
        items = []
        for start, end in zip(starts, starts[1:]):
            body = "".join(lines[start:end]).strip()
            if not body:
                continue
            if start == 0 and len(starts) > 2:
                preamble = body[len(frontmatter.rstrip()):] if frontmatter else body
                preamble = re.sub(r"^# .*$", "", preamble, flags=re.M).strip()
                if not preamble:
                    continue  # Do not duplicate metadata-only headers.
            if len(body) > self.MAX_SECTION:
                raise RetrievalError("A note section exceeds the prototype size limit; review it locally.")
            heading = lines[start][3:].strip() if lines[start].startswith("## ") else note_title
            raw_states = sorted(set(re.findall(r"\b(?:active|superseded|deprecated|uncertain)\b", body, re.I)))
            content = (frontmatter + "\n" + body).strip() if start else body
            if len(content) > self.MAX_SECTION:
                raise RetrievalError("A note section with metadata exceeds the prototype size limit.")
            digest = hashlib.sha256((relative + "\0" + note_title + "\0" + str(start) + "\0" + content).encode()).hexdigest()
            category = "archive" if "90_Archive" in relative.split("/") else (
                "system" if "00_System" in relative.split("/") else "note")
            title = f"{note_title} · {heading}" if heading != note_title else note_title
            if category == "archive":
                title = "[历史归档] " + title
            items.append(Item(
                id=digest,
                title=title,
                text=content,
                url="obsidian://open?" + urlencode({"vault": self.vault_name, "file": relative}),
                metadata={"relative_path": relative, "line_start": start + 1, "line_end": end,
                          "states_mentioned": raw_states, "frontmatter_raw": frontmatter,
                          "content_kind": "untrusted_source_text", "source_heading": heading,
                          "source_category": category, "historical": category == "archive"},
            ))
        return items

    def search(self, query: str) -> dict:
        with self.lock:
            self._gate()
            self.issued.clear()
            terms = re.findall(r"[\w-]+", query.casefold())
            if not terms or len(query) > 200 or len(terms) > 12:
                raise RetrievalError("Use 1–12 specific keywords or ISO dates, at most 200 characters.")
            self._refresh_files()
            matches = []
            total_bytes = 0
            for relative in self.files:
                self._gate()
                source = self._read(relative)
                total_bytes += len(source.encode("utf-8"))
                if total_bytes > self.MAX_TOTAL_BYTES:
                    raise RetrievalError("Vault total read size exceeds the limit.")
                for item in self._items(relative, source):
                    haystack = (relative + "\n" + item.title + "\n" + item.text).casefold()
                    if all(term in haystack for term in terms):
                        score = sum(3 * item.title.casefold().count(t) + haystack.count(t) for t in terms)
                        matches.append((score, item))
            self._gate()
            # Each search replaces the eligible fetch set; it is never a growing
            # cache of private note bodies. At most five opaque IDs remain.
            self.issued.clear()
            output = []
            for _, item in sorted(matches, key=lambda pair: (-pair[0], pair[1].id))[:5]:
                self.issued[item.id] = (item.metadata["relative_path"], item.id)
                output.append({"id": item.id, "title": item.title, "url": item.url})
            self.issued_deadline = time.monotonic() + self.ISSUED_TTL
            return {"results": output}

    def fetch(self, identifier: str) -> dict:
        with self.lock:
            self._gate()
            if time.monotonic() >= self.issued_deadline:
                self.issued.clear()
            if identifier not in self.issued:
                raise RetrievalError("Unknown or expired result ID. Search first; paths are not accepted.")
            relative, expected = self.issued[identifier]
            self._refresh_files()
            for item in self._items(relative, self._read(relative)):
                if item.id == expected:
                    self._gate()
                    return {"id": item.id, "title": item.title, "text": item.text,
                            "url": item.url, "metadata": item.metadata}
            self.issued.pop(identifier, None)
            raise RetrievalError("Source changed after search. Search again before quoting it.")
