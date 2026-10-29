# Eagle Ear Talk bridge (2026-10-22)

Lets the Wet Wafer Works Boardroom page start/stop a Eagle Ear recording and get the text back,
straight into the chat box (never auto-sent). Only works on TheWorkstation.

- `eagle_bridge.py` listens on **127.0.0.1:1338 only**. It talks to the running widget over the widget's own
  Win32 IPC (`bridgestart` / `bridgestop` / `bridgewav <id>`, added to `widget/eagle_tray.py`).
- The widget records exactly like its mic button (same mic, model server, training-data log, widget box) and writes
  that one recording's text to `R:\data\EagleEar\bridge\result-<id>.json`; the bridge reads and deletes it.
  **No clipboard read.** The bridge never sees the model-server secret. Transcript text is never logged.
- Guards: Host header must be 127.0.0.1/localhost:1338; browser Origins other than the Boardroom
  (localhost/127.0.0.1 :1337, extra via `EAGLE_BRIDGE_ORIGINS`) get 403;
  `/start` `/stop` need a per-start token (`GET /token`, allowed origins only) in `X-Bridge-Token`.
  `/test-wav` is command-line only (refused for any browser Origin). A Talk left running stops after 5 min.

Start (login does this hidden via `agent-tools\startup\Early-Login.vbs`):

    R:\repos\EagleEar\widget\.venv\Scripts\pythonw.exe R:\repos\EagleEar\bridge\eagle_bridge.py

Round-trip test (bridge + widget running):

    R:\repos\EagleEar\widget\.venv\Scripts\python.exe R:\repos\EagleEar\bridge\eagle_bridge.py --test-wav C:\path\to\16bit.wav

Log: `R:\data\EagleEar\logs\bridge.log` (ids, lengths, refusals only).
