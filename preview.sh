#!/bin/bash
# Preview the website locally.
#
#   ./preview.sh            serve docs/ at http://localhost:8000 and open it
#   ./preview.sh --build    rebuild the data first (pipeline + site data), then serve
#   PORT=9000 ./preview.sh  use another port
#
# Stop the preview with Ctrl+C.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8000}"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

if [ "${1:-}" = "--build" ]; then
  echo "Rebuilding data ..."
  (cd "$ROOT" && "$PY" -m pipeline.build && "$PY" -m pipeline.site_data)
fi

if [ ! -f "$ROOT/docs/data/meta.json" ]; then
  echo "No site data yet. Run: ./preview.sh --build   (needs ./get_full_data.sh first)"
  exit 1
fi

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is in use. Try: PORT=8001 ./preview.sh"
  exit 1
fi

URL="http://localhost:$PORT/"
echo "Serving docs/ at $URL  (Ctrl+C to stop)"
# Open the browser shortly after the server starts (macOS: open, Linux: xdg-open)
( sleep 1; { command -v open >/dev/null && open "$URL"; } || { command -v xdg-open >/dev/null && xdg-open "$URL"; } || true ) &
cd "$ROOT/docs" && exec "$PY" -m http.server "$PORT" --bind 127.0.0.1
