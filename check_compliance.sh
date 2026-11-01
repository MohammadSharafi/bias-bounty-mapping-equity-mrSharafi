#!/bin/sh
# Gate 3: the model package must not read any removed reference layer or the
# legacy outputs derived from them (file-path and import patterns, not prose).
set -e
cd "$(dirname "$0")"
if grep -rnE "census-tiger-roads|microsoft-buildings|hifld-|census-cbp|'out/|\"out/|from bb|import bb|-components\.parquet|raw-.*\.parquet" model/ ; then
  echo "COMPLIANCE FAIL: model/ references removed data"; exit 1
fi
echo "COMPLIANCE OK: model/ references permitted layers only"
