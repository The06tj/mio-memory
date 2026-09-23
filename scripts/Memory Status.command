#!/bin/zsh
set -eu
PROJECT_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
"$PROJECT_DIR/.venv/bin/python" -m mio_memory.cli status "$@"
