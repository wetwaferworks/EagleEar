#!/bin/bash
# Installs NeMo ASR into /opt/parakeet/venv and lays out /opt/parakeet (run as root inside WSL)
set -euo pipefail
SRC=/mnt/r/repos/EagleEar/batch
mkdir -p /opt/parakeet/{venv,models,hf-cache,scripts,logs-wsl}
for f in transcribe.py env.sh; do tr -d '\r' < "$SRC/$f" > /opt/parakeet/scripts/$f; done
chmod +x /opt/parakeet/scripts/transcribe.py
ln -sfn /opt/parakeet/scripts/transcribe.py /opt/parakeet/transcribe.py
grep -q 'parakeet/scripts/env.sh' /opt/parakeet/venv/bin/activate || \
  printf '\n# Parakeet cache locations\nsource /opt/parakeet/scripts/env.sh\n' >> /opt/parakeet/venv/bin/activate
source /opt/parakeet/scripts/env.sh
/opt/parakeet/venv/bin/pip install 'nemo_toolkit[asr]==3.0.0' --extra-index-url https://download.pytorch.org/whl/cu126
/opt/parakeet/venv/bin/pip check || true
/opt/parakeet/venv/bin/python - <<'PY'
import torch, nemo
import nemo.collections.asr as a
print("nemo", nemo.__version__, "torch", torch.__version__, "cuda", torch.version.cuda, "available", torch.cuda.is_available())
PY
echo NEMO_DONE
