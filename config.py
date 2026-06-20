#!/usr/bin/env python3
"""
Configuration untuk LazyFramework C2 Server
"""

import os
from datetime import timedelta

# ==================== SOCKET CONFIG ====================
C2_HOST = '192.168.1.8'
C2_PORT = 4444

# ==================== DATABASE CONFIG ====================
DATABASE = 'c2.db'

# ==================== FLASK CONFIG ====================
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-please')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# ==================== LOGGING ====================
LOG_FILE = 'c2.log'
LOG_LEVEL = 'DEBUG'

# ==================== COMMAND CONFIG ====================
COMMAND_TIMEOUT = 30
MAX_RESULT_SIZE = 10485760
AGENT_HEARTBEAT_TIMEOUT = 300

# ==================== AGENT CONFIG ====================
MAX_AGENTS = 1000
AGENT_CHECK_INTERVAL = 5

# ==================== DATABASE RETENTION ====================
RESULTS_RETENTION_DAYS = 30
LOGS_RETENTION_DAYS = 60
