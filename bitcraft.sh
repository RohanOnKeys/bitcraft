#!/usr/bin/env sh
# Opens BitCraft in a new, large terminal window. Usage: ./bitcraft.sh [run | demo | here | status] [options]
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then PY="$ROOT/.venv/Scripts/python.exe"
else PY=python3; fi
cd "$ROOT" && exec "$PY" -m bitcraft.cli "$@"
