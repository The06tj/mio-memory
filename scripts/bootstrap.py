#!/usr/bin/env python3
"""Create a project-local virtualenv and install this checkout; never starts retrieval."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Show preflight only; do not install or change files.")
    parser.add_argument("--dry-run", action="store_true", help="Alias of --check.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    environment = root / ".venv"
    checks = {"python_supported": sys.version_info >= (3, 10), "posix_platform": sys.platform in {"darwin", "linux"},
              "project_present": (root / "pyproject.toml").is_file(), "venv_not_symlink": not environment.is_symlink()}
    result = {"ok": all(checks.values()), "checks": checks, "project": str(root),
              "venv": str(environment), "starts_service": False, "reads_notes": False,
              "installs_tunnel_client": False,
              "plan": ["Create .venv with this Python", "Install the local project and declared dependencies in .venv"]}
    if args.check or args.dry_run or not result["ok"]:
        print(json.dumps(result))
        return 0 if result["ok"] else 1
    try:
        if environment.exists() and not (environment / "pyvenv.cfg").is_file():
            raise ValueError("Existing .venv is not a virtual environment; it was not overwritten.")
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin/python"
        process = subprocess.run([str(python), "-m", "pip", "install", "-e", str(root)],
                                 stdout=sys.stderr, stderr=sys.stderr)
        if process.returncode:
            raise ValueError("Dependency installation failed; see installer output.")
        result.update(installed=True, python=str(python))
    except (OSError, ValueError) as exc:
        result.update(ok=False, error=str(exc))
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
