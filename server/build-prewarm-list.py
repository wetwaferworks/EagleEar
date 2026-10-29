"""Build the page-cache prewarm list for Eagle Ear's server start (run inside WSL, CPU only).
Only the Python module files (source + .pyc + extension .so), in import order: a cold import stalls on
~12,700 small files. The big shared libraries (torch/CUDA, ~5 GB) are left to demand paging: the server
touches only part of them, and reading them whole would compete with the import. Their sizes are printed.
Writes /opt/parakeet/prewarm.list (one path per line)."""
import os, sys, glob
os.environ["CUDA_VISIBLE_DEVICES"] = ""
sys.path.insert(0, "/opt/parakeet/scripts")
OUT = "/opt/parakeet/prewarm.list"
VENV = os.path.realpath(sys.prefix)
def maps(pid="self"):
    out = []
    try:
        for line in open(f"/proc/{pid}/maps"):
            p = line.split()[-1] if len(line.split()) >= 6 else ""
            if p.startswith("/") and ".so" in os.path.basename(p) and p not in out:
                out.append(p)
    except OSError:
        pass
    return out
import torch  # noqa
first = maps()
import nemo.collections.asr as nemo_asr  # noqa
import eagle_fastload as fl
model = fl.load_cpu()          # hydra instantiates the encoder/decoder/... : their modules get imported too
mods = []
for name, m in list(sys.modules.items()):
    for attr in ("__file__", "__cached__"):
        f = getattr(m, "__dict__", {}).get(attr)   # never getattr: lazy modules would import more
        if isinstance(f, str) and os.path.isfile(f) and f not in mods:
            mods.append(f)
later = [p for p in maps() if p not in first]
gpu = []
for pid in os.listdir("/proc"):
    if pid.isdigit():
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read()
        except OSError:
            continue
        if b"live_server.py" in cmd and int(pid) != os.getpid():
            gpu = [p for p in maps(pid) if p not in first and p not in later and p not in mods]
            break
seen, order = set(), []
for p in mods:
    rp = os.path.realpath(p)
    if rp not in seen and os.path.isfile(rp):
        seen.add(rp); order.append(rp)
with open(OUT + ".tmp", "w") as f:
    f.write("\n".join(order) + "\n")
os.replace(OUT + ".tmp", OUT)
mb = lambda L: round(sum(os.path.getsize(os.path.realpath(p)) for p in L if os.path.isfile(os.path.realpath(p))) / 2**20)
print(f"MANIFEST files={len(order)} total_MB={mb(order)} | torch-import libs {len(first)} files {mb(first)} MB | "
      f"module files {len(mods)} {mb(mods)} MB | later libs {len(later)} {mb(later)} MB | gpu-server libs {len(gpu)} {mb(gpu)} MB")