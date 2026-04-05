# AI Waste Classification System

YOLO-powered waste sorting with ESP32, LEDs, and servo motors.

## Features
- Detects plastic, metal, paper in real-time
- ESP32 controls LEDs + servo bins
- Dashboard with statistics (SQLite)

## Setup
1. `pip install -r requirements.txt`
2. `python app.py`
3. Open `http://localhost:5000`

## Hardware Required
- ESP32
- 3x SG90 servos
- 3x LEDs (green, blue, orange)
- Breadboard + wires
