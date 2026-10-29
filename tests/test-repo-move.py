"""Log 50: post-move checks for Eagle Ear in the repo.
  M1 launch from the Start Menu shortcut -> window + model ready; paths (repo venv, data dir); no taskbar button
  M2 launch the shortcut again -> still one instance (single-instance mutex), window re-shown
  M3 hide (Esc path = hide()) -> hidden, still no taskbar button; quit -> no servers left
  M4 self-test: replay both samples through the live path; test training records go to
     <data_dir>\\test-runs\\... (a test folder under the data root; the real training set is not touched)"""
import json, os, re, subprocess, sys, time
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("EAGLE_EAR_DATA", r"R:\data\EagleEar")
W = os.path.join(REPO, "widget")
sys.path.insert(0, W)
import eagle_core as core
PY = os.path.join(W, ".venv", "Scripts", "python.exe")
APP = os.path.join(W, "eagle_ear.pyw")
WLOG = os.path.join(DATA, "logs", "widget.log")
STATE = os.path.join(DATA, "logs", "state.json")
LNK = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Eagle Ear.lnk")
TESTRUN = os.path.join(DATA, "test-runs", "2026-10-07-repo-move")
REAL_MANIFEST = os.path.join(DATA, "training-data", "manifest.jsonl")
SAMPLES = [os.path.join(DATA, "test-samples", f) for f in ("libri sample 16k mono.wav", "espeak sample 16k mono.wav")]
REF = ["Well, I don't wish to see it any more, observed Phebe, turning away her eyes. It is certainly very like the old portrait.",
       "Hello JD. This is a local transcription test running on the workstation graphics card. The bundle was a win."]
def p(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def lines(f):
    try: return sum(1 for l in open(f, encoding="utf-8") if l.strip())
    except FileNotFoundError: return 0
def procs():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*eagle_ear.pyw*' -and $_.CommandLine -notlike '*--cmd*' -and $_.CommandLine -notlike '*powershell*' } | "
        "ForEach-Object { $_.ProcessId.ToString() + ' | ' + $_.ExecutablePath + ' | ' + $_.CommandLine }"], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip()]
def vram(): return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip())
def servers(): return core._wsl(["bash", "-c", "pgrep -af live_server.py | grep -v pgrep || true"]).stdout.decode().strip()
class Log:
    def __init__(self): self.off = os.path.getsize(WLOG) if os.path.exists(WLOG) else 0
    def wait(self, pat, timeout):
        t0 = time.perf_counter(); rx = re.compile(pat)
        while time.perf_counter() - t0 < timeout:
            if os.path.exists(WLOG):
                with open(WLOG, encoding="utf-8", errors="replace") as f:
                    f.seek(self.off); chunk = f.read()
                for line in chunk.splitlines(True):
                    if not line.endswith("\n"): break
                    self.off += len(line.encode("utf-8"))
                    if rx.search(line): return line.strip(), time.perf_counter() - t0
            time.sleep(0.1)
        raise TimeoutError(pat)
def cmd(c): subprocess.run([PY, APP, "--cmd", c], timeout=30)
def state():
    cmd("dump"); time.sleep(0.7)
    with open(STATE, encoding="utf-8") as f: return json.load(f)
KEYS = ("engine", "visible", "data_dir", "training_dir", "app_dir", "tray_added", "hotkey_ok", "status")
def sk(st): return {k: st.get(k) for k in KEYS} | {k: v for k, v in st.items() if k in ("toolwindow", "appwindow", "topmost", "iswindowvisible")}
res = {"real_manifest_before": lines(REAL_MANIFEST)}
try:
    assert not procs(), "an instance is already running"
    os.makedirs(os.path.dirname(WLOG), exist_ok=True)
    # M1
    p("M1 launch from Start Menu shortcut"); L = Log(); t0 = time.perf_counter(); os.startfile(LNK)
    line0, _ = L.wait(r"started pid=", 30)
    line, _ = L.wait(r"engine ready", 240); t = time.perf_counter() - t0
    time.sleep(1); st = state()
    res["M1_shortcut"] = {"started": line0[20:], "launch_to_ready_s": round(t, 1), **sk(st), "procs": procs(), "vram_ready": vram()}
    p("M1", json.dumps(res["M1_shortcut"]))
    # M2
    p("M2 second launch -> single instance"); n1 = len(procs()); os.startfile(LNK); time.sleep(6)
    st = state(); res["M2_single_instance"] = {"instance_procs_before": n1, "instance_procs_after": len(procs()), "visible": st.get("visible")}
    p("M2", json.dumps(res["M2_single_instance"]))
    # M3
    p("M3 hide + quit"); cmd("hide"); time.sleep(1); st = state()
    res["M3_hide_quit"] = {"after_hide": sk(st)}
    cmd("quit"); time.sleep(8)
    res["M3_hide_quit"].update({"procs_after_quit": procs(), "servers_after_quit": servers(), "vram_after_quit": vram()})
    p("M3", json.dumps(res["M3_hide_quit"]))
    # M4
    p("M4 self-test replay"); os.makedirs(TESTRUN, exist_ok=True)
    td = os.path.join(TESTRUN, "training-data"); out = os.path.join(TESTRUN, "selftest.json")
    r = subprocess.run([PY, APP, "--selftest", out, "--no-save", "--training-dir", td, "--record-seconds", "1", "--replay"] + SAMPLES, timeout=400)
    with open(out, encoding="utf-8") as f: stt = json.load(f)
    rt = stt.get("replay_text", "")
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower()).split()
    res["M4_selftest"] = {"rc": r.returncode, "ok": stt.get("ok"), "engine_ready_s": stt.get("engine_ready_s"), "replay_text": rt,
                          "replay_words_match_refs": norm(rt) == norm(" ".join(REF)),
                          "latency": stt.get("latency_end_of_speech_to_text_ms"), "clipboard_ok": stt.get("clipboard_matches_box_after_replay"),
                          "test_training_records": lines(os.path.join(td, "manifest.jsonl")),
                          "test_training_wavs": len(os.listdir(os.path.join(td, "audio"))) if os.path.isdir(os.path.join(td, "audio")) else 0,
                          "real_manifest_after": lines(REAL_MANIFEST), "servers_after": servers(), "procs_after": procs()}
    p("M4", json.dumps(res["M4_selftest"]))
    res["data_logs"] = sorted(os.listdir(os.path.join(DATA, "logs")))
except Exception:
    import traceback; res["error"] = traceback.format_exc(); p("ERROR", res["error"]); subprocess.run([PY, APP, "--cmd", "quit"])
print("RESULT " + json.dumps(res, indent=1))
