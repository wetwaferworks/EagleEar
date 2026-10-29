#!/bin/sh
# Eagle Ear login page-cache prewarm (2026-10-09). Started hidden by start-login.ps1 as the command of the
# early WSL boot, so it runs while the widget starts. Reads the server's Python module files (list built by
# build-prewarm-list.py, in import order) into the VM page cache so the server's cold import does not stall on
# ~12,700 small files. Reads nothing private; writes only its own timing lines.
LOG="${EAGLE_EAR_PREWARM_LOG:-/opt/parakeet/logs-wsl/prewarm-boot.log}"
LIST=/opt/parakeet/prewarm.list
ts() { date '+%Y-%m-%dT%H:%M:%S.%3N'; }
if [ ! -r "$LIST" ]; then echo "$(ts) prewarm: no list ($LIST) - skipped" >> "$LOG"; exit 0; fi
if [ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 262144 ]; then mv -f "$LOG" "$LOG.1"; fi
UP=$(cut -d' ' -f1 /proc/uptime)
N=$(wc -l < "$LIST")
echo "$(ts) prewarm start: WSL uptime ${UP} s, $N files" >> "$LOG"
S=$(date +%s.%N)
tr '\n' '\0' < "$LIST" | xargs -0 -P 8 -n 256 cat > /dev/null 2>&1
E=$(date +%s.%N)
MB=$(tr '\n' '\0' < "$LIST" | xargs -0 stat -c %s 2>/dev/null | awk '{s+=$1} END {printf "%d", s/1048576}')
echo "$(ts) prewarm end: ${MB} MB in $(echo "$E $S" | awk '{printf "%.2f", $1-$2}') s; cached now $(awk '/^Cached:/{printf "%d", $2/1024}' /proc/meminfo) MB" >> "$LOG"