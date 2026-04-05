from flask import Flask, render_template, request, jsonify
from ultralytics import YOLO
import cv2
import numpy as np
import base64
import requests
from io import BytesIO
from PIL import Image
import os
from database import init_db, save_detection, get_statistics, clear_history

app = Flask(__name__)

# Initialize database on startup
init_db()

# ===== ESP32 CONFIGURATION =====
ESP32_IP = "192.168.100.177"  # Your ESP32 IP
ESP32_URL = f"http://{ESP32_IP}/classify"

# ===== LOAD MODELS =====
waste_model = YOLO("best.pt")
person_model = YOLO("yolov8n.pt")

# ===== CLASS MAPPING =====
WASTE_CLASSES = {
    3: "metal",
    4: "paper",
    5: "plastic"
}

# ===== DIFFERENT CONFIDENCE THRESHOLDS PER WASTE TYPE =====
CONFIDENCE_THRESHOLDS = {
    "plastic": 0.6,
    "metal": 0.6,
    "paper": 0.45
}

# ===== DETECTION SETTINGS =====
PERSON_CONF = 0.5
BASE_DETECTION_CONF = 0.4

def process_image(image_bytes):
    """Process image with YOLO and return detection results"""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Detect people
        person_results = person_model(frame, conf=PERSON_CONF, classes=[0])
        person_boxes = []
        for r in person_results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                person_boxes.append((x1, y1, x2, y2))
        
        # Detect waste
        waste_results = waste_model(frame, conf=BASE_DETECTION_CONF)
        
        detections = []
        for r in waste_results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                if cls_id not in WASTE_CLASSES:
                    continue
                
                waste_type = WASTE_CLASSES[cls_id]
                required_conf = CONFIDENCE_THRESHOLDS.get(waste_type, 0.5)
                
                if conf < required_conf:
                    continue
                
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Check overlap with person
                overlaps_person = False
                for px1, py1, px2, py2 in person_boxes:
                    if (x1 < px2 and x2 > px1 and y1 < py2 and y2 > py1):
                        overlaps_person = True
                        break
                
                if not overlaps_person:
                    detections.append({
                        'type': waste_type,
                        'confidence': round(conf * 100, 2),
                        'bbox': [x1, y1, x2, y2]
                    })
                    
                    # Draw bounding box
                    if waste_type == "plastic":
                        color = (16, 185, 129)
                    elif waste_type == "metal":
                        color = (59, 130, 246)
                    else:
                        color = (245, 158, 11)
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, f"{waste_type.upper()} {conf:.2f}", 
                               (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, color, 2)
        
        _, buffer = cv2.imencode('.jpg', frame)
        processed_image = base64.b64encode(buffer).decode('utf-8')
        
        return {
            'success': True,
            'detections': detections,
            'processed_image': processed_image
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_to_esp32(waste_type):
    """Send detection to ESP32"""
    try:
        response = requests.post(ESP32_URL, json={"class": waste_type}, timeout=2)
        return response.status_code == 200
    except:
        return False

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard page with statistics"""
    stats = get_statistics()
    return render_template('dashboard.html', stats=stats)

@app.route('/api/clear-history', methods=['POST'])
def api_clear_history():
    """Clear detection history"""
    clear_history()
    return jsonify({'success': True})

@app.route('/classify', methods=['POST'])
def classify():
    """Handle image upload and classification"""
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided', 'success': False}), 400
        
        image_data = data['image']
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        result = process_image(image_bytes)
        
        if not result['success']:
            return jsonify(result), 500
        
        # Save to database and send to ESP32
        esp32_ok = False
        sent_type = None
        
        if result['detections']:
            best_detection = max(result['detections'], key=lambda x: x['confidence'])
            esp32_ok = send_to_esp32(best_detection['type'])
            sent_type = best_detection['type']
            
            # Save to database
            save_detection(
                best_detection['type'], 
                best_detection['confidence'],
                esp32_ok
            )
            
            result['esp32_triggered'] = esp32_ok
            result['sent_to_esp32'] = sent_type
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    stats = get_statistics()
    return jsonify({
        'status': 'ok',
        'esp32_url': ESP32_URL,
        'waste_classes': list(WASTE_CLASSES.values()),
        'confidence_thresholds': CONFIDENCE_THRESHOLDS,
        'total_detections': stats['total']
    })

@app.route('/dashboard-data', methods=['GET'])
def dashboard_data():
    """Return dashboard statistics as JSON"""
    stats = get_statistics()
    return jsonify(stats)

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🤖 YOLO Waste Classification System")
    print("="*50)
    print(f"🎯 ESP32 Target: {ESP32_URL}")
    print("\n📊 Confidence Thresholds:")
    for waste_type, conf in CONFIDENCE_THRESHOLDS.items():
        print(f"   {waste_type.upper()}: {conf}")
    print("\n🌐 Open browser at: http://localhost:5000")
    print("📊 Dashboard: http://localhost:5000/dashboard")
    print("📱 Access from phone: http://[YOUR_LAPTOP_IP]:5000")
    print("⚠️  Press Ctrl+C to stop\n")
    print("="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)