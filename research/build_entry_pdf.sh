#!/bin/sh
# Builds docs/BEST_BIAS_DISCOVERY_mrSharafi.pdf from the Markdown entry (pandoc + headless Chrome).
set -e
cd "$(dirname "$0")/.."
python3 research/discovery_figures_v3.py
python3 research/build_discovery_doc.py
python3 research/check_entry_numbers.py | tail -1
pandoc docs/BEST_BIAS_DISCOVERY.md -s --metadata pagetitle="Best Bias Discovery - mrSharafi" -c entry.css -o docs/BEST_BIAS_DISCOVERY.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PWD/docs/BEST_BIAS_DISCOVERY_mrSharafi.pdf" "file://$PWD/docs/BEST_BIAS_DISCOVERY.html" 2>/dev/null
ls -l docs/BEST_BIAS_DISCOVERY_mrSharafi.pdf
