#!/bin/bash
# What sits in the WSL page cache while a standby (RAM-only) server is up? (log 47 diagnostics; read-only)
PORT=51799
/opt/parakeet/venv/bin/python /opt/parakeet/scripts/live_server.py --port $PORT --standby --idle-exit 60 >/tmp/cacheprof.log 2>&1 &
for i in $(seq 1 120); do curl -s localhost:$PORT/health | grep -q '"status": "standby"' && break; sleep 1; done
curl -s localhost:$PORT/health | head -c 300; echo
free -m
sleep 3
SP=$(/opt/parakeet/venv/bin/python -c 'import site;print(site.getsitepackages()[0])')
/opt/parakeet/venv/bin/python /mnt/r/repos/EagleEar/tools/cache-profile.py "$SP" /usr/lib /opt/parakeet/models
echo "== mapped by the server (RSS file-backed) =="
PID=$(pgrep -f "live_server.py --port $PORT" | head -1)
grep -E 'RssFile|RssAnon' /proc/$PID/status
curl -s -X POST localhost:$PORT/shutdown >/dev/null; sleep 2
