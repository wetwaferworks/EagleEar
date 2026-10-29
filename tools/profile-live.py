"""Profile the live inference path stage by stage (run inside WSL with the parakeet venv)."""
import sys, time
sys.path.insert(0, "/opt/parakeet/scripts")
import transcribe as tx
import numpy as np, soundfile as sf, torch
model, dtype = tx.load_model("cuda", no_cuda_graphs=True)
model.preprocessor.featurizer.dither = 0.0; model.preprocessor.featurizer.pad_to = 0
a, sr = sf.read("/opt/parakeet/samples/2086-149220-0033.wav", dtype="float32")
def sync(): torch.cuda.synchronize()
def run(audio, empty=True, label=""):
    T = {}
    t = time.perf_counter()
    sig = torch.from_numpy(audio).unsqueeze(0).cuda(); ln = torch.tensor([sig.shape[1]], device="cuda")
    with torch.inference_mode():
        f, fl = model.preprocessor(input_signal=sig, length=ln); sync(); T["pre"] = time.perf_counter() - t; t = time.perf_counter()
        with torch.autocast("cuda", dtype=dtype):
            e, el = model.encoder(audio_signal=f, length=fl)
        sync(); T["enc"] = time.perf_counter() - t; t = time.perf_counter()
        h = model.decoding.rnnt_decoder_predictions_tensor(encoder_output=e.float(), encoded_lengths=el, return_hypotheses=False)
        sync(); T["dec"] = time.perf_counter() - t; t = time.perf_counter()
    if empty: torch.cuda.empty_cache()
    T["empty"] = time.perf_counter() - t
    return {k: round(v * 1000, 1) for k, v in T.items()}, (h[0] if isinstance(h, tuple) else h)[0].text
for i in range(3): run(a)
print("decoding cfg strategy:", model.cfg.decoding.strategy, "| greedy:", dict(model.cfg.decoding.greedy))
for secs in (2, 4, 7.4):
    x = a[: int(secs * 16000)]
    for empty in (True, False):
        rs = [run(x, empty) for _ in range(6)]
        med = {k: float(np.median([r[0][k] for r in rs])) for k in rs[0][0]}
        print(f"{secs:>4}s empty_cache={empty}: {med} total={sum(med.values()):.0f} ms | {rs[-1][1][:50]}")
print("alloc MiB", torch.cuda.memory_allocated() // 2**20, "reserved MiB", torch.cuda.memory_reserved() // 2**20)
