import os, sys, time, json
sys.path.insert(0, r"R:\repos\EagleEar\widget")
import eagle_gpu as g
ad = g.find_adapter(); print("adapter", ad)
s = g.GpuSampler(ad)
cpu0, w0 = time.thread_time(), time.perf_counter(); n = 0; times = []
for i in range(6):
    time.sleep(4 if i else 1)
    t = time.thread_time(); x = s.sample(); times.append(time.thread_time() - t); n += 1
pr = x["procs"]
print("used/free/total MB", round(x["used_mb"] or -1), round(x["free_mb"] or -1), x["total_mb"])
print("mem", {pr.get(p, ("?",))[0] + ":" + str(p): round(v) for p, v in x["mem_mb"].items() if v > 5})
print("3d", {pr.get(p, ("?",))[0] + ":" + str(p): round(v, 1) for p, v in x["util3d"].items() if v > 0.5})
print("procs", len(pr), "sample cpu ms each:", [round(t * 1000, 1) for t in times])
