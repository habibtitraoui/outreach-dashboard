#!/usr/bin/env bash
# EduFormation outreach dashboard — one-click start (macOS / Linux)
#
# Double-click this file, or run:  bash start.sh
# Then open:  http://localhost:8000

cd "$(dirname "$0")" || exit 1

echo
echo "  EduFormation outreach dashboard"
echo "  --------------------------------"

# 1. python present?
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✗ python3 not found. Install it from https://python.org and run this again."
  read -r -p "  press Enter to close…" _; exit 1
fi
echo "  ✓ python3 $(python3 -V 2>&1 | awk '{print $2}')"

# 2. port free?
if command -v lsof >/dev/null 2>&1 && lsof -i :8000 >/dev/null 2>&1; then
  echo "  ! something is already using port 8000 — if the dashboard is already open, just use it."
fi

# 3. Gmail app password: use the saved one if you ticked "remember", otherwise ask once
if [ -z "$GMAIL_APP_PASSWORD" ] && [ ! -f ".gmail_app_password" ]; then
  echo
  echo "  Gmail app password (16 characters). Leave blank to type it inside the page instead."
  echo "  Create one at: Google Account → Security → App passwords"
  read -r -s -p "  app password: " PW
  echo
  if [ -n "$PW" ]; then export GMAIL_APP_PASSWORD="$PW"; fi
fi

# 4. open the browser a moment after the server comes up
( sleep 1.5; command -v open >/dev/null 2>&1 && open "http://localhost:8000" \
  || command -v xdg-open >/dev/null 2>&1 && xdg-open "http://localhost:8000" ) >/dev/null 2>&1 &

echo
echo "  starting…   open http://localhost:8000   (Ctrl-C stops it)"
echo
exec python3 app.py
