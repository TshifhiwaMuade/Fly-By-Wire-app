"""
Alert → then launch controller (with reliable sound + optional URL open)

Examples:
  python notify.py --controller=controller.py --controller-args="--mouse" --open-url="http://127.0.0.1:8090"
"""

import sys
import subprocess
import shlex
from pathlib import Path
import argparse
import time
import threading
import webbrowser
import pygame

# ---------- CLI ----------
ap = argparse.ArgumentParser(description="Alert → then launch controller")
ap.add_argument("--controller", default="controller.py",
                help="Path to the controller script (relative to this file, or absolute)")
ap.add_argument("--controller-args", default="--auto",
                help="Args to pass to controller (e.g. '--mouse', '--joystick --serial --port=COM10')")
ap.add_argument("--width", type=int, default=1200)
ap.add_argument("--height", type=int, default=600)
ap.add_argument("--flash-ms", type=int, default=500, help="Flash interval for ALERT text")
ap.add_argument("--min-show-ms", type=int, default=1000, help="Minimum time to show alert once triggered")
ap.add_argument("--sound", default="alertApp/alert-33762.mp3", help="Path to alert sound (MP3/WAV/OGG)")
ap.add_argument("--open-url", default="", help="Open this URL a moment after launching the controller")
ap.add_argument("--open-delay", type=float, default=1.5, help="Seconds to wait before opening --open-url")
args = ap.parse_args()

SCRIPT_DIR = Path(__file__).parent.resolve()

# ---------- Pygame setup ----------
pygame.init()

mixer_ready = False
try:
    # Explicit setup can help some systems
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    mixer_ready = True
except Exception as e:
    print(f"[WARN] mixer.init failed: {e}")
    mixer_ready = False

W, H = args.width, args.height
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Alert Demo")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont(None, 200, bold=True)
TEXT = 'ALERT! ALERT!'
RED, BLACK = (255, 0, 0), (0, 0, 0)

show_alert = False
flash = False
flash_timer = 0
start_show_ts = 0

# ---------- Sound loading (robust) ----------
sound_path = (SCRIPT_DIR / args.sound).resolve()
print(f"[INFO] Using sound: {sound_path}")
alert_sound = None           # pygame.mixer.Sound (best for WAV/OGG)
alert_music_loaded = False   # pygame.mixer.music (often better for MP3)

if sound_path.exists() and mixer_ready:
    # Heuristic: prefer Sound for .wav/.ogg; use music for .mp3
    ext = sound_path.suffix.lower()
    try:
        if ext in {".wav", ".ogg"}:
            alert_sound = pygame.mixer.Sound(str(sound_path))
            alert_sound.set_volume(1.0)
            print("[INFO] Loaded sound via mixer.Sound()")
        else:
            pygame.mixer.music.load(str(sound_path))
            pygame.mixer.music.set_volume(1.0)
            alert_music_loaded = True
            print("[INFO] Loaded sound via mixer.music (MP3 path)")
    except Exception as e:
        print(f"[WARN] Failed to load sound: {e}")
else:
    if not sound_path.exists():
        print(f"[WARN] Sound file not found: {sound_path}")
    elif not mixer_ready:
        print("[WARN] Mixer not ready; sound disabled")

def play_ping():
    """Try pygame sound; if that fails on Windows, use winsound.Beep as a fallback."""
    played = False
    if mixer_ready:
        try:
            if alert_sound:
                alert_sound.stop(); alert_sound.play()
                played = True
            elif alert_music_loaded:
                pygame.mixer.music.stop()
                pygame.mixer.music.play()
                played = True
        except Exception as e:
            print(f"[WARN] pygame play failed: {e}")
    if not played:
        # Windows fallback
        try:
            import platform
            if platform.system().lower().startswith("win"):
                import winsound
                winsound.Beep(880, 180)  # 880 Hz for 180 ms
        except Exception as e:
            # final fallback: no sound
            print(f"[WARN] winsound fallback failed: {e}")

# ---------- Main loop ----------
running = True
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                if (not show_alert) or (pygame.time.get_ticks() - start_show_ts >= args.min_show_ms):
                    running = False
            elif e.key == pygame.K_SPACE:
                if not show_alert:
                    show_alert = True
                    start_show_ts = pygame.time.get_ticks()
                    flash_timer = start_show_ts
                    play_ping()

    screen.fill(BLACK)

    if show_alert:
        now = pygame.time.get_ticks()
        if now - flash_timer >= args.flash_ms:
            flash = not flash
            flash_timer = now
            play_ping()

        if flash:
            surf = FONT.render(TEXT, True, RED)
            rect = surf.get_rect(center=(W // 2, H // 2))
            screen.blit(surf, rect)

    pygame.display.flip()
    clock.tick(60)

# ---------- After window closes: launch controller ----------
try:
    pygame.quit()
except Exception:
    pass

controller_path = (SCRIPT_DIR / args.controller).resolve()
if not controller_path.exists():
    print(f"[ERROR] Controller script not found: {controller_path}")
    sys.exit(1)

python_exe = sys.executable
cmd = [python_exe, str(controller_path)] + shlex.split(args.controller_args)

print(f"[INFO] Launching controller: {cmd}")
subprocess.Popen(cmd, cwd=str(controller_path.parent))

# Optional: open the visualiser page for you (if your controller doesn't auto-open)
if args.open_url:
    def _open():
        try:
            webbrowser.open(args.open_url)
        except Exception:
            pass
    threading.Timer(args.open_delay, _open).start()
