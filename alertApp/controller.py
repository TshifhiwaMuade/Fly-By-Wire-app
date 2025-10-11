import struct, time, sys, json, threading, webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Optional: joystick; if pygame not installed or no joystick, mouse mode still works
try:
    import pygame
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

# Optional: serial; can be disabled with --no-serial
try:
    import serial, serial.tools.list_ports
    PYSERIAL_OK = True
except Exception:
    PYSERIAL_OK = False

# ======== CONFIG (you can tweak) ========
PORT        = "COM10"     # Used if --serial is on and this exists; else tries first available
BAUD        = 115200
RATE_HZ     = 120
DEADZONE    = 0.06
START_BYTE  = 0xAA
WEB_PORT    = 8090

# ======== Runtime state ========
SER = None
INPUT_MODE = "auto"   # auto|joystick|mouse (can be overridden by CLI)
USE_SERIAL = False    # set via CLI
JOYSTICK_READY = False
BTN_INDEX = 0         # primary button index

# Latest values shown in web UI
LATEST = {
    "x":0.0, "y":0.0, "xi":0, "yi":0, "btn":0,
    "frame":"", "timestamp": time.time(), "simulation_mode": True
}

# Mouse override coming from web UI (if used)
OVERRIDE_ACTIVE = False
OVERRIDE_X = 0.0
OVERRIDE_Y = 0.0
OVERRIDE_BTN = 0

# ======== Helpers ========
def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v
def apply_deadzone(v, dz): return 0.0 if abs(v) < dz else v
def checksum(byte_seq): return (sum(byte_seq) & 0xFF)

def list_com_ports():
    if not PYSERIAL_OK: return []
    return list(serial.tools.list_ports.comports())

def try_open_serial(port, baud):
    global SER
    if not PYSERIAL_OK: return False
    try:
        s = serial.Serial(port, baud, timeout=0)
        time.sleep(2)
        s.reset_input_buffer()
        SER = s
        return True
    except Exception:
        SER = None
        return False

def update_latest(x, y, xi, yi, btn, frame, sim):
    global LATEST
    LATEST = {
        "x": float(x), "y": float(y),
        "xi": int(xi), "yi": int(yi),
        "btn": int(btn),
        "frame": str(frame),
        "timestamp": time.time(),
        "simulation_mode": bool(sim)
    }

# ======== Web visualiser & mouse controller ========
class Visualizer(SimpleHTTPRequestHandler):
    HTML = None

    @classmethod
    def page(cls):
        if cls.HTML: return cls.HTML
        cls.HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Aircraft Visualizer (Mouse/Joystick)</title>
<style>
 body{margin:0;padding:18px;font-family:system-ui,Segoe UI,Roboto,Arial;background:#0f1c3c;color:#fff}
 .row{display:flex;gap:18px;max-width:1100px;margin:0 auto;flex-wrap:wrap}
 .panel{flex:1 1 480px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);border-radius:14px;padding:16px}
 .title{font-weight:700;font-size:22px;margin:0 0 10px}
 .status{display:inline-block;padding:6px 12px;border-radius:999px;font-weight:700;margin:6px 0}
 .sim{background:rgba(255,107,107,.15);border:1px solid #ff6b6b;color:#ffb0b0}
 .ser{background:rgba(76,205,80,.15);border:1px solid #4ccd50;color:#b5f2ba}
 .air{position:relative;width:360px;height:360px;margin:0 auto 10px;border:2px solid rgba(255,255,255,.3);border-radius:12px;overflow:hidden;touch-action:none}
 .hln{position:absolute;top:50%;left:0;width:100%;height:2px;background:linear-gradient(90deg,transparent,#4ecdc4,transparent);transform:translateY(-50%)}
 .pitch{position:absolute;inset:0}
 .pl{position:absolute;left:0;width:100%;height:1px;background:rgba(255,255,255,.2)}
 .lab{position:absolute;left:8px;transform:translateY(-50%);font-size:12px;color:rgba(255,255,255,.7)}
 .plane{position:absolute;top:50%;left:50%;width:120px;height:40px;transform:translate(-50%,-50%);border-radius:10px;border:2px solid #ff6b6b;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.1);transition:transform .06s}
 .vals{display:grid;grid-template-columns:1fr 1fr;gap:10px}
 .v{background:rgba(0,0,0,.25);padding:10px;border-radius:10px;text-align:center;border:1px solid rgba(255,255,255,.1)}
 .vl{font-size:12px;opacity:.7;margin-bottom:4px}
 .vn{font-size:18px;font-weight:700;color:#4ecdc4}
 .btn{display:inline-flex;width:64px;height:64px;border-radius:50%;align-items:center;justify-content:center;border:2px solid rgba(255,255,255,.35);margin:8px auto 0;background:rgba(255,255,255,.08);font-weight:700;user-select:none;cursor:pointer}
 .btn.on{background:linear-gradient(45deg,#ff6b6b,#ff8e53);border-color:#fff;box-shadow:0 0 20px rgba(255,107,107,.5)}
 .hint{font-size:13px;opacity:.85;text-align:center;margin:10px 0 0}
</style>
</head><body>
  <div class="row">
    <div class="panel">
      <div class="title">Attitude & Mouse Control</div>
      <div id="mode" class="status sim">SIMULATION</div>
      <div class="air" id="pad">
        <div class="pitch" id="pitch"></div>
        <div class="hln"></div>
        <div id="plane" class="plane">✈</div>
      </div>
      <div class="hint">Drag inside the box to steer (X=roll, Y=pitch). Click “Button” to toggle BTN.</div>
      <div style="text-align:center">
        <div class="btn" id="btn">OFF</div>
      </div>
    </div>
    <div class="panel">
      <div class="title">Data</div>
      <div class="vals">
        <div class="v"><div class="vl">X (roll)</div><div id="x" class="vn">0.000</div></div>
        <div class="v"><div class="vl">Y (pitch)</div><div id="y" class="vn">0.000</div></div>
        <div class="v"><div class="vl">X int16</div><div id="xi" class="vn">0</div></div>
        <div class="v"><div class="vl">Y int16</div><div id="yi" class="vn">0</div></div>
        <div class="v"><div class="vl">BTN</div><div id="bv" class="vn">0</div></div>
      </div>
      <div class="v" style="margin-top:10px">
        <div class="vl">Frame</div>
        <div id="fr" style="word-break:break-all;font-family:ui-monospace,Consolas,monospace"></div>
      </div>
      <div class="vl" style="margin-top:6px">Last update: <span id="lu">Never</span></div>
    </div>
  </div>

<script>
 function lines(){
   const p=document.getElementById('pitch'); p.innerHTML='';
   for(let i=-150;i<=150;i+=30){
     const l=document.createElement('div'); l.className='pl'; l.style.top=(180+i)+'px';
     const t=document.createElement('div'); t.className='lab'; t.style.top=(180+i)+'px'; t.textContent=Math.abs(i/30*10)+'°';
     p.appendChild(l); p.appendChild(t);
   }
 }
 lines();

 function setPlane(x,y){
   const plane=document.getElementById('plane');
   plane.style.transform='translate(-50%,-50%) rotate('+(x*30)+'deg)';
   plane.style.top='calc(50% + '+(y*120)+'px)';
 }

 async function fetchData(){
   try{
     const r=await fetch('/data'); if(!r.ok) return;
     const d=await r.json();
     document.getElementById('x').textContent=d.x.toFixed(3);
     document.getElementById('y').textContent=d.y.toFixed(3);
     document.getElementById('xi').textContent=d.xi;
     document.getElementById('yi').textContent=d.yi;
     document.getElementById('bv').textContent=d.btn;
     document.getElementById('fr').textContent=d.frame;
     document.getElementById('lu').textContent=(new Date()).toLocaleTimeString();
     setPlane(d.x, d.y);
     const m=document.getElementById('mode');
     if(d.simulation_mode){ m.textContent='SIMULATION'; m.className='status sim'; }
     else { m.textContent='SERIAL'; m.className='status ser'; }
     const btn=document.getElementById('btn');
     if(d.btn===1){ btn.classList.add('on'); btn.textContent='ON'; } else { btn.classList.remove('on'); btn.textContent='OFF'; }
   }catch(_){}
 }

 // Mouse control inside the pad → sends override to Python
 const pad = document.getElementById('pad');
 let dragging=false;
 function norm(v, min, max){ return (v - min) / (max - min); }
 function clamp(v){ return Math.max(-1, Math.min(1, v)); }
 pad.addEventListener('pointerdown', e => { dragging=true; pad.setPointerCapture(e.pointerId); sendXY(e); });
 pad.addEventListener('pointermove', e => { if(dragging) sendXY(e); });
 pad.addEventListener('pointerup', e => { dragging=false; pad.releasePointerCapture(e.pointerId); });
 function sendXY(e){
   const r=pad.getBoundingClientRect();
   const nx = (e.clientX - r.left)/r.width;    // 0..1
   const ny = (e.clientY - r.top)/r.height;    // 0..1
   // Map to [-1..1]; center (0.5,0.5) is neutral. Invert Y (pull up = positive).
   const x = clamp((nx - 0.5) * 2.0);
   const y = clamp((0.5 - ny) * 2.0);
   fetch(`/override?x=${x.toFixed(4)}&y=${y.toFixed(4)}`);
 }

 const btnEl = document.getElementById('btn');
 btnEl.addEventListener('click', async ()=>{
   const on = btnEl.classList.contains('on') ? 0 : 1;
   await fetch(`/override?btn=${on}`);
 });

 setInterval(fetchData, 50); fetchData();
</script>
</body></html>"""
        return cls.HTML

    def do_GET(self):
        global OVERRIDE_ACTIVE, OVERRIDE_X, OVERRIDE_Y, OVERRIDE_BTN
        path = urlparse(self.path).path
        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type","text/html")
            self.end_headers()
            self.wfile.write(self.page().encode("utf-8"))
            return
        if path == "/data":
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            self.wfile.write(json.dumps(LATEST).encode("utf-8"))
            return
        if path == "/override":
            qs = parse_qs(urlparse(self.path).query)
            changed = False
            if "x" in qs:
                try:
                    OVERRIDE_X = float(qs["x"][0]); changed = True
                except: pass
            if "y" in qs:
                try:
                    OVERRIDE_Y = float(qs["y"][0]); changed = True
                except: pass
            if "btn" in qs:
                try:
                    OVERRIDE_BTN = 1 if int(qs["btn"][0]) else 0; changed = True
                except: pass
            if changed:
                OVERRIDE_ACTIVE = True
            self.send_response(200); self.end_headers()
            self.wfile.write(b"OK")
            return
        self.send_response(404); self.end_headers()

def start_web():
    try:
        httpd = HTTPServer(("", WEB_PORT), Visualizer)
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{WEB_PORT}")).start()
        httpd.serve_forever()
    except OSError:
        # If the port is busy, just run headless (still usable if joystick present)
        pass

# ======== Core loop ========
def run_loop():
    global JOYSTICK_READY
    t_delay = 1.0 / RATE_HZ

    # Joystick init if needed
    js = None
    if INPUT_MODE in ("auto","joystick") and PYGAME_OK:
        try:
            pygame.init(); pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                js = pygame.joystick.Joystick(0); js.init()
                JOYSTICK_READY = True
            else:
                JOYSTICK_READY = False
        except Exception:
            JOYSTICK_READY = False

    # Decide actual mode
    use_mouse = (INPUT_MODE == "mouse") or (INPUT_MODE == "auto" and not JOYSTICK_READY)
    simulation = (not USE_SERIAL or SER is None)

    while True:
        # Handle pygame events if using joystick
        if not use_mouse and js is not None and PYGAME_OK:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise KeyboardInterrupt

        # Read inputs
        if use_mouse and OVERRIDE_ACTIVE:
            x = clamp(OVERRIDE_X, -1.0, 1.0)
            y = clamp(OVERRIDE_Y, -1.0, 1.0)  # already inverted in page mapping
            btn = OVERRIDE_BTN
        elif not use_mouse and js is not None:
            x = clamp(apply_deadzone(js.get_axis(0), DEADZONE), -1.0, 1.0)
            y = clamp(apply_deadzone(js.get_axis(1), DEADZONE), -1.0, 1.0)
            y = -y  # invert Y (pull back = positive pitch)
            btn = 1 if (js.get_numbuttons() > BTN_INDEX and js.get_button(BTN_INDEX)) else 0
        else:
            # No source; keep neutral
            x = 0.0; y = 0.0; btn = 0

        xi = int(x * 32767)
        yi = int(y * 32767)

        payload = struct.pack("<BhhB", START_BYTE, xi, yi, btn)
        csum = checksum(payload[1:])
        frame = payload + bytes([csum])

        if USE_SERIAL and SER is not None:
            try:
                SER.write(frame)
            except Exception:
                pass

        update_latest(x, y, xi, yi, btn, frame, sim=(not USE_SERIAL or SER is None))
        time.sleep(t_delay)

# ======== Entrypoint / CLI ========
def main():
    global INPUT_MODE, USE_SERIAL

    # Minimal CLI parsing
    args = sys.argv[1:]
    INPUT_MODE = "auto"
    USE_SERIAL = False
    for i, a in enumerate(args):
        if a == "--mouse": INPUT_MODE = "mouse"
        elif a == "--joystick": INPUT_MODE = "joystick"
        elif a == "--auto": INPUT_MODE = "auto"
        elif a == "--serial": USE_SERIAL = True
        elif a.startswith("--port="): 
            globals()["PORT"] = a.split("=",1)[1]
        elif a.startswith("--baud="):
            globals()["BAUD"] = int(a.split("=",1)[1])

    # Serial setup (optional)
    if USE_SERIAL:
        ok = try_open_serial(PORT, BAUD)
        if not ok:
            ports = list_com_ports()
            if ports:
                try_open_serial(ports[0].device, BAUD)

    # Web
    threading.Thread(target=start_web, daemon=True).start()

    # Loop
    try:
        run_loop()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if SER and getattr(SER, "is_open", False):
                SER.close()
        except Exception:
            pass
        if PYGAME_OK:
            try: pygame.quit()
            except Exception: pass

if __name__ == "__main__":
    main()
