"""Allocator check + accurate watcher CPU cost (many samples)."""
import os, sys, time, subprocess
sys.path.insert(0, r"R:\repos\EagleEar\widget")
import eagle_gpu as g
ad = g.find_adapter(); s = g.GpuSampler(ad)
PY = r"R:\repos\EagleEar\widget\.venv\Scripts\python.exe"
# CPU cost: 40 samples, 0.25 s apart
c0 = time.process_time(); n = 40
for i in range(n):
    time.sleep(0.25); x = s.sample()
per = (time.process_time() - c0) / n
print(f"cpu per sample {per*1000:.2f} ms -> at 4 s polling {per/4*100:.3f}% of one core, {per/4*100/os.cpu_count():.4f}% of total ({os.cpu_count()} logical CPUs)")
base = x["used_mb"]
p = subprocess.Popen([PY, r"R:\repos\EagleEar\tests\gpu_alloc_test.py", "--mb", "600", "--seconds", "15"], stdout=subprocess.PIPE, text=True)
print(p.stdout.readline().strip())
time.sleep(2); x = s.sample()
pr = x["procs"]
print("during: used", round(x["used_mb"]), "free", round(x["free_mb"]), "(was used", round(base), ")")
print("mem", {pr.get(q, ("?",))[0] + ":" + str(q): round(v) for q, v in x["mem_mb"].items() if v > 5}, "alloc pid", p.pid)
p.wait(); print(p.stdout.read().strip())
time.sleep(1); x = s.sample(); print("after: used", round(x["used_mb"]), "free", round(x["free_mb"]))
