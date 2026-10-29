#!/bin/bash
source /opt/parakeet/scripts/env.sh
for mode in "$@"; do
  echo "=== $mode"
  /opt/parakeet/venv/bin/python /mnt/r/repos/EagleEar/tools/debug-decode.py "$mode" 2>&1 | grep -v "NeMo [IW]" | tail -4
done
