#!/usr/bin/env python3
"""
Execute a command on the OpenHAB server via SSH.

This utility script allows you to easily run commands on the remote server
using the same SSH configuration as the deployment script.
"""

import sys
import argparse
from pathlib import Path
import paramiko

# Import the SSH utilities from deploy_openhab.py
sys.path.insert(0, str(Path(__file__).parent))
from deploy_openhab import parse_ssh_config, execute_ssh_command


def main():
    parser = argparse.ArgumentParser(
        description='Execute a command on the OpenHAB server via SSH',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute a simple command
  python execute_command.py "ls -la /var/lib/openhab/conf"
  
  # Check OpenHAB service status
  python execute_command.py "sudo systemctl status openhab"
  
  # View recent logs
  python execute_command.py "sudo journalctl -u openhab -n 50"
  
  # Use a different SSH config
  python execute_command.py --ssh-config custom_config "uptime"
  
  # Use the deploy user instead of admin
  python execute_command.py --host server-deploy "whoami"
        """
    )
    parser.add_argument(
        'command',
        help='Command to execute on the server'
    )
    parser.add_argument(
        '--ssh-config',
        default='.ssh/config',
        help='Path to SSH config file (default: .ssh/config)'
    )
    parser.add_argument(
        '--host',
        default='server',
        help='SSH host alias from config file (default: server)'
    )
    parser.add_argument(
        '--show-stderr',
        action='store_true',
        help='Show stderr output even if command succeeds'
    )
    
    args = parser.parse_args()
    
    # Resolve paths relative to project root
    project_root = Path(__file__).parent.parent
    ssh_config_path = project_root / args.ssh_config
    
    if not ssh_config_path.exists():
        print(f"Error: SSH config file not found: {ssh_config_path}", file=sys.stderr)
        sys.exit(1)
    
    # Parse SSH config - we need to find the specific host
    ssh_config = {}
    current_host = None
    with open(ssh_config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if line.lower().startswith('host '):
                    host_name = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ''
                    if host_name == args.host:
                        current_host = args.host
                    else:
                        current_host = None
                elif current_host == args.host:
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        key = parts[0].lower()
                        value = parts[1]
                        if key == 'hostname':
                            ssh_config['hostname'] = value
                        elif key == 'user':
                            ssh_config['user'] = value
                        elif key == 'port':
                            ssh_config['port'] = int(value)
                        elif key == 'identityfile':
                            ssh_config['keyfile'] = value
    
    if not all(k in ssh_config for k in ['hostname', 'user', 'keyfile']):
        print(f"Error: Could not find host '{args.host}' in SSH config or missing required fields", file=sys.stderr)
        sys.exit(1)
    
    # Resolve keyfile path
    keyfile_path = Path(ssh_config['keyfile'])
    if not keyfile_path.is_absolute():
        keyfile_path = project_root / ssh_config['keyfile']
    
    if not keyfile_path.exists():
        print(f"Error: SSH key file not found: {keyfile_path}", file=sys.stderr)
        sys.exit(1)
    
    # Connect to server
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(
            hostname=ssh_config['hostname'],
            username=ssh_config['user'],
            key_filename=str(keyfile_path),
            port=ssh_config.get('port', 22),
            timeout=10
        )
        
        # Execute command
        exit_status, stdout, stderr = execute_ssh_command(ssh, args.command)
        
        # Read output
        stdout_text = stdout.read().decode()
        stderr_text = stderr.read().decode()
        
        # Print output
        if stdout_text:
            print(stdout_text, end='')
        
        if stderr_text and (exit_status != 0 or args.show_stderr):
            print(stderr_text, end='', file=sys.stderr)
        
        # Exit with the same status as the remote command
        sys.exit(exit_status)
        
    except paramiko.AuthenticationException:
        print("Error: Authentication failed. Check your SSH key.", file=sys.stderr)
        sys.exit(1)
    except paramiko.SSHException as e:
        print(f"Error: SSH connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        ssh.close()


if __name__ == '__main__':
    main()



