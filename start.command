#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

if ! .venv/bin/python -c 'import forap_analysis, openpyxl, pandas, plotly, scipy, streamlit' 2>/dev/null; then
  .venv/bin/python -m pip install -e .
fi

exec .venv/bin/streamlit run app.py
