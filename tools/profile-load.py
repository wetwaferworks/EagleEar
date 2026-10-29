#!/opt/parakeet/venv/bin/python
"""Profile a cold Parakeet load stage by stage (log 43). Usage: profile-load.py [--variant nemo|extracted|fast]"""
import os, sys, time, json, resource
T0 = time.perf_counter()
sys.path.insert(0, "/opt/parakeet/scripts")
marks = []
def mark(name, t):
    marks.append((name, round(t, 2)))
    print(f"  {name:<44} {t:7.2f} s   rss={rss():.0f} MiB", flush=True)
def rss():
    with open("/proc/self/status") as f:
        for ln in f:
            if ln.startswith("VmRSS"):
                return int(ln.split()[1]) / 1024
    return 0
import argparse
ap = argparse.ArgumentParser(); ap.add_argument("--variant", default="nemo"); ap.add_argument("--no-gpu", action="store_true")
a = ap.parse_args()
t = time.perf_counter(); import transcribe as tx; mark("import transcribe (env setup)", time.perf_counter() - t)
t = time.perf_counter(); import numpy as np; mark("import numpy", time.perf_counter() - t)
t = time.perf_counter(); import torch; mark("import torch", time.perf_counter() - t)
t = time.perf_counter(); torch.cuda.init(); _ = torch.zeros(1, device="cuda"); mark("CUDA context init", time.perf_counter() - t)
t = time.perf_counter()
if a.variant == "nemo":
    import nemo.collections.asr as nemo_asr; mark("import nemo.collections.asr", time.perf_counter() - t)
else:
    from nemo.collections.asr.models import EncDecRNNTBPEModel; mark("import nemo...asr.models (trimmed)", time.perf_counter() - t)
import logging; logging.getLogger("nemo_logger").setLevel(logging.ERROR)
from nemo.core.connectors.save_restore_connector import SaveRestoreConnector
import torch.serialization
stage = {"unpack": 0.0, "torch_load": 0.0}
_unpack = SaveRestoreConnector._unpack_nemo_file
def unpack(*k, **kw):
    t = time.perf_counter(); r = _unpack(*k, **kw); stage["unpack"] += time.perf_counter() - t; return r
SaveRestoreConnector._unpack_nemo_file = staticmethod(unpack)
_tl = torch.load
def tload(*k, **kw):
    t = time.perf_counter(); r = _tl(*k, **kw); stage["torch_load"] += time.perf_counter() - t; return r
torch.load = tload
t = time.perf_counter()
if a.variant == "nemo":
    model = nemo_asr.models.ASRModel.restore_from(str(tx.MODEL_FILE), map_location="cpu")
else:
    con = SaveRestoreConnector(); con.model_extracted_dir = "/opt/parakeet/models/parakeet-tdt-0.6b-v2-extracted"
    if a.variant == "fast":
        import contextlib
        from nemo.core.classes.modelPT import ModelPT
        # skip random weight init during construction: every parameter is overwritten by load_state_dict(strict=True)
        noop = lambda tensor, *k, **kw: tensor
        names = ["uniform_", "normal_", "xavier_uniform_", "xavier_normal_", "kaiming_uniform_", "kaiming_normal_",
                 "trunc_normal_", "constant_", "zeros_", "ones_", "orthogonal_"]
        saved = {n: getattr(torch.nn.init, n) for n in names}
        for n in names: setattr(torch.nn.init, n, noop)
        try:
            model = EncDecRNNTBPEModel.restore_from(str(tx.MODEL_FILE), map_location="cpu", save_restore_connector=con)
        finally:
            for n, f in saved.items(): setattr(torch.nn.init, n, f)
    else:
        model = EncDecRNNTBPEModel.restore_from(str(tx.MODEL_FILE), map_location="cpu", save_restore_connector=con)
tot = time.perf_counter() - t
mark("restore_from total", tot)
mark("  of which .nemo tar unpack", stage["unpack"])
mark("  of which torch.load (weights read)", stage["torch_load"])
mark("  of which construct model + load_state_dict + tokenizer", tot - stage["unpack"] - stage["torch_load"])
t = time.perf_counter()
model.eval()
try: model.change_subsampling_conv_chunking_factor(1)
except Exception: pass
tx.disable_cuda_graph_decoder(model)
model.preprocessor.featurizer.dither = 0.0; model.preprocessor.featurizer.pad_to = 0
mark("eval + decoding config", time.perf_counter() - t)
t = time.perf_counter(); model.encoder.to(torch.bfloat16); mark("encoder -> bf16 (CPU)", time.perf_counter() - t)
t = time.perf_counter(); model = model.to("cuda"); torch.cuda.synchronize(); mark("model .to(cuda)", time.perf_counter() - t)
sys.path.insert(0, "/mnt/r/repos/EagleEar/server")
import live_server as ls
ls.MODEL.update(model=model, dtype=torch.bfloat16, device="cuda", fast_ok=True)
warm = (np.random.default_rng(0).standard_normal(16000 * 2) * 0.01).astype("float32")
t = time.perf_counter(); ls.infer(np.zeros(16000, dtype="float32")); mark("warm-up 1 (zeros, fast path)", time.perf_counter() - t)
t = time.perf_counter(); ls.infer(warm); mark("warm-up 2 (noise, fast path)", time.perf_counter() - t)
t = time.perf_counter(); ls.infer(warm, path="slow"); mark("warm-up 3 (slow path transcribe())", time.perf_counter() - t)
import wave
outs = {}
for f in ("libri sample 16k mono.wav", "espeak sample 16k mono.wav"):
    with wave.open("/mnt/r/data/EagleEar/test-samples/" + f) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768
    outs[f] = ls.infer(x)
# CPU<->GPU round trip (RAM standby feasibility)
t = time.perf_counter(); model.cpu(); torch.cuda.synchronize(); torch.cuda.empty_cache(); mark("standby: model.cpu() + empty_cache", time.perf_counter() - t)
free, total = torch.cuda.mem_get_info(); mark(f"  gpu used after standby (MiB) = {(total-free)/2**20:.0f}", 0)
t = time.perf_counter(); model.to("cuda"); torch.cuda.synchronize(); mark("resume: model.to(cuda)", time.perf_counter() - t)
t = time.perf_counter(); ls.infer(warm); mark("  first infer after resume", time.perf_counter() - t)
outs2 = {}
for f in outs:
    with wave.open("/mnt/r/data/EagleEar/test-samples/" + f) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768
    outs2[f] = ls.infer(x)
mark("TOTAL process time", time.perf_counter() - T0)
print("TRANSCRIPTS " + json.dumps(outs))
print("AFTER_RESUME_SAME " + str(outs == outs2))
print("MAXRSS_MIB %.0f" % (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024))
