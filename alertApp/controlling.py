#!/usr/bin/env python3
# joystick_tx_with_visualiser.py
# == Your pc_joystick_tx.py behaviour + a non-intrusive web visualiser ==
import struct, time, sys, threading, json, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import pygame
import serial

# === CONFIG (identical defaults) ===
PORT      = "COM11"
BAUD      = 115200
RATE_HZ   = 100
DEADZONE  = 0.05
START     = 0xAA
WEB_HOST  = "127.0.0.1"
WEB_PORT  = 8090

# === Helpers (identical) ===
def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v
def apply_deadzone(v, dz): return 0.0 if abs(v) < dz else v
def checksum(bytes_): return sum(bytes_) & 0xFF

# === Shared state for the visualiser (read-only unless you toggle Mouse Control on the page) ===
LATEST = {
    "x":0.0, "y":0.0, "xi":0, "yi":0, "btn":0,
    "frame":"", "timestamp": time.time(), "simulation_mode": False
}
OVERRIDE = {"enabled": False, "x":0.0, "y":0.0, "btn":0}

# === Visualiser (minimal server; HTML uses no f-strings) ===
INDEX_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Fly-By-Wire Visualiser</title>
<style>
:root { --gold:#FFD700; --bg:#1a1a1a; --sky:#7EC0EE; --ground:#8B4513; --fg:#fff; }
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial}
header{padding:16px 20px;text-align:center}
h1{margin:0;font-size:28px;letter-spacing:1px;color:var(--gold);text-transform:uppercase}
.status{margin-top:8px;display:inline-block;padding:6px 12px;border-radius:999px;border:1px solid #333;background:#00000040;font-weight:700;font-size:12px}
.row{max-width:1100px;margin:0 auto;padding:16px;display:grid;gap:18px;grid-template-columns:1fr 1fr}
@media (max-width:1000px){.row{grid-template-columns:1fr}}
.panel{background:#00000040;border:1px solid #333;border-radius:14px;padding:16px}
.att-wrap{display:flex;justify-content:center}
.att{width:700px;height:700px;max-width:min(92vw,700px);max-height:min(92vw,700px);aspect-ratio:1;border-radius:50%;position:relative;overflow:hidden;border:15px solid #333}
.horizon{position:absolute;width:1400px;height:1400px;top:50%;left:50%;transform-origin:center;transition:transform .08s linear}
.sky{position:absolute;inset:0 0 50% 0;background:var(--sky)}
.ground{position:absolute;inset:50% 0 0 0;background:var(--ground)}
.pitch-lines{position:absolute;inset:0}
.pitch-line{position:absolute;left:50%;width:140px;height:2px;background:#fff;transform:translateX(-50%)}
.pitch-line.thin{width:90px;opacity:.75}
.pitch-text{position:absolute;left:calc(50% + 100px);transform:translateY(-50%);font-size:13px;opacity:.9}
.ref{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:10}
.ac{width:200px;height:200px;position:relative}
.ac::before{content:"";position:absolute;width:240px;height:12px;background:var(--gold);top:50%;left:50%;transform:translate(-50%,-50%)}
.ac::after{content:"";position:absolute;width:12px;height:12px;background:var(--gold);border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%)}
.values{font-family:ui-monospace,Consolas,monospace;text-align:center;margin-top:12px;background:#00000055;border:1px solid #333;border-radius:10px;padding:10px;font-size:16px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center;margin-top:10px}
.btn{cursor:pointer;border:1px solid #444;padding:8px 12px;border-radius:10px;background:#101010;color:#eee;font-weight:600}
.btn.on{outline:2px solid var(--gold)}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.k{background:#00000040;border:1px solid #333;border-radius:10px;padding:10px;text-align:center}
.k .l{opacity:.8;font-size:12px;margin-bottom:4px}
.k .v{font-family:ui-monospace,Consolas,monospace;font-weight:700}
</style></head>
<body>
<header>
  <h1>Fly-By-Wire Visualiser</h1>
  <div id="status" class="status">SERIAL</div>
</header>

<div class="row">
  <div class="panel">
    <div class="att-wrap">
      <div class="att" id="pad">
        <div class="horizon" id="horizon">
          <div class="sky"></div><div class="ground"></div><div class="pitch-lines" id="pitchLines"></div>
        </div>
        <div class="ref"><div class="ac"></div></div>
      </div>
    </div>
    <div class="values" id="values">Pitch: 0° | Roll: 0°</div>
    <div class="controls"><button id="mouseBtn" class="btn">Enable Mouse Control</button></div>
  </div>

  <div class="panel">
    <h3 style="margin-top:0">Data</h3>
    <div class="kv">
      <div class="k"><div class="l">X (roll)</div><div class="v" id="xv">0.000</div></div>
      <div class="k"><div class="l">Y (pitch)</div><div class="v" id="yv">0.000</div></div>
      <div class="k"><div class="l">X int16</div><div class="v" id="x16">0</div></div>
      <div class="k"><div class="l">Y int16</div><div class="v" id="y16">0</div></div>
      <div class="k" style="grid-column:1/3"><div class="l">Frame</div><div class="v" id="frame" style="word-break:break-all"></div></div>
    </div>
  </div>
</div>

<script>
function clamp(v,min,max){ return v<min?min:v>max?max:v; }
function buildPitchLines(){ const p=document.getElementById('pitchLines'); p.innerHTML='';
  for(let i=-90;i<=90;i+=10){ if(i===0) continue;
    const line=document.createElement('div'); line.className='pitch-line '+(i%20===0?'':'thin'); line.style.top=`${50+i}%`;
    const txt=document.createElement('div'); txt.className='pitch-text'; txt.textContent=Math.abs(i)+'°'; txt.style.top=`${50+i}%`;
    p.appendChild(line); p.appendChild(txt);
  }
}
let mouseMode=false, dragging=false;
function setMouseUI(on){ const b=document.getElementById('mouseBtn'); b.classList.toggle('on',on); b.textContent= on?"Disable Mouse Control":"Enable Mouse Control"; }
document.getElementById('mouseBtn').addEventListener('click',()=>{ mouseMode=!mouseMode; setMouseUI(mouseMode); fetch('/override?enabled='+(mouseMode?1:0)).catch(()=>{}); });

const pad=document.getElementById('pad');
pad.addEventListener('pointerdown', e=>{ if(!mouseMode) return; dragging=true; pad.setPointerCapture(e.pointerId); moveFromEvent(e); });
pad.addEventListener('pointermove', e=>{ if(!mouseMode||!dragging) return; moveFromEvent(e); });
pad.addEventListener('pointerup',   e=>{ if(!mouseMode) return; dragging=false; pad.releasePointerCapture(e.pointerId); });

function moveFromEvent(e){
  const r=pad.getBoundingClientRect();
  const nx=(e.clientX-r.left)/r.width; const ny=(e.clientY-r.top)/r.height;
  const x=clamp((nx-0.5)*2.0,-1,1); const y=clamp((0.5-ny)*2.0,-1,1); // invert Y so up=+
  fetch(`/override?x=${x.toFixed(4)}&y=${y.toFixed(4)}`).catch(()=>{});
}

function update(d){
  const rollDeg = -d.x * 60, pitchDeg =  d.y * 45;
  const h=document.getElementById('horizon');
  h.style.transform = `translate(-50%,-50%) rotate(${rollDeg}deg) translateY(${pitchDeg}%)`;
  document.getElementById('values').textContent = `Pitch: ${(-pitchDeg).toFixed(1)}° | Roll: ${rollDeg.toFixed(1)}°`;
  document.getElementById('xv').textContent = d.x.toFixed(3);
  document.getElementById('yv').textContent = d.y.toFixed(3);
  document.getElementById('x16').textContent = d.xi;
  document.getElementById('y16').textContent = d.yi;
  document.getElementById('frame').textContent = d.frame;
}

async function poll(){
  try{ const r=await fetch('/data'); if(r.ok){ update(await r.json()); } }catch(e){}
  requestAnimationFrame(poll);
}

buildPitchLines(); setMouseUI(false); poll();
</script>
</body></html>
"""

class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if p.path == "/data":
            self._json(LATEST); return
        if p.path == "/override":
            qs = parse_qs(p.query)
            if "enabled" in qs:
                OVERRIDE["enabled"] = bool(int(qs["enabled"][0]))
            if "x" in qs: OVERRIDE["x"] = max(-1.0, min(1.0, float(qs["x"][0])))
            if "y" in qs: OVERRIDE["y"] = max(-1.0, min(1.0, float(qs["y"][0])))
            if "btn" in qs: OVERRIDE["btn"] = 1 if int(qs["btn"][0]) else 0
            self._json({"ok": True}); return
        self.send_response(404); self.end_headers()

def start_server():
    httpd = HTTPServer((WEB_HOST, WEB_PORT), Handler)
    threading.Timer(1.0, lambda: webbrowser.open(f"http://{WEB_HOST}:{WEB_PORT}")).start()
    httpd.serve_forever()

# === Main loop: identical serial behaviour, with optional visual override ===
def main():
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No joystick detected."); sys.exit(1)
    js = pygame.joystick.Joystick(0); js.init()
    print(f"Using joystick: {js.get_name()} with {js.get_numaxes()} axes")

    ser = serial.Serial(PORT, BAUD, timeout=0)
    time.sleep(2); ser.reset_input_buffer()

    # start visualiser (non-blocking)
    threading.Thread(target=start_server, daemon=True).start()

    t_delay = 1.0 / RATE_HZ
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    raise KeyboardInterrupt

            # === EXACT behaviour unless you toggle Mouse Control on the page ===
            if not OVERRIDE["enabled"]:
                x = apply_deadzone(js.get_axis(0), DEADZONE)
                y = apply_deadzone(js.get_axis(1), DEADZONE)
                y = -y
                btn = 1 if (js.get_numbuttons() > 0 and js.get_button(0)) else 0
            else:
                x = clamp(OVERRIDE["x"], -1.0, 1.0)
                y = clamp(OVERRIDE["y"], -1.0, 1.0)
                btn = OVERRIDE["btn"]

            xi = int(clamp(x, -1.0, 1.0) * 32767)
            yi = int(clamp(y, -1.0, 1.0) * 32767)

            payload = struct.pack("<BhhB", START, xi, yi, btn)
            csum = checksum(payload[1:])
            frame = payload + bytes([csum])

            ser.write(frame)

            # Update visualiser snapshot (non-blocking)
            LATEST.update({
                "x": float(x), "y": float(y), "xi": int(xi), "yi": int(yi),
                "btn": int(btn), "frame": str(frame), "timestamp": time.time(),
                "simulation_mode": False
            })

            # (Optional) print, like your original:
            # print(f"Joystick → X:{x:.3f} Y:{y:.3f} | Int16: ({xi}, {yi}) Btn:{btn} | Frame:{frame}")

            time.sleep(t_delay)
    except KeyboardInterrupt:
        pass
    finally:
        try: ser.close()
        except: pass
        try: pygame.quit()
        except: pass

if __name__ == "__main__":
    main()
