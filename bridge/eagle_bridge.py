"""Eagle Ear <-> Boardroom Talk bridge (2026-10-22).

Lets the Wet Wafer Works Boardroom page (opened on TheWorkstation) start and stop a Eagle Ear recording
and get the transcript back directly - no app switching, no clipboard.

  page  --HTTP 127.0.0.1:1338-->  this bridge  --Win32 IPC (bridgestart/bridgestop <id>)-->  running widget
  widget records exactly like its own mic button (same mic, model server, training log) and writes the text of
  that one recording to <data>\\bridge\\result-<id>.json; the bridge reads it, deletes it, returns it.

Run:  widget\\.venv\\Scripts\\pythonw.exe bridge\\eagle_bridge.py   (from the repo root)
Test: ...\\python.exe eagle_bridge.py --test-wav "C:\\path\\sample.wav"   (bridge must be running)

Guards: binds 127.0.0.1 only; Host must be 127.0.0.1/localhost:1338 (no DNS rebinding); browser requests must
come from an allowed Boardroom origin (CORS + explicit 403 otherwise); start/stop need a per-start token that only
an allowed origin can fetch (GET /token), sent in the X-Bridge-Token header (forces a CORS preflight).
Never logs transcript text, only lengths. Never touches the EagleEar server secret.
"""
import ctypes
import json
import os
import secrets
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "widget"))
import eagle_tray as trayw  # noqa: E402

PORT = 1338
DATA_DIR = os.environ.get("EAGLE_EAR_DATA") or r"R:\data\EagleEar"
BRIDGE_DIR = os.path.join(DATA_DIR, "bridge")
STATE_PATH = os.path.join(DATA_DIR, "logs", "state.json")
LOG_PATH = os.path.join(DATA_DIR, "logs", "bridge.log")
ORIGINS = {"http://localhost:1337", "http://127.0.0.1:1337"}   # add LAN/tailnet origins via EAGLE_BRIDGE_ORIGINS
ORIGINS |= {o.strip().rstrip("/") for o in os.environ.get("EAGLE_BRIDGE_ORIGINS", "").split(",") if o.strip()}
HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
TOKEN = secrets.token_urlsafe(24)       # per start; only handed to allowed origins
MAX_TALK_S = 300                        # a Talk left running (tab closed) is stopped after 5 min
LOCK = threading.Lock()
CUR = {"id": None, "t": 0.0}


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def widget_running():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenMutexW.restype = ctypes.c_void_p
    h = k32.OpenMutexW(0x00100000, False, "Local\\EagleEar.Widget")
    if h:
        k32.CloseHandle(ctypes.c_void_p(h))
    return bool(h)


def widget_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return {"engine": d.get("engine"), "recording": d.get("recording"), "parked": bool(d.get("parked"))}
    except Exception:
        return {}


def new_id():
    return secrets.randbelow(2 ** 30 - 1) + 1


def wait_result(rid, want, timeout):
    p = os.path.join(BRIDGE_DIR, f"result-{rid}.json")
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("state") in want:
                os.remove(p)
                return d
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    return None


def purge_stale(max_age_s=300):
    """Result/request files a timed-out Talk left behind hold transcript text: don't let them pile up."""
    try:
        now = time.time()
        for f in os.listdir(BRIDGE_DIR):
            if f.startswith(("result-", "req-")) and now - os.path.getmtime(os.path.join(BRIDGE_DIR, f)) > max_age_s:
                os.remove(os.path.join(BRIDGE_DIR, f))
    except OSError:
        pass


def start(cmd="bridgestart", wav=None):
    if not widget_running():
        return 503, {"error": "Eagle Ear isn't running. Start it from the tray or the Start menu."}
    with LOCK:
        if CUR["id"]:
            return 409, {"error": "A Talk recording is already running."}
        rid = new_id()
        os.makedirs(BRIDGE_DIR, exist_ok=True)
        purge_stale()
        if wav:
            with open(os.path.join(BRIDGE_DIR, f"req-{rid}.json"), "w", encoding="utf-8") as f:
                json.dump({"wav": wav}, f)
        if not trayw.send_ipc(cmd, rid):
            return 503, {"error": "Couldn't reach the Eagle Ear widget."}
        d = wait_result(rid, ("recording", "error"), 10)
        if wav:
            try:
                os.remove(os.path.join(BRIDGE_DIR, f"req-{rid}.json"))
            except OSError:
                pass
        if not d:
            return 504, {"error": "Eagle Ear didn't answer."}
        if d["state"] == "error":
            return 409, {"error": d.get("error") or "Couldn't start recording."}
        CUR.update(id=rid, t=time.monotonic())
    log(f"talk {rid} started ({'wav' if wav else 'mic'}), engine {d.get('engine')}")
    return 200, {"state": "recording", "id": rid, "engine": d.get("engine")}


def stop(rid=None, auto=False):
    with LOCK:
        rid = rid or CUR["id"]
        if not rid or rid != CUR["id"]:
            return 409, {"error": "No Talk recording is running."}
        trayw.send_ipc("bridgestop", rid)
        d = wait_result(rid, ("done", "error"), 150)
        CUR.update(id=None, t=0.0)
    if not d:
        log(f"talk {rid}: no result")
        return 504, {"error": "Transcription timed out - the text stays in the Eagle Ear widget."}
    text = d.get("text") or ""
    log(f"talk {rid} {'auto-stopped' if auto else 'stopped'}: {d['state']}, {len(text)} chars")
    if d["state"] == "error":
        return 200, {"text": text, "warning": d.get("error")}
    return 200, {"text": text}


def watchdog():
    while True:
        time.sleep(5)
        if CUR["id"] and time.monotonic() - CUR["t"] > MAX_TALK_S:
            stop(auto=True)


class H(BaseHTTPRequestHandler):
    server_version = "EagleBridge/1"

    def log_message(self, fmt, *a):
        pass

    def _origin(self):
        return self.headers.get("Origin")

    def _send(self, code, obj=None):
        body = b"" if obj is None else json.dumps(obj).encode()
        self.send_response(code)
        o = self._origin()
        if o in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "X-Bridge-Token, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")
            if self.headers.get("Access-Control-Request-Private-Network"):
                self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")
        if obj is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _guard(self, need_token=False):
        if self.headers.get("Host", "") not in HOSTS:
            self._send(403, {"error": "bad host"})
            return False
        o = self._origin()
        if o is not None and o not in ORIGINS:
            log(f"refused origin {o[:80]!r} {self.command} {self.path}")
            self._send(403, {"error": "origin not allowed"})
            return False
        if need_token and not secrets.compare_digest(self.headers.get("X-Bridge-Token", ""), TOKEN):
            self._send(403, {"error": "bad token"})
            return False
        return True

    def do_OPTIONS(self):
        if self._guard():
            self._send(204)

    def do_GET(self):
        if not self._guard():
            return
        if self.path == "/health":
            self._send(200, {"ok": True, "widget": widget_running(), "talk": bool(CUR["id"]), **widget_state()})
        elif self.path == "/token":
            self._send(200, {"token": TOKEN})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._guard(need_token=True):
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(min(n, 4096)) or b"{}") if n else {}
        except ValueError:
            body = {}
        if self.path == "/start":
            self._send(*start())
        elif self.path == "/stop":
            self._send(*stop(body.get("id")))
        elif self.path == "/test-wav" and self._origin() is None:   # command line only, never a browser
            wav = str(body.get("wav") or "")
            if not (wav.lower().endswith(".wav") and os.path.isfile(wav)):
                self._send(400, {"error": "wav must be an existing .wav file"})
            else:
                self._send(*start("bridgewav", wav))
        else:
            self._send(404, {"error": "not found"})


def main():
    if "--test-wav" in sys.argv:
        path = sys.argv[sys.argv.index("--test-wav") + 1]
        base = f"http://127.0.0.1:{PORT}"
        tok = json.load(urllib.request.urlopen(base + "/token"))["token"]
        hdr = {"X-Bridge-Token": tok, "Content-Type": "application/json"}
        r = urllib.request.Request(base + "/test-wav", json.dumps({"wav": os.path.abspath(path)}).encode(), hdr)
        t0 = time.time()
        print("start:", json.load(urllib.request.urlopen(r)))
        import wave
        with wave.open(path, "rb") as w:
            time.sleep(w.getnframes() / w.getframerate() + 1.5)  # the widget plays it in real time
        r = urllib.request.Request(base + "/stop", b"{}", hdr)     # the widget feeds the WAV, then finishes
        out = json.load(urllib.request.urlopen(r, timeout=200))
        print(json.dumps(out, ensure_ascii=False))
        print(f"round trip {time.time() - t0:.1f}s")
        return
    os.makedirs(BRIDGE_DIR, exist_ok=True)
    purge_stale(0)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=watchdog, daemon=True).start()
    log(f"bridge listening on 127.0.0.1:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
