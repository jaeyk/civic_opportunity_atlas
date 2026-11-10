#!/bin/bash
# Publish the website: (optionally) rebuild the data, run the tests, commit, and push main.
# GitHub Pages serves docs/ on main: https://jaeyk.github.io/civic_opportunity_atlas/
#
#   ./update_website.sh                     test, commit any changes, push
#   ./update_website.sh --build             rebuild the data first (needs ./get_full_data.sh once)
#   ./update_website.sh -m "Fix wording"    use your own commit message
#
# It stops without publishing if you're not on main or if the tests fail.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

BUILD=0
MSG="Update website"
while [ $# -gt 0 ]; do
  case "$1" in
    --build) BUILD=1; shift ;;
    -m) MSG="${2:?-m needs a message}"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)"; exit 1 ;;
  esac
done

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "You're on '$BRANCH', but the site publishes from main."
  echo "Switch first:  git checkout main && git merge $BRANCH"
  exit 1
fi

if [ "$BUILD" = 1 ]; then
  echo "Rebuilding data ..."
  "$PY" -m pipeline.build
  "$PY" -m pipeline.site_data
fi

echo "Running tests ..."
if ! "$PY" -m pytest -q tests; then
  echo "Tests failed, so nothing was published. Fix the failures and run again."
  exit 1
fi

# Stage the website and any edits to tracked files (new files outside docs/ need a manual git add)
git add docs
git add -u
if git diff --cached --quiet; then
  echo "No new changes to commit."
else
  git status --short | grep -v '^?? ' | sed -n '1,15p'
  git commit -q -m "$MSG"
  echo "Committed: $MSG"
fi

echo "Pushing to GitHub ..."
git push origin main
echo "Done. The site updates within a few minutes at https://jaeyk.github.io/civic_opportunity_atlas/"
