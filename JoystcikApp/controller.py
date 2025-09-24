# pc_joystick_tx.py
import struct, time, sys
import pygame
import serial

# === CONFIG ===
PORT      = "COM11"      # Update if needed
BAUD      = 115200
RATE_HZ   = 100
DEADZONE  = 0.05
START     = 0xAA

# Helpers
def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v
def apply_deadzone(v, dz): return 0.0 if abs(v) < dz else v
def checksum(bytes_): return sum(bytes_) & 0xFF

def main():
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No joystick detected.")
        sys.exit(1)
    js = pygame.joystick.Joystick(0)
    js.init()
    print(f"Using joystick: {js.get_name()} with {js.get_numaxes()} axes")

    ser = serial.Serial(PORT, BAUD, timeout=0)
    time.sleep(2)                # give Arduino time after port opens
    ser.reset_input_buffer()
    t_delay = 1.0 / RATE_HZ

    running = True

    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

            # Axes
            x = apply_deadzone(js.get_axis(0), DEADZONE)
            y = apply_deadzone(js.get_axis(1), DEADZONE)
            y = -y  # invert Y if needed

            xi = int(clamp(x, -1.0, 1.0) * 32767)
            yi = int(clamp(y, -1.0, 1.0) * 32767)

            btn = 1 if (js.get_numbuttons() > 0 and js.get_button(0)) else 0

            payload = struct.pack("<BhhB", START, xi, yi, btn)
            csum = checksum(payload[1:])
            frame = payload + bytes([csum])

            ser.write(frame)

            # --- Print to terminal ---
            print(f"Joystick → X:{x:.3f} Y:{y:.3f} | Int16: ({xi}, {yi}) Btn:{btn} | Frame:{frame}")

            time.sleep(t_delay)

    finally:
        ser.close()

if __name__ == "__main__":
    main()
