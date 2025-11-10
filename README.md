```markdown
# Fly-By-Wire System

A real-time aircraft control system that replaces traditional mechanical linkages with electronic interfaces, providing enhanced stability and safety features.

## 🚀 Project Overview

This Fly-By-Wire system translates pilot inputs (from joystick or mouse) into electronic signals that control aircraft servos via wireless communication. The system includes automatic stabilization features and can maintain control even if the pilot becomes incapacitated.

## 👥 Development Team

- Tshifhiwa  Muade (576941) 
- Ulrigh Oosthuizen (577952) 
- Tokelo Ramogase (601009) 
- Tsepang Mosala (600429)
- Tshegofatso Mashego (600627)
- Tumiso Lethabo Koee (600441)
- Tshiamo Kagiso Maphanga (600516)
- Ugochukwu Winner Ogbonnaya (600528)
- Tshegetsanang Nkqwatau (600219)
- Tinyiko Mnisi (600311)

## 🛠️ System Architecture

### Components
- **Ground Station**: Python-based controller with joystick/mouse input
- **Wireless Communication**: nRF24L01 2.4GHz RF modules
- **Aircraft Node**: Arduino with servo control and failsafe mechanisms
- **Web Visualizer**: Real-time attitude indicator and control interface

### Data Flow
```
PC (Python) → Serial/USB → nRF24L01 TX → nRF24L01 RX → Arduino → Servos (5x)
```

## 💻 Software & Libraries

### Python Dependencies
```python
# Core libraries for ground station and visualizer
pygame==2.5.0          # Joystick input handling and audio
pyserial==3.5          # Serial communication with Arduino
webbrowser==0.0        # Auto-opening web visualizer (built-in)
threading==0.0         # Concurrent execution (built-in)
http.server==0.0       # Web server for visualizer (built-in)
json==0.0              # Data serialization (built-in)
urllib.parse==0.0      # URL parsing (built-in)
subprocess==0.0        # Process management (built-in)
argparse==0.0          # Command-line argument parsing (built-in)
pathlib==0.0           # File path operations (built-in)
time==0.0              # Timing and delays (built-in)
struct==0.0            # Binary data packing (built-in)
sys==0.0               # System operations (built-in)

# Optional Windows fallback
winsound==0.0          # Audio fallback on Windows (built-in)
platform==0.0          # System detection (built-in)
```

### Arduino Libraries
```cpp
#include <SPI.h>           // Serial Peripheral Interface for nRF24L01
#include <nRF24L01.h>      // nRF24L01 transceiver driver
#include <RF24.h>          // Radio Frequency library wrapper
#include <Servo.h>         // Servo motor control library
```

### Web Technologies
- **HTML5/CSS3**: Visualizer interface with modern styling
- **JavaScript ES6**: Real-time data polling and interactive controls
- **CSS Grid/Flexbox**: Responsive layout design
- **CSS Custom Properties**: Theming with CSS variables

## 📁 Code Structure

### Core Components

1. **`joystick_tx_with_visualiser.py`**
   - Main ground station controller
   - Joystick/mouse input with deadzone handling
   - Real-time web visualizer (port 8090)
   - Mouse override capability
   - Fixed-step loop for deterministic timing

2. **`notify.py`**
   - Alert system with sound notifications
   - Controller launcher with auto URL opening
   - Robust audio initialization with fallbacks

3. **Arduino Receiver** (`main.ino`)
   - RF packet parsing with checksum verification
   - Servo control with differential ailerons
   - Failsafe centering (800ms timeout)
   - LED status indicators

## 🔧 Key Features

### Input Processing
- Fixed-rate sampling (100Hz)
- Configurable deadzone (5% default)
- Y-axis inversion for intuitive control
- Send-on-change for bandwidth efficiency

### Communication Protocol
```
Frame: [0xAA][int16 x][int16 y][uint8 btn][uint8 checksum]
- x, y: Normalized to ±32767
- btn: Button state (0/1)
- checksum: Sum of x, y, btn (8-bit)
```

### Safety Mechanisms
- **Failsafe Centering**: Automatic return to neutral on signal loss
- **Checksum Verification**: Data integrity validation
- **Signal Monitoring**: Continuous link quality assessment
- **Manual Override**: Mouse control fallback

### Visualizer
- Real-time attitude indicator (artificial horizon)
- Pitch and roll visualization (±60° roll, ±45° pitch)
- Live data display (values, frame data, servo positions)
- Mouse control toggle

## 🎮 Usage

### Starting the System
```bash
# Launch with alert and auto-open visualizer
python notify.py --controller-args="--joystick" --open-url="http://127.0.0.1:8090"

# Or run controller directly
python joystick_tx_with_visualiser.py
```

### Controller Options
- **Joystick Mode**: Physical joystick input (default)
- **Mouse Mode**: Click "Enable Mouse Control" in visualizer
- **Serial Port**: Configurable (default: COM11, 115200 baud)

## 🔌 Hardware Setup

### Hardware Components

| Component | Quantity | Technical Function | Project Implementation |
|-----------|----------|-------------------|------------------------|
| Arduino Uno | 2 | Microcontroller boards for reading inputs and controlling outputs | One Arduino (transmitter) reads joystick inputs and sends data via NRF24L01. The other Arduino (receiver) processes received commands and drives servos controlling aircraft surfaces. |
| NRF24L01 Transceiver Modules | 2 | 2.4GHz wireless communication for bidirectional serial data transfer | Sends joystick movement data from transmitter to receiver module on RC aircraft, maintaining real-time low-latency control. |
| MG996R Servo Motors | 5 | High-torque servos converting PWM signals into precise angular motion | Actuates aircraft control surfaces: left/right ailerons, elevator, rudder, and auxiliary wing. Each servo adjusts based on pilot's joystick inputs. |
| Joystick Module | 1 | Analog input device outputting variable voltage for X/Y axes and digital button input | Provides pilot's manual control input for pitch (up/down), roll (left/right), and optional mode switching or kill-switch control. |
| Breadboard | 1 | Prototyping board for temporary circuit assembly | Used during transmitter and receiver wiring for connecting NRF24L01, power lines, and signal routing without soldering. |
| External Power Adapter (5-6V DC, 2A) | 1 | Stable external power supply for servos and microcontrollers | Powers servos independently of Arduino's USB port to prevent brownouts under heavy load during control surface movement. |
| Jumper Wires (Male-Male / Male-Female) | ~30 | Flexible connectors for circuit wiring and signal routing | Connects all modules on breadboard (Arduino to NRF24L01, servos, joystick, and power rails). |
| Prototype RC Plane Frame / Control Surface Rig | 1 | Physical 3D printed frame to mount servos and receiver | Represents aircraft structure for testing servo stabilization, control responsiveness, and mechanical linkages. |

### Ground Station
- Arduino with nRF24L01 (Transmitter)
- USB connection to PC
- Joystick module
- Breadboard for prototyping

### Aircraft
- Arduino with nRF24L01 (Receiver)
- 5x MG996R Servos 
  - 2x Ailerons (mirrored)
  - 3x Elevators (synchronized)
- External 5-6V power supply for servos
- 3D printed RC plane frame

### Servo Configuration
```cpp
// Pin assignments
SERVO_X_LEFT  = 4   // Right aileron
SERVO_X_RIGHT = 5   // Left aileron (mirrored)
SERVO_Y_1     = 6   // Elevator 1
SERVO_Y_2     = 9   // Elevator 2  
SERVO_Y_3     = 10  // Elevator 3
```

## 📊 Technical Specifications

- **Update Rate**: 100Hz (configurable)
- **RF Data Rate**: 250kbps (robust link)
- **Servo Range**: 0-180° (±80° travel from center)
- **Failsafe Timeout**: 800ms
- **Deadzone**: 5% (configurable)
- **RF Channel**: 100
- **Power Requirements**: 5-6V DC, 2A for servos

## 🚨 Safety Features

1. **Signal Loss Protection**: Servos center automatically
2. **Data Validation**: Checksum on all packets
3. **Range Limiting**: Servo movement constrained to safe limits
4. **Manual Override**: Mouse control available if joystick fails
5. **Brownout Prevention**: External power supply for servos

## 🔮 Future Enhancements

- Machine learning-based flight stabilization
- Anomaly detection for autonomous takeover
- Waypoint-based autonomous navigation
- Enhanced redundancy with duplicate sensors
- Digital servos for reduced jitter



