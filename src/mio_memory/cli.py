"""Agent-friendly JSON command line for a user-controlled read-only memory bridge."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from . import runtime


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's raw diagnostic may echo an accidentally supplied API key.
        raise runtime.RuntimeErrorSafe("Invalid command arguments. Use --help; never pass a key value on the command line.")


def parser() -> argparse.ArgumentParser:
    result = Parser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True, parser_class=Parser)
    for name in ("init", "start", "stop", "status", "doctor", "inspect", "_serve"):
        item = commands.add_parser(name, help="Internal supervisor" if name == "_serve" else name.capitalize())
        item.add_argument("--state-dir", type=Path, help="Private runtime directory outside the project and vault.")
        if name == "init":
            item.add_argument("--vault", type=Path, required=True)
            item.add_argument("--vault-name", required=True)
            item.add_argument("--scope", choices=("files", "vault_markdown"), required=True)
            item.add_argument("--file", action="append", default=[])
        if name == "start":
            access = item.add_mutually_exclusive_group()
            access.add_argument("--continuous-read", action="store_true")
            access.add_argument("--open-seconds", type=int, default=0)
            item.add_argument("--port", type=int, default=8789, help="Default 8789; 0 selects a free loopback port.")
            item.add_argument("--tunnel-id")
            item.add_argument("--tunnel-client", help="Absolute path to the separately installed official tunnel-client.")
            item.add_argument("--key-file", help="Owner-only file containing a restricted tunnel runtime key.")
        if name == "_serve":
            item.add_argument("--token", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    args = None
    try:
        args = parser().parse_args(argv)
        if args.command == "init":
            result = runtime.init(args.state_dir, args.vault, args.vault_name, args.scope, args.file)
        else:
            directory = runtime.state_path(args.state_dir)
            if args.command == "_serve":
                runtime.serve(directory, args.token)
                return 0
            if args.command == "start":
                result = runtime.start(directory, port=args.port, continuous_read=args.continuous_read,
                                       open_seconds=args.open_seconds, tunnel_id=args.tunnel_id,
                                       tunnel_client=args.tunnel_client, key_file=args.key_file)
            else:
                result = getattr(runtime, args.command)(directory)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    except (runtime.RuntimeErrorSafe, OSError) as exc:
        error = str(exc) if isinstance(exc, runtime.RuntimeErrorSafe) else "Filesystem or process operation failed; inspect paths and permissions locally."
        result = {"ok": False, "error": error}
        if args is not None and args.command == "_serve":
            try:
                runtime.write_json(runtime.state_path(args.state_dir) / "startup-error.json", result)
            except OSError:
                pass
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
