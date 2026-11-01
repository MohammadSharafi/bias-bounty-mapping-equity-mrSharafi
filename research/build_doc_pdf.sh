#!/bin/sh
# Builds docs/BEST_DOCUMENTATION_mrSharafi.pdf from the Markdown entry (pandoc + headless Chrome).
set -e
cd "$(dirname "$0")/.."
python3 research/doc_figures.py
pandoc docs/BEST_DOCUMENTATION.md -s --metadata pagetitle="Best Documentation - mrSharafi" -c entry.css -o docs/BEST_DOCUMENTATION.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PWD/docs/BEST_DOCUMENTATION_mrSharafi.pdf" "file://$PWD/docs/BEST_DOCUMENTATION.html" 2>/dev/null
ls -l docs/BEST_DOCUMENTATION_mrSharafi.pdf
