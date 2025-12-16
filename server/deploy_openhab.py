#!/usr/bin/env python3
"""
Deploy OpenHAB configuration files to the OpenHAB server via SSH.

This script deploys files from server/config/openhab_config/ to the OpenHAB server
using SSH/SCP based on the configuration in server/config/ssh_config.
"""

import os
import sys
import argparse
from pathlib import Path
import paramiko
from scp import SCPClient
import json
import time


def parse_ssh_config(config_path, host='server-deploy'):
    """Parse SSH config file and return connection parameters for a specific host."""
    config = {}
    current_host = None
    in_target_host = False
    
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split(None, 1)
                if len(parts) >= 1:
                    key = parts[0].lower()
                    value = parts[1] if len(parts) == 2 else ''
                    
                    # Check if this is a Host directive
                    if key == 'host':
                        current_host = value
                        in_target_host = (current_host == host)
                    
                    # Only capture config for the target host
                    elif in_target_host:
                        if key == 'hostname':
                            config['hostname'] = value
                        elif key == 'user':
                            config['user'] = value
                        elif key == 'port':
                            config['port'] = int(value)
                        elif key == 'identityfile':
                            config['keyfile'] = value
    
    return config


def log_debug(location, message, data=None, hypothesis_id=None):
    """Write debug log entry to NDJSON file."""
    # #region agent log
    log_entry = {
        "sessionId": "debug-session",
        "runId": "deploy-run",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000)
    }
    log_path = Path(__file__).parent.parent / ".cursor" / "debug.log"
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception:
        pass  # Silently fail if logging fails
    # #endregion


def execute_ssh_command(ssh, command):
    """
    Execute a command via SSH and return the result.
    
    Args:
        ssh: Paramiko SSH client
        command: Command to execute
    
    Returns:
        tuple: (exit_status, stdout_text, stderr_text) where stdout_text and stderr_text are decoded strings
    """
    # #region agent log
    log_debug("deploy_openhab.py:execute_ssh_command", "Executing SSH command", {"command": command}, "A")
    # #endregion
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    stdout_text = stdout.read().decode()
    stderr_text = stderr.read().decode()
    # #region agent log
    log_debug("deploy_openhab.py:execute_ssh_command", "SSH command result", {
        "command": command,
        "exit_status": exit_status,
        "stdout": stdout_text[:500],  # Limit size
        "stderr": stderr_text[:500]
    }, "A")
    # #endregion
    return exit_status, stdout_text, stderr_text


def deploy_files(ssh_config_path, local_config_dir, remote_base_dir='/etc/openhab', restart_service=True, dry_run=False, host='server-deploy'):
    """
    Deploy OpenHAB configuration files to the server.
    
    This function uses a dedicated deployment user (openhab-deploy) that has:
    - Group write permissions to OpenHAB config directories
    - Passwordless sudo access for restarting the OpenHAB service
    
    Args:
        ssh_config_path: Path to SSH config file
        local_config_dir: Local directory containing config files
        remote_base_dir: Remote OpenHAB configuration directory
        restart_service: Whether to restart OpenHAB service after deployment
        dry_run: If True, only print what would be done without actually doing it
        host: SSH config host to use (default: 'server-deploy')
    """
    # #region agent log
    log_debug("deploy_openhab.py:deploy_files", "Starting deployment", {
        "ssh_config_path": str(ssh_config_path),
        "local_config_dir": local_config_dir,
        "remote_base_dir": remote_base_dir,
        "restart_service": restart_service,
        "host": host
    }, "A")
    # #endregion
    
    # Parse SSH config
    ssh_config = parse_ssh_config(ssh_config_path, host=host)
    
    # #region agent log
    log_debug("deploy_openhab.py:deploy_files", "SSH config parsed", {"ssh_config": ssh_config}, "A")
    # #endregion
    
    if not ssh_config:
        print(f"Error: Host '{host}' not found in SSH config file: {ssh_config_path}")
        sys.exit(1)
    
    if not all(k in ssh_config for k in ['hostname', 'user', 'keyfile']):
        print(f"Error: SSH config for host '{host}' missing required fields (HostName, User, IdentityFile)")
        sys.exit(1)
    
    # Resolve paths
    project_root = Path(__file__).parent.parent
    local_config_path = project_root / local_config_dir
    keyfile_path = project_root / ssh_config['keyfile']
    
    # #region agent log
    log_debug("deploy_openhab.py:deploy_files", "Paths resolved", {
        "local_config_path": str(local_config_path),
        "keyfile_path": str(keyfile_path),
        "keyfile_exists": keyfile_path.exists()
    }, "A")
    # #endregion
    
    if not keyfile_path.exists():
        print(f"Error: SSH key file not found: {keyfile_path}")
        sys.exit(1)
    
    # File mapping: local_file -> remote_path (will be updated after detecting actual config dir)
    file_mappings = {
        'weather_station.items': f'{remote_base_dir}/items/weather_station.items',
        'weather_station.sitemap': f'{remote_base_dir}/sitemaps/weather_station.sitemap',
        'weather_station.rules': f'{remote_base_dir}/rules/weather_station.rules',
    }
    
    if dry_run:
        print("DRY RUN - No files will be deployed")
        print(f"\nUsing SSH host: {host}")
        print(f"Would connect to: {ssh_config['user']}@{ssh_config['hostname']}")
        print(f"Using key: {keyfile_path}")
        print("\nWould deploy files:")
        for local_file, remote_path in file_mappings.items():
            local_path = local_config_path / local_file
            if local_path.exists():
                print(f"  {local_path} -> {remote_path}")
            else:
                print(f"  {local_path} -> {remote_path} (FILE NOT FOUND)")
        if restart_service:
            print("\nWould restart OpenHAB service")
        return
    
    # Connect to server
    print(f"Using SSH host: {host}")
    print(f"Connecting to {ssh_config['user']}@{ssh_config['hostname']}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "Attempting SSH connection", {
            "hostname": ssh_config['hostname'],
            "username": ssh_config['user'],
            "port": ssh_config.get('port', 22)
        }, "A")
        # #endregion
        
        ssh.connect(
            hostname=ssh_config['hostname'],
            username=ssh_config['user'],
            key_filename=str(keyfile_path),
            port=ssh_config.get('port', 22),
            timeout=10
        )
        print("Connected successfully!")
        
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "SSH connection successful", {}, "A")
        # #endregion
        
        # Check OpenHAB version and actual config directory (Hypothesis B, G)
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "Checking OpenHAB installation", {}, "B")
        # #endregion
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "which openhab || which openhab-runtime || echo 'not-found'")
        openhab_path = stdout_text.strip()
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "OpenHAB binary path", {"openhab_path": openhab_path}, "B")
        # #endregion
        
        # Check actual OpenHAB config directory
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "ls -la /etc/openhab 2>/dev/null && echo 'EXISTS' || ls -la /var/lib/openhab 2>/dev/null && echo 'EXISTS_VARLIB' || ls -la /usr/share/openhab 2>/dev/null && echo 'EXISTS_USRSHARE' || echo 'NOT_FOUND'")
        config_check = stdout_text.strip()
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "OpenHAB config directory check", {
            "config_check": config_check,
            "remote_base_dir": remote_base_dir
        }, "B")
        # #endregion
        
        # Check OpenHAB 3.x userdata directory (Hypothesis B)
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "ls -la /var/lib/openhab 2>/dev/null && echo 'EXISTS_VARLIB_CONF' || echo 'NOT_FOUND'")
        var_lib_conf_check = stdout_text.strip()
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "OpenHAB userdata config check", {
            "var_lib_conf_check": var_lib_conf_check
        }, "B")
        # #endregion
        
        # Check which directory OpenHAB is actually using
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "cat /etc/default/openhab 2>/dev/null | grep OPENHAB_USERDATA || cat /etc/default/openhab2 2>/dev/null | grep OPENHAB_USERDATA || echo 'NOT_FOUND'")
        openhab_userdata = stdout_text.strip()
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "OpenHAB userdata environment variable", {
            "openhab_userdata": openhab_userdata
        }, "B")
        # #endregion
        
        # Determine actual config directory, preferring OPENHAB_CONF env var if set
        # Otherwise use the remote_base_dir parameter (defaults to /etc/openhab)
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "printenv OPENHAB_CONF || echo ''")
        openhab_conf_env = stdout_text.strip()
        if openhab_conf_env:
            actual_config_base = openhab_conf_env
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "Using OPENHAB_CONF env var", {
                "actual_config_base": actual_config_base
            }, "B")
            # #endregion
        else:
            # Use the remote_base_dir parameter (defaults to /etc/openhab)
            actual_config_base = remote_base_dir
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "Using specified config directory", {
                "actual_config_base": actual_config_base
            }, "B")
            # #endregion
        
        # Update file mappings to use actual config directory
        # Note: OPENHAB_CONF already points to the config directory (e.g., /etc/openhab)
        # which contains items/, sitemaps/, rules/ subdirectories directly
        file_mappings = {
            'weather_station.items': f'{actual_config_base}/items/weather_station.items',
            'weather_station.sitemap': f'{actual_config_base}/sitemaps/weather_station.sitemap',
            'weather_station.rules': f'{actual_config_base}/rules/weather_station.rules',
        }
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "File mappings updated", {
            "file_mappings": file_mappings,
            "actual_config_base": actual_config_base
        }, "B")
        # #endregion
        
        # Check OpenHAB service status (Hypothesis F)
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "sudo systemctl is-active openhab 2>&1 || sudo systemctl is-active openhab.service 2>&1 || echo 'unknown'")
        service_status = stdout_text.strip()
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "OpenHAB service status", {"service_status": service_status}, "F")
        # #endregion
        
        # Create remote directories if they don't exist
        print("\nCreating remote directories...")
        for dir_path in [
            f"{actual_config_base}/items",
            f"{actual_config_base}/sitemaps",
            f"{actual_config_base}/rules"
        ]:
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "Creating directory", {"dir_path": dir_path}, "A")
            # #endregion
            exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, f"mkdir -p {dir_path}")
            if exit_status != 0:
                error = stderr_text
                print(f"  Warning: Failed to create {dir_path}: {error}")
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "Directory creation failed", {
                    "dir_path": dir_path,
                    "error": error
                }, "A")
                # #endregion
        
        # Deploy files using SCP
        print("\nDeploying files...")
        scp = SCPClient(ssh.get_transport())
        
        # Create temp directory in user's home directory
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "echo $HOME")
        home_dir = stdout_text.strip()
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "Home directory retrieved", {"home_dir": home_dir}, "A")
        # #endregion
        temp_dir = f"{home_dir}/.openhab-deploy-tmp"
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "Creating temp directory", {"temp_dir": temp_dir}, "A")
        # #endregion
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, f"mkdir -p {temp_dir}")
        if exit_status != 0:
            error = stderr_text
            print(f"  Warning: Failed to create temp directory {temp_dir}: {error}")
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "Temp directory creation failed", {
                "temp_dir": temp_dir,
                "error": error
            }, "A")
            # #endregion
        
        deployed_count = 0
        for local_file, remote_path in file_mappings.items():
            local_path = local_config_path / local_file
            
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "Processing file", {
                "local_file": local_file,
                "local_path": str(local_path),
                "remote_path": remote_path,
                "local_exists": local_path.exists()
            }, "A")
            # #endregion
            
            if not local_path.exists():
                print(f"  Warning: {local_file} not found, skipping...")
                continue
            
            print(f"  Deploying {local_file} -> {remote_path}...")
            
            # Copy to temp location in user's home directory
            temp_path = f"{temp_dir}/{local_file}"
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "SCP put to temp", {
                "local_path": str(local_path),
                "temp_path": temp_path
            }, "A")
            # #endregion
            try:
                scp.put(str(local_path), temp_path)
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "SCP put successful", {"temp_path": temp_path}, "A")
                # #endregion
            except Exception as e:
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "SCP put failed", {"error": str(e)}, "A")
                # #endregion
                print(f"    ✗ SCP failed for {local_file}: {e}")
                continue
            
            # Copy to final location and set permissions (group permissions handle ownership)
            copy_cmd = f"cp {temp_path} {remote_path} && chmod 644 {remote_path} && rm {temp_path}"
            exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, copy_cmd)
            
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "File copy command executed", {
                "local_file": local_file,
                "remote_path": remote_path,
                "exit_status": exit_status
            }, "A")
            # #endregion
            
            if exit_status == 0:
                print(f"    ✓ Successfully deployed {local_file}")
                deployed_count += 1
                
                # Verify file exists and check permissions (Hypothesis C)
                exit_status, stdout_text2, stderr_text2 = execute_ssh_command(ssh, f"ls -la {remote_path} 2>&1")
                file_info = stdout_text2.strip()
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "File verification", {
                    "local_file": local_file,
                    "remote_path": remote_path,
                    "file_info": file_info
                }, "C")
                # #endregion
                
                # Check if OpenHAB user can read the file
                exit_status, stdout_text3, stderr_text3 = execute_ssh_command(ssh, f"sudo -u openhab test -r {remote_path} && echo 'READABLE' || echo 'NOT_READABLE'")
                readable_check = stdout_text3.strip()
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "OpenHAB user readability check", {
                    "local_file": local_file,
                    "remote_path": remote_path,
                    "readable": readable_check
                }, "C")
                # #endregion
            else:
                error = stderr_text
                print(f"    ✗ Failed to deploy {local_file}: {error}")
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "File deployment failed", {
                    "local_file": local_file,
                    "remote_path": remote_path,
                    "error": error
                }, "A")
                # #endregion
        
        scp.close()
        
        # Restart OpenHAB service (passwordless sudo via sudoers configuration)
        if restart_service and deployed_count > 0:
            print("\nRestarting OpenHAB service...")
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "Restarting OpenHAB service", {
                "deployed_count": deployed_count
            }, "D")
            # #endregion
            
            exit_status, stdout_text, stderr_text = execute_ssh_command(
                ssh, "sudo systemctl restart openhab"
            )
            
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "Service restart command executed", {
                "exit_status": exit_status
            }, "D")
            # #endregion
            
            if exit_status == 0:
                print("  ✓ OpenHAB service restarted successfully")
                # Wait a moment and verify service is running
                time.sleep(2)
                exit_status, stdout_text2, stderr_text2 = execute_ssh_command(ssh, "sudo systemctl is-active openhab 2>&1")
                final_status = stdout_text2.strip()
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "Service status after restart", {
                    "final_status": final_status
                }, "D")
                # #endregion
            else:
                error = stderr_text
                print(f"  ✗ Failed to restart OpenHAB service: {error}")
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "Service restart failed", {
                    "error": error
                }, "D")
                # #endregion
        
        # Final verification: Check if files are actually in the expected location
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "Final file existence check", {}, "A")
        # #endregion
        for local_file, remote_path in file_mappings.items():
            exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, f"test -f {remote_path} && echo 'EXISTS' || echo 'MISSING'")
            exists_check = stdout_text.strip()
            # #region agent log
            log_debug("deploy_openhab.py:deploy_files", "Final file check", {
                "local_file": local_file,
                "remote_path": remote_path,
                "exists": exists_check
            }, "A")
            # #endregion
            
            # Check for syntax errors in rules/items files (Hypothesis E)
            if local_file.endswith('.rules') or local_file.endswith('.items'):
                exit_status, stdout_text2, stderr_text2 = execute_ssh_command(ssh, f"head -5 {remote_path} 2>&1")
                file_preview = stdout_text2.strip()[:200]
                # #region agent log
                log_debug("deploy_openhab.py:deploy_files", "File content preview", {
                    "local_file": local_file,
                    "preview": file_preview
                }, "E")
                # #endregion
        
        print(f"\n✓ Deployment complete! ({deployed_count} files deployed)")
        
    except paramiko.AuthenticationException:
        print("Error: Authentication failed. Check your SSH key.")
        sys.exit(1)
    except paramiko.SSHException as e:
        print(f"Error: SSH connection failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        ssh.close()


def main():
    parser = argparse.ArgumentParser(
        description='Deploy OpenHAB configuration files to the server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy files and restart service (uses server-deploy host by default)
  python deploy_openhab.py
  
  # Dry run (see what would be done)
  python deploy_openhab.py --dry-run
  
  # Deploy without restarting service
  python deploy_openhab.py --no-restart
  
  # Use custom remote directory
  python deploy_openhab.py --remote-dir /opt/openhab
  
  # Use a different SSH config host
  python deploy_openhab.py --host server

Note: This script requires a dedicated deployment user (openhab-deploy) with:
  - Group write permissions to OpenHAB config directories
  - Passwordless sudo access for restarting the OpenHAB service
  See server/SETUP_DEPLOY_USER.md for setup instructions.
        """
    )
    parser.add_argument(
        '--ssh-config',
        default='server/config/ssh_config',
        help='Path to SSH config file (default: server/config/ssh_config)'
    )
    parser.add_argument(
        '--config-dir',
        default='server/config/openhab_config',
        help='Local directory containing config files (default: server/config/openhab_config)'
    )
    parser.add_argument(
        '--remote-dir',
        default='/etc/openhab',
        help='Remote OpenHAB configuration directory (default: /etc/openhab)'
    )
    parser.add_argument(
        '--no-restart',
        action='store_true',
        help='Do not restart OpenHAB service after deployment'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually deploying'
    )
    parser.add_argument(
        '--host',
        default='server-deploy',
        help='SSH config host to use (default: server-deploy)'
    )
    
    args = parser.parse_args()
    
    # Resolve paths relative to project root
    project_root = Path(__file__).parent.parent
    ssh_config_path = project_root / args.ssh_config
    
    if not ssh_config_path.exists():
        print(f"Error: SSH config file not found: {ssh_config_path}")
        sys.exit(1)
    
    deploy_files(
        ssh_config_path=str(ssh_config_path),
        local_config_dir=args.config_dir,
        remote_base_dir=args.remote_dir,
        restart_service=not args.no_restart,
        dry_run=args.dry_run,
        host=args.host
    )


if __name__ == '__main__':
    main()

