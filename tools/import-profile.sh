#!/bin/bash
# log 43: where does "import nemo.collections.asr" spend its time?
cd /tmp
P=/opt/parakeet/venv/bin/python
s=$(date +%s.%N); $P -c pass; e=$(date +%s.%N); echo "python -c pass: $(echo "$e - $s" | bc) s"
s=$(date +%s.%N); $P -S -c pass; e=$(date +%s.%N); echo "python -S -c pass: $(echo "$e - $s" | bc) s"
echo ".pth files: $(ls /opt/parakeet/venv/lib/python3.12/site-packages/*.pth 2>/dev/null | wc -l)"
$P -X importtime -c "import torch; import nemo.collections.asr" 2> /tmp/imp.txt
$P - <<'PY'
rows=[]
for ln in open('/tmp/imp.txt'):
    if not ln.startswith('import time:') or 'cumulative' in ln: continue
    p=ln[12:].split('|'); self_us=int(p[0]); cum=int(p[1]); name=p[2].rstrip()
    depth=(len(name)-len(name.lstrip()))//2
    rows.append((cum,self_us,depth,name.strip()))
print("depth<=3 cumulative > 400 ms:")
for cum,s,d,n in sorted([r for r in rows if r[2]<=3],reverse=True)[:40]:
    if cum>400000: print(f"{cum/1e6:7.2f}s  self {s/1e6:5.2f}s  d{d} {n}")
print("biggest self times:")
for cum,s,d,n in sorted(rows,key=lambda r:-r[1])[:15]:
    print(f"self {s/1e6:5.2f}s cum {cum/1e6:6.2f}s d{d} {n}")
PY
$P -c "import safetensors; print('safetensors', safetensors.__version__)" 2>&1
