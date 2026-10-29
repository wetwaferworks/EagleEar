import os, sys, time
mode = sys.argv[1]
if "noexp" in mode:
    os.environ.pop("PYTORCH_CUDA_ALLOC_CONF", None)
import torch, logging
import nemo.collections.asr as nemo_asr
from omegaconf import open_dict
logging.getLogger("nemo_logger").setLevel(logging.ERROR)
m = nemo_asr.models.ASRModel.restore_from("/opt/parakeet/models/parakeet-tdt-0.6b-v2.nemo", map_location="cpu").eval()
if "nograph" in mode:
    cfg = m.cfg.decoding
    with open_dict(cfg):
        cfg.greedy.use_cuda_graph_decoder = False
    m.change_decoding_strategy(cfg)
if "bf16" in mode:
    m.encoder.to(torch.bfloat16)
m = m.cuda()
if "chunk1" in mode:
    m.change_subsampling_conv_chunking_factor(1)
if "attn" in mode:
    m.change_attention_model("rel_pos")
if "local" in mode:
    m.change_attention_model("rel_pos_local_attn", [256, 256])
wav = "/opt/parakeet/samples/2086-149220-0033.wav"
t = time.time()
ctx = torch.autocast("cuda", dtype=torch.bfloat16) if "bf16" in mode else torch.autocast("cuda", enabled=False)
with torch.inference_mode(), ctx:
    out = m.transcribe([wav], batch_size=1, timestamps=True, verbose=False)
torch.cuda.synchronize()
print(mode, "OK", round(time.time()-t, 2), "s", repr(out[0].text), "peak MiB", torch.cuda.max_memory_allocated()//2**20, flush=True)
