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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>✈️ Aircraft Joystick Visualizer</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #0f1c3c 0%, #1a3c72 100%);
            color: white;
            min-height: 100vh;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .title {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .status {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            margin-bottom: 15px;
            animation: pulse 2s infinite;
        }
        .simulation { background: rgba(255, 107, 107, 0.2); border: 1px solid #ff6b6b; color: #ff6b6b; }
        .serial { background: rgba(76, 205, 80, 0.2); border: 1px solid #4ccd50; color: #4ccd50; }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        .panel {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .aircraft-display {
            position: relative;
            width: 300px;
            height: 300px;
            margin: 0 auto 30px;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-radius: 15px;
            background: radial-gradient(circle, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 100%);
            box-shadow: inset 0 0 50px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        .horizon-line {
            position: absolute;
            top: 50%;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, #4ecdc4, transparent);
            transform: translateY(-50%);
        }
        .pitch-lines {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        .pitch-line {
            position: absolute;
            left: 0;
            width: 100%;
            height: 1px;
            background: rgba(255, 255, 255, 0.2);
        }
        .pitch-label {
            position: absolute;
            left: 10px;
            transform: translateY(-50%);
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
        }
        .aircraft-symbol {
            position: absolute;
            top: 50%;
            left: 50%;
            width: 120px;
            height: 40px;
            transform: translate(-50%, -50%);
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            border: 2px solid #ff6b6b;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.1s ease;
        }
        .aircraft-symbol::before {
            content: '✈️';
            font-size: 20px;
            filter: grayscale(1) brightness(2);
        }
        .values-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .value-display {
            background: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .value-label {
            font-size: 0.9em;
            opacity: 0.7;
            margin-bottom: 5px;
        }
        .value-number {
            font-size: 1.4em;
            font-weight: bold;
            color: #4ecdc4;
            text-shadow: 0 0 10px rgba(78, 205, 196, 0.5);
        }
        .button-indicator {
            display: inline-block;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 255, 255, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.2em;
            transition: all 0.2s ease;
            margin: 0 auto;
        }
        .button-indicator.pressed {
            background: linear-gradient(45deg, #ff6b6b, #ff8e53);
            border-color: white;
            box-shadow: 0 0 20px rgba(255, 107, 107, 0.6);
            transform: scale(1.1);
        }
        .frame-display {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 10px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            word-break: break-all;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .frame-label {
            color: #4ecdc4;
            margin-bottom: 10px;
            font-weight: bold;
        }
        .connection-status {
            text-align: center;
            margin: 20px 0;
            padding: 15px;
            border-radius: 10px;
            background: rgba(0, 0, 0, 0.2);
        }
        .instructions {
            text-align: center;
            margin: 20px 0;
            padding: 15px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="title">✈️ Aircraft Joystick Visualizer</h1>
        <div class="status" id="statusIndicator">CONNECTING...</div>
    </div>
    
    <div class="instructions">
        <p><strong>Aircraft Controls:</strong> Forward (push) = Nose Down | Backward (pull) = Nose Up</p>
    </div>
    
    <div class="container">
        <div class="panel">
            <h2 style="text-align: center; margin-bottom: 20px;">✈️ Aircraft Attitude Display</h2>
            
            <div class="aircraft-display" id="aircraftDisplay">
                <div class="pitch-lines" id="pitchLines"></div>
                <div class="horizon-line"></div>
                <div class="aircraft-symbol" id="aircraftSymbol"></div>
            </div>

            <div class="values-grid">
                <div class="value-display">
                    <div class="value-label">X-Axis (Roll)</div>
                    <div class="value-number" id="xValue">0.000</div>
                </div>
                <div class="value-display">
                    <div class="value-label">Y-Axis (Pitch)</div>
                    <div class="value-number" id="yValue">0.000</div>
                </div>
            </div>
        </div>

        <div class="panel">
            <h2 style="text-align: center; margin-bottom: 20px;">📊 Data Display</h2>
            
            <div class="values-grid">
                <div class="value-display">
                    <div class="value-label">X Integer</div>
                    <div class="value-number" id="xiValue">0</div>
                </div>
                <div class="value-display">
                    <div class="value-label">Y Integer</div>
                    <div class="value-number" id="yiValue">0</div>
                </div>
            </div>

            <div style="text-align: center; margin: 20px 0;">
                <div class="value-label" style="margin-bottom: 15px;">Button State</div>
                <div class="button-indicator" id="buttonIndicator">OFF</div>
            </div>

            <div class="frame-display">
                <div class="frame-label">📡 Frame Data</div>
                <div id="frameData">Waiting for data...</div>
            </div>
        </div>
    </div>

    <div class="connection-status">
        <p><strong>Connection:</strong> <span id="connectionStatus">Connecting to Python script...</span></p>
        <p><strong>Last Update:</strong> <span id="lastUpdate">Never</span></p>
    </div>

    <script>
        function createPitchLines() {
            const pitchLines = document.getElementById('pitchLines');
            pitchLines.innerHTML = '';
            
            // Create pitch lines every 30 pixels (10 degrees)
            for (let i = -150; i <= 150; i += 30) {
                const line = document.createElement('div');
                line.className = 'pitch-line';
                line.style.top = (150 + i) + 'px';
                
                const label = document.createElement('div');
                label.className = 'pitch-label';
                label.style.top = (150 + i) + 'px';
                label.textContent = Math.abs(i / 30 * 10) + '°';
                
                pitchLines.appendChild(line);
                pitchLines.appendChild(label);
            }
        }

        function updateVisualization(data) {
            const { x, y, xi, yi, btn, frame, simulation_mode } = data;
            
            // Update status indicator
            const statusIndicator = document.getElementById('statusIndicator');
            const connectionStatus = document.getElementById('connectionStatus');
            
            if (simulation_mode) {
                statusIndicator.textContent = 'SIMULATION MODE';
                statusIndicator.className = 'status simulation';
                connectionStatus.textContent = 'Simulation Mode - No hardware connected';
            } else {
                statusIndicator.textContent = 'SERIAL CONNECTED';
                statusIndicator.className = 'status serial';
                connectionStatus.textContent = 'Connected to hardware';
            }
            
            // Update aircraft attitude
            const aircraftSymbol = document.getElementById('aircraftSymbol');
            const display = document.getElementById('aircraftDisplay');
            
            // Apply roll (x-axis) as rotation
            const rollDegrees = x * 30; // ±30 degrees roll
            aircraftSymbol.style.transform = `translate(-50%, -50%) rotate(${rollDegrees}deg)`;
            
            // Apply pitch (y-axis) as vertical movement with aircraft convention
            // Forward (positive y) = nose down = aircraft moves up in display
            // Backward (negative y) = nose up = aircraft moves down in display
            const pitchOffset = y * 100; // ±100 pixels movement for pitch
            aircraftSymbol.style.top = `calc(50% + ${pitchOffset}px)`;
            
            // Update text values
            document.getElementById('xValue').textContent = x.toFixed(3);
            document.getElementById('yValue').textContent = y.toFixed(3);
            document.getElementById('xiValue').textContent = xi;
            document.getElementById('yiValue').textContent = yi;
            
            // Update button indicator
            const btnIndicator = document.getElementById('buttonIndicator');
            if (btn === 1) {
                btnIndicator.classList.add('pressed');
                btnIndicator.textContent = 'ON';
            } else {
                btnIndicator.classList.remove('pressed');
                btnIndicator.textContent = 'OFF';
            }
            
            // Update frame data
            document.getElementById('frameData').textContent = frame;
            
            // Update last update time
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }

        // Poll for data from Python script
        async function fetchData() {
            try {
                const response = await fetch('/data');
                if (response.ok) {
                    const data = await response.json();
                    updateVisualization(data);
                }
            } catch (error) {
                console.log('Waiting for Python script...');
            }
        }

        // Initialize pitch lines and start polling
        createPitchLines();
        setInterval(fetchData, 50);
        fetchData();
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

            # Axes - NO inversion of Y axis for aircraft controls
            x = apply_deadzone(js.get_axis(0), DEADZONE)
            y = apply_deadzone(js.get_axis(1), DEADZONE)
            # Note: Y axis is NOT inverted to maintain aircraft convention

            xi = int(clamp(x, -1.0, 1.0) * 32767)
            yi = int(clamp(y, -1.0, 1.0) * 32767)

            btn = 1 if (js.get_numbuttons() > 0 and js.get_button(0)) else 0

            payload = struct.pack("<BhhB", START, xi, yi, btn)
            csum = checksum(payload[1:])
            frame = payload + bytes([csum])

            # Send frame (or simulate)
            send_frame(frame)
            
            # Update web visualizer data
            update_web_data(x, y, xi, yi, btn, frame)

            # Print the input from the joystick to terminal
            mode_str = "[SIMULATION]" if SIMULATION_MODE else "[SERIAL]"
            print(f"{mode_str} Joystick → X:{x:.3f} Y:{y:.3f} | Int16: ({xi}, {yi}) Btn:{btn} | Frame:{frame}")

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