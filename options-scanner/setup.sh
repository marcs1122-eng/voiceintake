#!/usr/bin/env bash
# One-shot setup: installs dependencies, asks for your tastytrade credentials
# (only if .env doesn't already exist), validates the connection, and launches
# the dashboard. Credentials are typed into THIS terminal only (input hidden)
# and saved to the git-ignored .env file on this computer.
set -e
cd "$(dirname "$0")"

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python

echo "Installing dependencies (first run can take a few minutes)..."
"$PY" -m pip install --quiet -r requirements.txt \
  || "$PY" -m pip install --quiet --user --break-system-packages -r requirements.txt

if [ ! -f .env ]; then
  echo
  echo "Enter your tastytrade API credentials (from developer.tastytrade.com)."
  echo "Typing is hidden - paste each value and press Enter."
  read -r -s -p "CLIENT SECRET: " TT_SECRET; echo
  read -r -s -p "REFRESH TOKEN: " TT_TOKEN; echo
  printf "TASTYTRADE_CLIENT_SECRET=%s\nTASTYTRADE_REFRESH_TOKEN=%s\n" "$TT_SECRET" "$TT_TOKEN" > .env
  echo "Saved to .env (stays on this computer; git-ignored)."
fi

echo
echo "Validating tastytrade connection..."
if "$PY" -m scanner.tastytrade_check; then
  echo
  echo "Launching dashboard (leave this window open; Ctrl+C to stop)..."
  "$PY" -m streamlit run app.py
else
  echo
  echo "Validation failed. Fix the values in .env (or delete .env and rerun this"
  echo "script to re-enter them). To use free Yahoo data instead:"
  echo "  $PY -m streamlit run app.py"
  exit 1
fi
