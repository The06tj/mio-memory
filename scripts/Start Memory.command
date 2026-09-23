#!/bin/zsh
# No private path or key is embedded. An agent can configure the default state first.
set -eu
PROJECT_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
"$PROJECT_DIR/.venv/bin/python" -m mio_memory.cli start "$@"
