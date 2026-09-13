#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m streamlit run app.py --server.port "${PORT:-8501}" --server.address 0.0.0.0

