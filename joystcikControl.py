# pc_joystick_tx.py - With Aircraft-Style Visualizer
import struct, time, sys, json, threading
import pygame
import serial
import serial.tools.list_ports
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
from urllib.parse import urlparse, parse_qs
import webbrowser

# === CONFIG ===
PORT      = "COM10"      # Update if needed to the right port
BAUD      = 115200
RATE_HZ   = 100
DEADZONE  = 0.05
START     = 0xAA
WEB_PORT  = 8080         # Port for the web visualizer

# Global variables for simulation mode and web server
SIMULATION_MODE = False
ser = None
latest_data = {
    'x': 0.0, 'y': 0.0, 'xi': 0, 'yi': 0, 'btn': 0, 'frame': '', 'timestamp': time.time()
}

# Helpers
def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v
def apply_deadzone(v, dz): return 0.0 if abs(v) < dz else v
def checksum(bytes_): return sum(bytes_) & 0xFF

def find_available_ports():
    """List all available COM ports"""
    ports = list(serial.tools.list_ports.comports())
    print("Available COM ports:")
    for port, desc, hwid in sorted(ports):
        print(f"  {port}: {desc}")
    return ports

def setup_serial_connection():
    """Setup serial connection with fallback to simulation mode"""
    global ser, SIMULATION_MODE
    
    # First, list available ports
    available_ports = find_available_ports()
    
    if not available_ports:
        print("No COM ports found. Running in SIMULATION MODE.")
        SIMULATION_MODE = True
        return
    
    # Try to connect to the specified port
    try:
        print(f"Attempting to connect to {PORT}...")
        ser = serial.Serial(PORT, BAUD, timeout=0)
        print(f"Successfully connected to {PORT}")
        SIMULATION_MODE = False
        time.sleep(2)  # give Arduino time after port opens
        ser.reset_input_buffer()
    except serial.SerialException as e:
        print(f"Could not open serial port {PORT}: {e}")
        
        # Try the first available port
        if available_ports:
            first_port = available_ports[0][0]
            try:
                print(f"Trying first available port: {first_port}")
                ser = serial.Serial(first_port, BAUD, timeout=0)
                print(f"Successfully connected to {first_port}")
                SIMULATION_MODE = False
                time.sleep(2)  # give Arduino time after port opens
                ser.reset_input_buffer()
                return
            except serial.SerialException as e2:
                print(f"Could not connect to {first_port}: {e2}")
        
        print("Falling back to SIMULATION MODE.")
        SIMULATION_MODE = True

def send_frame(frame):
    """Send frame via serial or simulate"""
    global SIMULATION_MODE
    
    if SIMULATION_MODE:
        # In simulation mode, just show what would be sent
        pass  # The print statement in main() will show the data
    else:
        try:
            if ser and ser.is_open:
                ser.write(frame)
        except serial.SerialException as e:
            print(f"Serial send error: {e}")
            print("Switching to simulation mode")
            SIMULATION_MODE = True

def update_web_data(x, y, xi, yi, btn, frame):
    """Update the data that gets sent to the web visualizer"""
    global latest_data
    latest_data = {
        'x': x, 'y': y, 'xi': xi, 'yi': yi, 'btn': btn, 
        'frame': str(frame), 'timestamp': time.time(),
        'simulation_mode': SIMULATION_MODE
    }

class VisualizerHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            # Serve the main visualizer page
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Fly-By-Wire System Visualizer</title>
    <style>
        body {
            background: #1a1a1a;
            color: white;
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            font-size: 32px;
            margin-bottom: 30px;
            color: #FFD700;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 2px;
            text-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
        }
        .attitude-indicator {
            width: 800px;            /* Increased from 400px */
            height: 800px;           /* Increased from 400px */
            margin: 20px auto;
            position: relative;
            border-radius: 50%;
            overflow: hidden;
            border: 15px solid #333;  /* Increased border thickness */
            box-shadow: inset 0 0 40px rgba(0,0,0,0.5);
        }
        .horizon {
            position: absolute;
            width: 1600px;           /* Doubled from original */
            height: 1600px;          /* Doubled from original */
            top: 50%;
            left: 50%;
            transform-origin: center;
            transition: transform 0.1s linear;
        }
        .sky {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 50%;
            background: #7EC0EE;
        }
        .ground {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 50%;
            background: #8B4513;
        }
        .reference-marker {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 10;
        }
        .aircraft-symbol {
            width: 200px;            /* Increased from 100px */
            height: 200px;           /* Increased from 100px */
            position: relative;
        }
        .aircraft-symbol::before {
            content: '';
            position: absolute;
            width: 240px;            /* Increased from 120px */
            height: 12px;            /* Increased from 8px */
            background: #FFD700;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }
        .aircraft-symbol::after {
            content: '';
            position: absolute;
            width: 12px;             /* Increased from 8px */
            height: 12px;            /* Increased from 8px */
            background: #FFD700;
            border-radius: 50%;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }
        .pitch-lines {
            position: absolute;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
        }
        .pitch-line {
            position: absolute;
            width: 200px;
            height: 2px;
            background: white;
            left: 50%;
            transform: translateX(-50%);
        }
        .pitch-text {
            position: absolute;
            color: white;
            left: calc(50% + 110px);
            transform: translateY(-50%);
            font-size: 14px;
        }
        .roll-indicator {
            position: absolute;
            width: 400px;
            height: 400px;
            top: 0;
            left: 0;
        }
        .roll-marker {
            position: absolute;
            width: 2px;
            height: 15px;
            background: white;
            left: 50%;
            transform-origin: bottom;
        }
        .values {
            text-align: center;
            margin-top: 20px;
            font-size: 24px;         /* Increased from 18px */
            font-family: monospace;
            background: rgba(0, 0, 0, 0.5);
            padding: 15px 30px;
            border-radius: 10px;
            border: 1px solid #333;
        }
    </style>
</head>
<body>
    <h1>Fly-By-Wire System Visualizer</h1>
    <div class="attitude-indicator">
        <div class="horizon" id="horizon">
            <div class="sky"></div>
            <div class="ground"></div>
            <div class="pitch-lines" id="pitchLines"></div>
        </div>
        <div class="reference-marker">
            <div class="aircraft-symbol"></div>
        </div>
        <div class="roll-indicator" id="rollIndicator"></div>
    </div>
    <div class="values" id="values">
        Pitch: 0° | Roll: 0°
    </div>

    <script>
        function createPitchLines() {
            const pitchLines = document.getElementById('pitchLines');
            for(let i = -90; i <= 90; i += 10) {
                if(i === 0) continue;
                const line = document.createElement('div');
                line.className = 'pitch-line';
                line.style.top = `${50 + i}%`;
                line.style.width = i % 20 === 0 ? '150px' : '100px';
                
                const text = document.createElement('div');
                text.className = 'pitch-text';
                text.textContent = Math.abs(i) + '°';
                text.style.top = `${50 + i}%`;
                
                pitchLines.appendChild(line);
                pitchLines.appendChild(text);
            }
        }

        function createRollMarkers() {
            const rollIndicator = document.getElementById('rollIndicator');
            for(let i = -60; i <= 60; i += 10) {
                const marker = document.createElement('div');
                marker.className = 'roll-marker';
                marker.style.transform = `rotate(${i}deg)`;
                marker.style.height = i % 30 === 0 ? '20px' : '10px';
                rollIndicator.appendChild(marker);
            }
        }

        function updateAttitude(data) {
            const horizon = document.getElementById('horizon');
            const values = document.getElementById('values');
            
            // Convert joystick values to degrees
            const rollDeg = -data.x * 60;  // Roll: ±60 degrees
            const pitchDeg = data.y * 45;  // Pitch: ±45 degrees
            
            // Update horizon transformation
            horizon.style.transform = `translate(-50%, -50%) rotate(${rollDeg}deg) translateY(${pitchDeg}%)`;
            
            // Update values display
            values.textContent = `Pitch: ${-pitchDeg.toFixed(1)}° | Roll: ${rollDeg.toFixed(1)}°`;
        }

        // Initialize pitch lines and roll markers
        createPitchLines();
        createRollMarkers();

        // Poll for data updates
        setInterval(async () => {
            try {
                const response = await fetch('/data');
                const data = await response.json();
                updateAttitude(data);
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }, 16);
    </script>
</body>
</html>'''
            self.wfile.write(html_content.encode())
            
        elif parsed_path.path == '/data':
            # Serve the joystick data as JSON
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(latest_data).encode())
        else:
            # Default handling
            super().do_GET()

def start_web_server():
    """Start the web server in a separate thread"""
    try:
        with socketserver.TCPServer(("", WEB_PORT), VisualizerHandler) as httpd:
            print(f"🌐 Web visualizer started at: http://localhost:{WEB_PORT}")
            print("   The visualizer will open automatically in your browser")
            
            # Open browser automatically
            threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{WEB_PORT}')).start()
            
            httpd.serve_forever()
    except OSError as e:
        print(f"Could not start web server on port {WEB_PORT}: {e}")
        print("The visualizer is disabled, but joystick control will still work.")

def main():
    # Start web server in background thread
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No joystick detected.")
        sys.exit(1)
    js = pygame.joystick.Joystick(0)
    js.init()
    print(f"Using joystick: {js.get_name()} with {js.get_numaxes()} axes")

    # Setup serial connection (with simulation fallback)
    setup_serial_connection()
    
    t_delay = 1.0 / RATE_HZ
    running = True

    print("\n=== AIRCRAFT CONTROLS ===")
    print("Forward (push) = Nose Down")
    print("Backward (pull) = Nose Up")
    print("Left/Right = Roll")
    print("Press ESC to exit")
    if SIMULATION_MODE:
        print("Running in SIMULATION MODE - no data will be sent to serial port")
    else:
        print(f"Sending data to serial port at {RATE_HZ} Hz")
    print("==========================\n")

    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                elif event.type == pygame.QUIT:
                    running = False
                # Add joystick hotplug support
                elif event.type == pygame.JOYDEVICEADDED:
                    print("Joystick connected!")
                    js = pygame.joystick.Joystick(0)
                    js.init()
                elif event.type == pygame.JOYDEVICEREMOVED:
                    print("Joystick disconnected!")

            # Get joystick axes with proper scaling and aircraft convention
            try:
                # Read raw joystick values
                x = js.get_axis(0)  # Roll (left-right)
                y = js.get_axis(1)  # Pitch (forward-backward)
                
                # Apply deadzone
                x = apply_deadzone(x, DEADZONE)
                y = apply_deadzone(y, DEADZONE)
                
                # Invert Y axis for proper aircraft behavior:
                # Pulling back (negative Y) = nose up (positive pitch)
                # Pushing forward (positive Y) = nose down (negative pitch)
                y = y  # Remove the previous -y inversion since we want natural aircraft behavior
                
                # Scale values
                xi = int(clamp(x, -1.0, 1.0) * 32767)
                yi = int(clamp(y, -1.0, 1.0) * 32767)
                
                # Get button state
                btn = 1 if (js.get_numbuttons() > 0 and js.get_button(0)) else 0
                
                # Debug output
                print(f"Raw Joystick: X={x:.3f} Y={y:.3f}")
                
            except pygame.error:
                print("Joystick error - check connection")
                x, y, xi, yi, btn = 0, 0, 0, 0, 0

            payload = struct.pack("<BhhB", START, xi, yi, btn)
            csum = checksum(payload[1:])
            frame = payload + bytes([csum])

            # Send frame (or simulate)
            send_frame(frame)
            
            # Update web visualizer data
            update_web_data(x, y, xi, yi, btn, frame)

            # Print the input from the joystick to terminal
            mode_str = "[SIMULATION]" if SIMULATION_MODE else "[SERIAL]"
            print(f"{mode_str} Joystick → X:{x:.3f} Y:{y:.3f} | Int16: ({xi}, {yi}) Btn:{btn}")

            time.sleep(t_delay)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if ser and ser.is_open:
            ser.close()
            print("Serial connection closed.")
        pygame.quit()
        print("Pygame closed.")

if __name__ == "__main__":
    main()