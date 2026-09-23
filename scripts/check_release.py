"""Scan the distributable tree without printing potential secrets or note contents."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", "__pycache__", "build", "dist"}
PATTERNS = {
    "personal absolute path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),
    "possible API credential": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "private tunnel identifier": re.compile(r"\btunnel_[0-9a-f]{24,}\b"),
    "private application identifier": re.compile(r"\basdk_app(?:_v)?_[0-9a-f]{24,}\b"),
    "private organization identifier": re.compile(r"\borg-[A-Za-z0-9]{10,}\b"),
    "private conversation URL": re.compile(r"https://chatgpt\.com/c/[0-9a-f-]+"),
    "personal mailbox": re.compile(r"[A-Za-z0-9_.+-]+@(?:outlook|gmail|hotmail)\.com", re.I),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked", action="store_true", help="Scan exactly git-tracked files.")
    args = parser.parse_args()
    if args.tracked:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        paths = [ROOT / name for name in output.decode().split("\0") if name]
    else:
        paths = [p for p in ROOT.rglob("*") if p.is_file()
                 and not any(x in EXCLUDED or x.endswith(".egg-info") for x in p.relative_to(ROOT).parts)]
    failures = []
    for path in paths:
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            failures.append(f"{relative}: symlinks are not distributable")
            continue
        if any(part in {".local", ".runtime", "private", "state"} for part in relative.parts) or path.name.startswith(".env"):
            failures.append(f"{relative}: local data or credential file")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            failures.append(f"{relative}: binary file requires manual review")
            continue
        for number, line in enumerate(content.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    failures.append(f"{relative}:{number}: {label}")
    if failures:
        print("Release scan FAILED; matched values are deliberately withheld.")
        print("\n".join(failures))
        return 1
    print(f"Release scan passed for {len(paths)} text files. Manual provenance review is still required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
