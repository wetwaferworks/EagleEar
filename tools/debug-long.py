import os, sys, time
mode = sys.argv[1]
import torch, logging
import nemo.collections.asr as nemo_asr
from omegaconf import open_dict
logging.getLogger("nemo_logger").setLevel(logging.ERROR)
if "nocudnn" in mode:
    torch.backends.cudnn.enabled = False
m = nemo_asr.models.ASRModel.restore_from("/opt/parakeet/models/parakeet-tdt-0.6b-v2.nemo", map_location="cpu").eval()
cfg = m.cfg.decoding
with open_dict(cfg):
    cfg.greedy.use_cuda_graph_decoder = False
m.change_decoding_strategy(cfg, verbose=False)
if "full" not in mode:
    m.change_attention_model("rel_pos_local_attn", [256, 256])
if "cf" in mode:
    m.change_subsampling_conv_chunking_factor(int(mode.split("cf")[1].split("-")[0]))
else:
    m.change_subsampling_conv_chunking_factor(1)
bf = "bf16" in mode
if bf:
    m.encoder.to(torch.bfloat16)
m = m.cuda()
wav = sys.argv[2]
t = time.perf_counter()
ctx = torch.autocast("cuda", dtype=torch.bfloat16) if bf else torch.autocast("cuda", enabled=False)
try:
    with torch.inference_mode(), ctx:
        out = m.transcribe([wav], batch_size=1, timestamps=True, verbose=False)
    torch.cuda.synchronize()
    print(mode, "OK", round(time.perf_counter()-t, 2), "s words", len(out[0].text.split()), "peak MiB", torch.cuda.max_memory_allocated()//2**20, flush=True)
except Exception as e:
    print(mode, "FAIL", type(e).__name__, str(e)[:200], "peak MiB", torch.cuda.max_memory_allocated()//2**20, flush=True)
