# controller.py — Visualiser + Controller + (optional) Arduino serial
# ---------------------------------------------------------------
# Features:
# - Starts a local web UI (attitude indicator) and auto-opens your browser.
# - Inputs: joystick (preferred) or browser mouse (/override).
# - Serial optional: enable with --serial (and --port=COM10).
# - Fixed-step loop, invert-Y (pull = nose up), deadzone, send-on-change.

import struct, time, sys, json, threading, webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Optional: joystick
try:
    import pygame
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

# Optional: serial
try:
    import serial, serial.tools.list_ports
    PYSERIAL_OK = True
except Exception:
    PYSERIAL_OK = False

# ================== CONFIG (defaults; can be overridden by CLI) ==================
PORT        = "COM10"
BAUD        = 115200
RATE_HZ     = 240
DEADZONE    = 0.06
START_BYTE  = 0xAA
WEB_PORT    = 8090
HOST        = "127.0.0.1"

# ================== RUNTIME STATE ==================
SER = None
INPUT_MODE = "auto"     # auto | joystick | mouse
USE_SERIAL = False
JOYSTICK_READY = False
BTN_INDEX = 0

# Latest values for the web UI
LATEST = {
    "x": 0.0, "y": 0.0, "xi": 0, "yi": 0, "btn": 0,
    "frame": "", "timestamp": time.time(), "simulation_mode": True
}

# Browser mouse override
OVERRIDE_ACTIVE = False
OVERRIDE_X = 0.0
OVERRIDE_Y = 0.0
OVERRIDE_BTN = 0

# ================== HELPERS ==================
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
        s = serial.Serial(port, baud, timeout=0, write_timeout=0)
        time.sleep(1.5)               # let the MCU settle
        s.reset_input_buffer()
        SER = s
        return True
    except Exception:
        SER = None
        return False

def update_latest(x, y, xi, yi, btn, frame, sim):
    LATEST.update({
        "x": float(x), "y": float(y),
        "xi": int(xi), "yi": int(yi),
        "btn": int(btn),
        "frame": str(frame),
        "timestamp": time.time(),
        "simulation_mode": bool(sim)
    })

# ================== WEB VISUALISER ==================
class Visualizer(SimpleHTTPRequestHandler):
    HTML = None

    @classmethod
    def page(cls):
        if cls.HTML: return cls.HTML
        cls.HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Fly-By-Wire Visualizer</title>
<style>
  :root { --gold:#FFD700; --bg:#1a1a1a; --sky:#7EC0EE; --ground:#8B4513; --fg:#fff; }
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial}
  header{padding:16px 20px;text-align:center}
  h1{margin:0;font-size:28px;letter-spacing:1px;color:var(--gold);text-transform:uppercase;text-shadow:0 0 8px rgba(255,215,0,.25)}
  .status{margin-top:8px;display:inline-block;padding:6px 12px;border-radius:999px;border:1px solid #333;background:#00000040;font-weight:700;font-size:12px}
  .row{max-width:1200px;margin:0 auto;padding:16px;display:grid;gap:18px;grid-template-columns:1fr 1fr}
  @media (max-width:1000px){.row{grid-template-columns:1fr}}
  .panel{background:#00000040;border:1px solid #333;border-radius:14px;padding:16px}
  .att-wrap{display:flex;justify-content:center}
  .att{width:800px;height:800px;max-width:min(92vw,800px);max-height:min(92vw,800px);aspect-ratio:1;border-radius:50%;position:relative;overflow:hidden;border:15px solid #333;box-shadow:inset 0 0 40px rgba(0,0,0,.5)}
  .horizon{position:absolute;width:1600px;height:1600px;top:50%;left:50%;transform-origin:center;transition:transform .08s linear}
  .sky{position:absolute;inset:0 0 50% 0;background:var(--sky)}
  .ground{position:absolute;inset:50% 0 0 0;background:var(--ground)}
  .pitch-lines{position:absolute;inset:0}
  .pitch-line{position:absolute;left:50%;width:150px;height:2px;background:#fff;transform:translateX(-50%)}
  .pitch-line.thin{width:100px;opacity:.75}
  .pitch-text{position:absolute;left:calc(50% + 110px);transform:translateY(-50%);font-size:14px;opacity:.9}
  .ref{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:10}
  .ac{width:200px;height:200px;position:relative}
  .ac::before{content:"";position:absolute;width:240px;height:12px;background:var(--gold);top:50%;left:50%;transform:translate(-50%,-50%)}
  .ac::after{content:"";position:absolute;width:12px;height:12px;background:var(--gold);border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%)}
  .roll-ring{position:absolute;inset:0}
  .roll-marker{position:absolute;left:50%;width:2px;height:15px;background:#fff;transform-origin:bottom}
  .roll-marker.major{height:20px}
  .values{font-family:ui-monospace,Consolas,monospace;text-align:center;margin-top:12px;background:#00000055;border:1px solid #333;border-radius:10px;padding:12px;font-size:18px}
  .controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center;margin-top:10px}
  .btn{cursor:pointer;border:1px solid #444;padding:8px 12px;border-radius:10px;background:#101010;color:#eee;font-weight:600}
  .btn.on{outline:2px solid var(--gold);box-shadow:0 0 10px rgba(255,215,0,.35)}
  .kv{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .k{background:#00000040;border:1px solid #333;border-radius:10px;padding:10px;text-align:center}
  .k .l{opacity:.8;font-size:12px;margin-bottom:4px}
  .k .v{font-family:ui-monospace,Consolas,monospace;font-weight:700}
</style>
</head>
<body>
  <header>
    <h1>Fly-By-Wire System Visualizer</h1>
    <div id="status" class="status">Connecting…</div>
  </header>

  <div class="row">
    <div class="panel">
      <div class="att-wrap">
        <div class="att" id="pad">
          <div class="horizon" id="horizon">
            <div class="sky"></div>
            <div class="ground"></div>
            <div class="pitch-lines" id="pitchLines"></div>
          </div>
          <div class="ref"><div class="ac"></div></div>
          <div class="roll-ring" id="rollRing"></div>
        </div>
      </div>
      <div class="values" id="values">Pitch: 0° | Roll: 0°</div>
      <div class="controls">
        <button id="mouseBtn" class="btn">Enable Mouse Control</button>
        <button id="btnToggle" class="btn">BTN OFF</button>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">Data</h3>
      <div class="kv">
        <div class="k"><div class="l">X (roll)</div><div class="v" id="xv">0.000</div></div>
        <div class="k"><div class="l">Y (pitch)</div><div class="v" id="yv">0.000</div></div>
        <div class="k"><div class="l">X int16</div><div class="v" id="x16">0</div></div>
        <div class="k"><div class="l">Y int16</div><div class="v" id="y16">0</div></div>
        <div class="k"><div class="l">Button</div><div class="v" id="bval">0</div></div>
        <div class="k" style="grid-column:1/3"><div class="l">Frame</div><div class="v" id="frame" style="word-break:break-all"></div></div>
      </div>
    </div>
  </div>

<script>
  function clamp(v,min,max){ return v<min?min:v>max?max:v; }

  function buildPitchLines(){
    const p=document.getElementById('pitchLines'); p.innerHTML='';
    for(let i=-90;i<=90;i+=10){
      if(i===0) continue;
      const line=document.createElement('div');
      line.className='pitch-line '+(i%20===0?'':'thin');
      line.style.top=`${50+i}%`;
      const txt=document.createElement('div');
      txt.className='pitch-text';
      txt.textContent=Math.abs(i)+'°';
      txt.style.top=`${50+i}%`;
      p.appendChild(line); p.appendChild(txt);
    }
  }

  function buildRollMarkers(){
    const ring=document.getElementById('rollRing'); ring.innerHTML='';
    for(let i=-60;i<=60;i+=10){
      const d=document.createElement('div');
      d.className='roll-marker '+(i%30===0?'major':'');
      d.style.transform=`rotate(${i}deg)`;
      ring.appendChild(d);
    }
  }

  let vis={x:0,y:0}, tgt={x:0,y:0}, btnState=0, mouseMode=false;

  function updateAttitude(d){
    const rollDeg = -d.x * 60;    // ±60°
    const pitchDeg =  d.y * 45;   // ±45°
    const horizon=document.getElementById('horizon');
    horizon.style.transform = `translate(-50%,-50%) rotate(${rollDeg}deg) translateY(${pitchDeg}%)`;
    document.getElementById('values').textContent = `Pitch: ${(-pitchDeg).toFixed(1)}° | Roll: ${rollDeg.toFixed(1)}°`;
    if(document.getElementById('xv').textContent !== d.x.toFixed(3)) document.getElementById('xv').textContent = d.x.toFixed(3);
    if(document.getElementById('yv').textContent !== d.y.toFixed(3)) document.getElementById('yv').textContent = d.y.toFixed(3);
    document.getElementById('x16').textContent = d.xi;
    document.getElementById('y16').textContent = d.yi;
    document.getElementById('bval').textContent = d.btn;
    document.getElementById('frame').textContent = d.frame;
    const s = document.getElementById('status');
    s.textContent = d.simulation_mode ? "SIMULATION" : "SERIAL";
  }

  async function fetchData(){
    try{
      const r = await fetch('/data'); if(!r.ok) return;
      const d = await r.json(); tgt.x = d.x; tgt.y = d.y; btnState = d.btn; updateAttitude(d);
    }catch(e){}
  }

  (function anim(){ vis.x += (tgt.x - vis.x) * 0.35; vis.y += (tgt.y - vis.y) * 0.35; requestAnimationFrame(anim); })();

  const mouseBtn = document.getElementById('mouseBtn');
  const pad = document.getElementById('pad');
  let dragging=false;
  function setMouseUI(on){ mouseBtn.classList.toggle('on', on); mouseBtn.textContent = on ? "Disable Mouse Control" : "Enable Mouse Control"; }
  mouseBtn.addEventListener('click',()=>{ mouseMode=!mouseMode; setMouseUI(mouseMode); });

  function sendOverride(x,y){ fetch(`/override?x=${x.toFixed(4)}&y=${y.toFixed(4)}`).catch(()=>{}); }

  pad.addEventListener('pointerdown', e=>{ if(!mouseMode) return; dragging=true; pad.setPointerCapture(e.pointerId); moveFromEvent(e); });
  pad.addEventListener('pointermove', e=>{ if(!mouseMode||!dragging) return; moveFromEvent(e); });
  pad.addEventListener('pointerup',   e=>{ if(!mouseMode) return; dragging=false; pad.releasePointerCapture(e.pointerId); });

  function moveFromEvent(e){
    const r = pad.getBoundingClientRect();
    const nx = (e.clientX - r.left) / r.width;
    const ny = (e.clientY - r.top)  / r.height;
    const x  = clamp((nx - 0.5) * 2.0, -1, 1);
    const y  = clamp((0.5 - ny) * 2.0, -1, 1); // invert Y so up = +
    sendOverride(x,y);
  }

  document.getElementById('btnToggle').addEventListener('click', ()=>{ const next=(btnState===1)?0:1; fetch(`/override?btn=${next}`).catch(()=>{}); });

  buildPitchLines(); buildRollMarkers(); setMouseUI(false); setInterval(fetchData, 16); fetchData();
</script>
</body>
</html>"""
        return cls.HTML

    def do_GET(self):
        global OVERRIDE_ACTIVE, OVERRIDE_X, OVERRIDE_Y, OVERRIDE_BTN
        path = urlparse(self.path).path
        if path == "/":
            self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
            self.wfile.write(self.page().encode("utf-8")); return
        if path == "/data":
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
            self.wfile.write(json.dumps(LATEST).encode("utf-8")); return
        if path == "/override":
            qs = parse_qs(urlparse(self.path).query)
            changed = False
            if "x" in qs:
                try: OVERRIDE_X = float(qs["x"][0]); changed = True
                except: pass
            if "y" in qs:
                try: OVERRIDE_Y = float(qs["y"][0]); changed = True
                except: pass
            if "btn" in qs:
                try: OVERRIDE_BTN = 1 if int(qs["btn"][0]) else 0; changed = True
                except: pass
            if changed: OVERRIDE_ACTIVE = True
            self.send_response(200); self.end_headers(); self.wfile.write(b"OK"); return
        self.send_response(404); self.end_headers()

def start_web_server(host=HOST, port=WEB_PORT, auto_open=True):
    httpd = HTTPServer((host, port), Visualizer)
    if auto_open:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    httpd.serve_forever()

# ================== CORE LOOP ==================
def run_loop():
    global JOYSTICK_READY
    # Fixed-step cadence
    t_step = 1.0 / RATE_HZ
    next_t = time.perf_counter() + t_step

    # Joystick setup (if desired)
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

    # Decide actual input source
    use_mouse = (INPUT_MODE == "mouse") or (INPUT_MODE == "auto" and not JOYSTICK_READY)
    simulation = (not USE_SERIAL or SER is None)

    prev_xi = prev_yi = prev_btn = None

    while True:
        # keep pygame event queue fresh if using joystick
        if not use_mouse and js is not None and PYGAME_OK:
            try: pygame.event.pump()
            except: pass

        # Read inputs
        if use_mouse and OVERRIDE_ACTIVE:
            x = clamp(OVERRIDE_X, -1.0, 1.0)
            y = clamp(OVERRIDE_Y, -1.0, 1.0)       # already inverted by page mapping
            btn = OVERRIDE_BTN
        elif not use_mouse and js is not None:
            x = clamp(apply_deadzone(js.get_axis(0), DEADZONE), -1.0, 1.0)
            y = clamp(apply_deadzone(js.get_axis(1), DEADZONE), -1.0, 1.0)
            y = -y                                  # invert Y (pull back = positive)
            btn = 1 if (js.get_numbuttons() > BTN_INDEX and js.get_button(BTN_INDEX)) else 0
        else:
            x = 0.0; y = 0.0; btn = 0

        xi = int(x * 32767)
        yi = int(y * 32767)

        payload = struct.pack("<BhhB", START_BYTE, xi, yi, btn)
        csum = checksum(payload[1:])
        frame = payload + bytes([csum])

        # send on change only
        changed = (xi != prev_xi) or (yi != prev_yi) or (btn != prev_btn)
        if changed and USE_SERIAL and SER is not None:
            try:
                SER.write(frame)
            except Exception:
                pass
            prev_xi, prev_yi, prev_btn = xi, yi, btn

        update_latest(x, y, xi, yi, btn, frame, sim=(not USE_SERIAL or SER is None))

        # fixed-step sleep
        now = time.perf_counter()
        sleep_s = next_t - now
        if sleep_s > 0:
            time.sleep(sleep_s)
        next_t += t_step

# ================== ENTRYPOINT / CLI ==================
def main():
    global INPUT_MODE, USE_SERIAL, PORT, BAUD, WEB_PORT

    # Minimal CLI
    args = sys.argv[1:]
    INPUT_MODE = "auto"
    USE_SERIAL = False
    auto_open = True

    for a in args:
        if a == "--mouse": INPUT_MODE = "mouse"
        elif a == "--joystick": INPUT_MODE = "joystick"
        elif a == "--auto": INPUT_MODE = "auto"
        elif a == "--serial": USE_SERIAL = True
        elif a == "--no-browser": auto_open = False
        elif a.startswith("--port="): PORT = a.split("=",1)[1]
        elif a.startswith("--baud="): BAUD = int(a.split("=",1)[1])
        elif a.startswith("--web-port="): WEB_PORT = int(a.split("=",1)[1])

    # Serial setup if requested
    if USE_SERIAL:
        ok = try_open_serial(PORT, BAUD)
        if not ok:
            ports = list_com_ports()
            if ports:
                try_open_serial(ports[0].device, BAUD)

    # Start web UI (auto-open browser)
    threading.Thread(target=start_web_server, kwargs={"host":HOST, "port":WEB_PORT, "auto_open":auto_open}, daemon=True).start()

    # Run controller loop
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
