import sqlite3
from datetime import datetime
import os

DB_PATH = 'waste_stats.db'

def init_db():
    """Create database and table if not exists"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waste_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            timestamp TEXT NOT NULL,
            esp32_triggered INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def save_detection(waste_type, confidence, esp32_triggered=False):
    """Save a detection to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            INSERT INTO detections (waste_type, confidence, timestamp, esp32_triggered)
            VALUES (?, ?, ?, ?)
        ''', (waste_type, confidence, timestamp, 1 if esp32_triggered else 0))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error: {e}")
        return False

def get_statistics():
    """Get statistics from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total count
        cursor.execute("SELECT COUNT(*) FROM detections")
        total = cursor.fetchone()[0]
        
        # Count by type
        cursor.execute("SELECT waste_type, COUNT(*) FROM detections GROUP BY waste_type")
        type_counts = dict(cursor.fetchall())
        
        # Last 10 detections
        cursor.execute('''
            SELECT waste_type, confidence, timestamp 
            FROM detections 
            ORDER BY id DESC 
            LIMIT 10
        ''')
        recent = cursor.fetchall()
        
        conn.close()
        
        return {
            'total': total,
            'plastic': type_counts.get('plastic', 0),
            'metal': type_counts.get('metal', 0),
            'paper': type_counts.get('paper', 0),
            'recent': recent
        }
    except Exception as e:
        print(f"Stats error: {e}")
        return {
            'total': 0,
            'plastic': 0,
            'metal': 0,
            'paper': 0,
            'recent': []
        }

def clear_history():
    """Clear all detection history"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM detections")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Clear error: {e}")
        return False