import sys
import pygame

#Setup screen and display output for pygame display
pygame.init()
W, H = 1200, 600
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Alert Demo")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont(None, 200, bold = True)
TEXT = 'ALERT! ALERT!'

RED = (255, 0, 0)
import sys, subprocess, shlex
from pathlib import Path
import pygame
import argparse
import time

# ---------- CLI ----------
ap = argparse.ArgumentParser(description="Alert → then launch controller")
ap.add_argument("--controller", default="controller.py",
                help="Path to the controller script to run after alert (relative to this file, or absolute)")
ap.add_argument("--controller-args", default="--auto",
                help="Args to pass to controller (e.g. '--mouse', '--joystick --serial --port=COM10')")
ap.add_argument("--width", type=int, default=1200)
ap.add_argument("--height", type=int, default=600)
ap.add_argument("--flash-ms", type=int, default=500,
                help="Flash interval for the ALERT text")
ap.add_argument("--min-show-ms", type=int, default=1500,
                help="Minimum time to show the alert once triggered")
ap.add_argument("--sound", default="alertApp/alert-33762.mp3",
                help="Path to alert sound (optional)")
args = ap.parse_args()

# ---------- Pygame setup ----------
pygame.init()
pygame.mixer.init()
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

# Load sound (optional)
alert_sfx = None
sound_path = Path(args.sound)
if sound_path.exists():
    try:
        alert_sfx = pygame.mixer.Sound(str(sound_path))
    except Exception:
        alert_sfx = None

def play_ping():
    if alert_sfx:
        # avoid overlapping: stop first, then play once
        alert_sfx.stop()
        alert_sfx.play()

# ---------- Main loop ----------
running = True
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
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

# Build command
controller_path = (Path(__file__).parent / args.controller).resolve()
if not controller_path.exists():
    print(f"[ERROR] Controller script not found: {controller_path.resolve()}")
    sys.exit(1)

python_exe = sys.executable  # use current interpreter
cmd = [python_exe, str(controller_path)] + shlex.split(args.controller_args)

print(f"[INFO] Launching controller: {cmd}")
# Use Popen so the controller runs independently
subprocess.Popen(cmd, cwd=str(controller_path.parent))

BLACK = (0, 0, 0)

show_alert = False #This will become true after space is pressed
flash = False
flash_timer = 0
FLASH_INTERVAL = 500 #milliseconds

#Sound effects
alert_sfx = pygame.mixer.Sound("alertApp/alert-33762.mp3") #Alert sound affect triggered when alert system is acttive

#Lightweight script running to wait for the input of the allert, in this case simulated by the press of spacebar
  
while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            if e.key == pygame.K_SPACE:
                show_alert = True
                flash_timer = pygame.time.get_ticks() #resets the timer
    
    screen.fill(BLACK) # clear each frame

    if show_alert:
        now = pygame.time.get_ticks()
        if now - flash_timer > FLASH_INTERVAL:
            flash = not flash
            flash_timer = now
        if flash:
            surf = FONT.render(TEXT, True, RED)
            rect = surf.get_rect(center=(W // 2, H // 2))
            screen.blit(surf, rect)
            alert_sfx.play()
    
    pygame.display.flip()
    clock.tick(60)