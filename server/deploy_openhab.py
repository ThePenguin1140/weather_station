#!/usr/bin/env python3
"""
Deploy OpenHAB configuration files to the OpenHAB server via SSH.

This script deploys files from server/config/openhab_config/ to the OpenHAB server
using SSH/SCP based on the configuration in .ssh/config.
"""

import os
import sys
import argparse
from pathlib import Path
import paramiko
from scp import SCPClient
import json
import re
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


def ensure_restricted_sudo(ssh, expected_user=None):
    """
    Verify that the remote user does NOT have unrestricted sudo access.
    
    This is a safety check to avoid running the deploy script with a user that
    can run arbitrary commands as root (e.g. sudo ALL=(ALL:ALL) ALL).
    """
    # Determine the remote user account
    exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "whoami")
    remote_user = stdout_text.strip() or "<unknown>"

    if expected_user and remote_user != expected_user:
        print(
            f"Warning: SSH config user is '{expected_user}', "
            f"but remote reports 'whoami' as '{remote_user}'."
        )

    # Get sudo privileges for the remote user without prompting for a password
    exit_status, stdout_text, stderr_text = execute_ssh_command(
        ssh, "sudo -l -n 2>&1"
    )

    if exit_status != 0:
        # If sudo requires a password or is not configured, fail fast.
        print(
            f"Error: unable to run 'sudo -l -n' as remote user '{remote_user}'.\n"
            "This likely means sudo is not configured for non-interactive use.\n"
            "For safety, this deploy script requires a dedicated deployment user\n"
            "with limited, passwordless sudo as described in server/SETUP_DEPLOY_USER.md."
        )
        sys.exit(1)

    sudo_output = stdout_text

    # Detect dangerous sudo rules that effectively grant full root access.
    #
    # Examples we want to block:
    #   (ALL : ALL) ALL
    #   (ALL) ALL
    #   (ALL) NOPASSWD: ALL
    #   (ALL) PASSWD: ALL
    #
    # These mean the user can run any command as any user, which is more
    # privilege than the deploy user should have.
    dangerous_pattern = re.compile(
        r"\(ALL(?:[^)]*)\)\s*(?:NOPASSWD:|PASSWD:)?\s*ALL\b"
    )

    dangerous_lines = []
    for line in sudo_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip headers/metadata lines from sudo -l
        if stripped.startswith("Matching Defaults entries") or stripped.startswith(
            "Defaults"
        ) or stripped.startswith("User "):
            continue

        if dangerous_pattern.search(stripped):
            dangerous_lines.append(stripped)

    if dangerous_lines:
        print(
            f"Error: remote user '{remote_user}' appears to have unrestricted sudo access.\n"
            "The following sudoers entries look unsafe:\n"
            + "\n".join(f"  {line}" for line in dangerous_lines)
            + "\n\nFor safety, this deploy script refuses to run with a user that has\n"
            "full sudo privileges. Please create a dedicated deployment user with only\n"
            "the minimal sudo rules described in server/SETUP_DEPLOY_USER.md."
        )
        sys.exit(1)


def deploy_receiver_service(ssh, project_root, remote_dir, service_name, deploy_config=False):
    """
    Deploy receiver.py and config.json to the server, ensure Python dependencies
    are installed, and restart the existing systemd service.
    
    This function assumes the systemd service unit already exists on the server.
    It does NOT create or modify systemd unit files. The service must be created
    once as root using the instructions in server/SETUP_DEPLOY_USER.md (Step 7).
    
    Args:
        ssh: Paramiko SSH client
        project_root: Path to the project root directory
        remote_dir: Remote directory for receiver files
        service_name: Name of the existing systemd service to restart
        deploy_config: Whether to deploy config.json alongside receiver.py
    
    Returns:
        bool: True if deployment and restart succeeded, False otherwise
    """
    log_debug(
        "deploy_openhab.py:deploy_receiver_service",
        "Starting receiver deployment",
        {
            "remote_dir": remote_dir,
            "service_name": service_name,
            "deploy_config": deploy_config,
        },
        "R",
    )

    receiver_src_dir = project_root / "server" / "src"
    # Always deploy receiver.py; only deploy config.json when explicitly requested.
    receiver_files = ["receiver.py"]
    if deploy_config:
        receiver_files.append("config.json")
    # Requirements file for receiver dependencies (pyRF24, requests, etc.)
    requirements_path = project_root / "server" / "requirements.txt"
    deps_ok = True

    missing_files = [
        f for f in receiver_files if not (receiver_src_dir / f).exists()
    ]
    if missing_files:
        print(
            "Receiver deployment skipped: missing local files: "
            + ", ".join(missing_files)
        )
        log_debug(
            "deploy_openhab.py:deploy_receiver_service",
            "Missing local receiver files",
            {"missing_files": missing_files},
            "R",
        )
        return False

    print("\nDeploying receiver application files...")

    # Ensure remote directory exists
    mkdir_cmd = f"mkdir -p {remote_dir}"
    exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, mkdir_cmd)
    if exit_status != 0:
        print(f"  Warning: Failed to create receiver directory {remote_dir}: {stderr_text}")
        log_debug(
            "deploy_openhab.py:deploy_receiver_service",
            "Receiver directory creation failed",
            {"remote_dir": remote_dir, "error": stderr_text},
            "R",
        )
        return False

    scp = SCPClient(ssh.get_transport())
    deployed_count = 0
    try:
        for filename in receiver_files:
            local_path = receiver_src_dir / filename
            remote_path = f"{remote_dir.rstrip('/')}/{filename}"

            log_debug(
                "deploy_openhab.py:deploy_receiver_service",
                "Deploying receiver file",
                {
                    "local_path": str(local_path),
                    "remote_path": remote_path,
                },
                "R",
            )

            if not local_path.exists():
                print(f"  Warning: {local_path} not found, skipping...")
                continue

            print(f"  Deploying {filename} -> {remote_path}...")
            try:
                scp.put(str(local_path), remote_path)
                print(f"    ✓ Successfully deployed {filename}")
                deployed_count += 1
                log_debug(
                    "deploy_openhab.py:deploy_receiver_service",
                    "SCP put successful",
                    {"remote_path": remote_path},
                    "R",
                )
            except Exception as e:
                print(f"    ✗ SCP failed for {filename}: {e}")
                log_debug(
                    "deploy_openhab.py:deploy_receiver_service",
                    "SCP put failed",
                    {"remote_path": remote_path, "error": str(e)},
                    "R",
                )
                return False
    finally:
        try:
            scp.close()
        except Exception:
            pass

    # Deploy requirements.txt for the receiver and attempt to install/update
    # Python dependencies on the target server so that receiver.py can run.
    if requirements_path.exists():
        requirements_remote_path = f"{remote_dir.rstrip('/')}/requirements.txt"
        print("\nDeploying receiver Python requirements...")
        log_debug(
            "deploy_openhab.py:deploy_receiver_service",
            "Deploying requirements.txt for receiver",
            {
                "local_path": str(requirements_path),
                "remote_path": requirements_remote_path,
            },
            "R",
        )

        scp = SCPClient(ssh.get_transport())
        try:
            scp.put(str(requirements_path), requirements_remote_path)
            print(f"  ✓ requirements.txt -> {requirements_remote_path}")
            log_debug(
                "deploy_openhab.py:deploy_receiver_service",
                "requirements.txt SCP put successful",
                {"remote_path": requirements_remote_path},
                "R",
            )
        except Exception as e:
            deps_ok = False
            print(f"  Warning: Failed to deploy requirements.txt: {e}")
            log_debug(
                "deploy_openhab.py:deploy_receiver_service",
                "requirements.txt SCP put failed",
                {
                    "remote_path": requirements_remote_path,
                    "error": str(e),
                },
                "R",
            )
        finally:
            try:
                scp.close()
            except Exception:
                pass

        if deps_ok:
            # Create or reuse a dedicated Python virtual environment for the receiver.
            remote_dir_clean = remote_dir.rstrip("/")
            venv_dir = f"{remote_dir_clean}/.venv"
            python_bin = f"{venv_dir}/bin/python"

            print("\nEnsuring Python virtual environment for receiver...")
            venv_cmd = (
                f"cd {remote_dir_clean} && "
                f"(test -x {python_bin} || python3 -m venv .venv)"
            )
            exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, venv_cmd)
            log_debug(
                "deploy_openhab.py:deploy_receiver_service",
                "Receiver venv ensure command finished",
                {
                    "command": venv_cmd,
                    "exit_status": exit_status,
                    "stdout": stdout_text[:500],
                    "stderr": stderr_text[:500],
                    "venv_dir": venv_dir,
                },
                "R",
            )

            if exit_status != 0:
                deps_ok = False
                print(
                    "  Warning: Failed to create or verify Python virtual environment "
                    f"at {venv_dir}."
                )
                print(
                    "           The deploy script avoids installing into the "
                    "system Python environment because it is externally managed "
                    "(PEP 668)."
                )
                print(
                    "           Please ensure the 'python3-venv' package is "
                    "installed on the server and that this command succeeds:"
                )
                print(f"             cd {remote_dir_clean} && python3 -m venv .venv")
                if stderr_text.strip():
                    print("           Error output (truncated):")
                    for line in stderr_text.strip().splitlines()[-5:]:
                        print(f"             {line}")
            else:
                print(f"  ✓ Virtual environment available at {venv_dir}")
                print("\nInstalling/updating receiver Python dependencies in venv...")
                pip_cmd = (
                    f"cd {remote_dir_clean} && "
                    f"{python_bin} -m pip install --upgrade pip && "
                    f"{python_bin} -m pip install --upgrade -r requirements.txt"
                )
                exit_status, stdout_text, stderr_text = execute_ssh_command(
                    ssh, pip_cmd
                )
                log_debug(
                    "deploy_openhab.py:deploy_receiver_service",
                    "Receiver dependency install command finished",
                    {
                        "command": pip_cmd,
                        "exit_status": exit_status,
                        "stdout": stdout_text[:500],
                        "stderr": stderr_text[:500],
                        "venv_dir": venv_dir,
                    },
                    "R",
                )

                if exit_status == 0:
                    print(
                        "  ✓ Receiver Python dependencies installed/updated "
                        "inside virtual environment"
                    )
                    print(
                        "  Note: Ensure your weather-station systemd service uses "
                        "this venv's Python, for example:\n"
                        f"        ExecStart={python_bin} {remote_dir_clean}/receiver.py"
                    )
                else:
                    deps_ok = False
                    print(
                        "  Warning: Failed to install/update receiver Python "
                        "dependencies inside virtual environment."
                    )
                    print(
                        "           Please ensure the following command succeeds "
                        "on the server as the same user that manages the receiver:"
                    )
                    print(f"             {pip_cmd}")
                    if stderr_text.strip():
                        print("           Error output (truncated):")
                        for line in stderr_text.strip().splitlines()[-5:]:
                            print(f"             {line}")
    else:
        deps_ok = False
        print(
            "  Warning: server/requirements.txt not found locally; "
            "receiver dependencies were not installed on the server."
        )
        log_debug(
            "deploy_openhab.py:deploy_receiver_service",
            "Local requirements.txt missing",
            {"requirements_path": str(requirements_path)},
            "R",
        )

    # Restart the existing service (assumes it was created as per SETUP_DEPLOY_USER.md)
    if deployed_count > 0:
        print(f"\nRestarting receiver service '{service_name}'...")
        log_debug(
            "deploy_openhab.py:deploy_receiver_service",
            "Restarting receiver service",
            {"service_name": service_name},
            "R",
        )
        restart_cmd = f"sudo systemctl restart {service_name}"
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, restart_cmd)
        if exit_status != 0:
            print(f"  ✗ Failed to restart receiver service: {stderr_text}")
            print(
                f"  Note: The '{service_name}' service must exist on the server.\n"
                f"        If it doesn't, create it as root per server/SETUP_DEPLOY_USER.md Step 7."
            )
            log_debug(
                "deploy_openhab.py:deploy_receiver_service",
                "Service restart failed",
                {"error": stderr_text},
                "R",
            )
            return False

    # Verify service is active
    status_cmd = f"systemctl is-active {service_name}"
    exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, status_cmd)
    service_status = stdout_text.strip()
    log_debug(
        "deploy_openhab.py:deploy_receiver_service",
        "Receiver service status",
        {"status": service_status},
        "R",
    )

    if service_status == "active":
        print(f"  ✓ Receiver service '{service_name}' is active")
        if not deps_ok:
            print(
                "  ⚠ Note: The receiver service is running, but there were "
                "problems installing or updating Python dependencies. "
                "See messages above."
            )
        return deps_ok

    print(
        f"  ✗ Receiver service '{service_name}' is not active "
        f"(status: {service_status})"
    )
    print(
        f"  Note: The '{service_name}' service must exist on the server.\n"
        f"        If it doesn't, create it as root per server/SETUP_DEPLOY_USER.md Step 7."
    )
    return False


def deploy_files(
    ssh_config_path,
    local_config_dir,
    remote_base_dir="/etc/openhab",
    restart_service=True,
    dry_run=False,
    host="server-deploy",
    deploy_receiver=True,
    receiver_remote_dir="~/weather_station/server/src",
    receiver_service_name="weather-station",
    deploy_openhab_config=True,
    deploy_receiver_config=False,
    deploy_openhabian_conf=False,
):
    """
    Deploy OpenHAB configuration files and receiver application to the server.
    
    This function uses a dedicated deployment user (openhab-deploy) that has:
    - Group write permissions to OpenHAB config directories
    - Passwordless sudo access for restarting the OpenHAB and weather-station services
    
    The receiver deployment assumes the weather-station systemd service already
    exists on the server. It deploys receiver.py and config.json, then restarts
    the service. The service must be created once as root per SETUP_DEPLOY_USER.md.
    
    Args:
        ssh_config_path: Path to SSH config file
        local_config_dir: Local directory containing config files
        remote_base_dir: Remote OpenHAB configuration directory
        restart_service: Whether to restart OpenHAB service after deployment
        dry_run: If True, only print what would be done without actually doing it
        host: SSH config host to use (default: 'server-deploy')
        deploy_receiver: Whether to deploy receiver files and restart the service
        receiver_remote_dir: Remote directory for receiver.py and config.json
        receiver_service_name: Name of the existing systemd service to restart
        deploy_openhab_config: Whether to deploy OpenHAB config files and restart the
            OpenHAB service
        deploy_receiver_config: Whether to deploy receiver config.json alongside
            receiver.py (off by default)
        deploy_openhabian_conf: Whether to deploy openhabian.conf to the remote host
            (off by default)
    """
    # #region agent log
    log_debug(
        "deploy_openhab.py:deploy_files",
        "Starting deployment",
        {
            "ssh_config_path": str(ssh_config_path),
            "local_config_dir": local_config_dir,
            "remote_base_dir": remote_base_dir,
            "restart_service": restart_service,
            "host": host,
            "deploy_receiver": deploy_receiver,
            "receiver_remote_dir": receiver_remote_dir,
            "receiver_service_name": receiver_service_name,
            "deploy_openhab_config": deploy_openhab_config,
            "deploy_receiver_config": deploy_receiver_config,
            "deploy_openhabian_conf": deploy_openhabian_conf,
        },
        "A",
    )
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
    deployed_count = 0
    
    if dry_run:
        print("DRY RUN - No files will be deployed")
        print(f"\nUsing SSH host: {host}")
        print(f"Would connect to: {ssh_config['user']}@{ssh_config['hostname']}")
        print(f"Using key: {keyfile_path}")
        if deploy_openhab_config:
            print("\nWould deploy OpenHAB config files:")
            for local_file, remote_path in file_mappings.items():
                local_path = local_config_path / local_file
                if local_path.exists():
                    print(f"  {local_path} -> {remote_path}")
                else:
                    print(f"  {local_path} -> {remote_path} (FILE NOT FOUND)")
        else:
            print("\nSkipping OpenHAB config deployment (receiver-only mode).")
        if deploy_receiver:
            receiver_src_dir = project_root / "server" / "src"
            requirements_path = project_root / "server" / "requirements.txt"
            print("\nWould deploy receiver application files:")
            receiver_files = ["receiver.py"]
            if deploy_receiver_config:
                receiver_files.append("config.json")
            for filename in receiver_files:
                local_path = receiver_src_dir / filename
                remote_path = f"{receiver_remote_dir.rstrip('/')}/{filename}"
                if local_path.exists():
                    print(f"  {local_path} -> {remote_path}")
                else:
                    print(f"  {local_path} -> {remote_path} (FILE NOT FOUND)")
            print("\nWould handle receiver Python dependencies:")
            if requirements_path.exists():
                print(f"  {requirements_path} -> "
                      f"{receiver_remote_dir.rstrip('/')}/requirements.txt")
                print("  Then run on the server (using a virtual environment):")
                print(
                    f"    cd {receiver_remote_dir.rstrip('/')} && "
                    "python3 -m venv .venv"
                )
                print(
                    f"    cd {receiver_remote_dir.rstrip('/')} && "
                    ".venv/bin/python -m pip install --upgrade pip"
                )
                print(
                    f"    cd {receiver_remote_dir.rstrip('/')} && "
                    ".venv/bin/python -m pip install --upgrade -r requirements.txt"
                )
            else:
                print(
                    f"  server/requirements.txt (LOCAL FILE NOT FOUND) "
                    "- dependencies would NOT be installed automatically"
                )
            print(
                f"\nWould restart existing systemd service "
                f"'{receiver_service_name}.service'\n"
                f"(Note: service must already exist on server, see SETUP_DEPLOY_USER.md Step 7)"
            )
        if deploy_openhabian_conf:
            openhabian_local_path = local_config_path / "openhabian.conf"
            print("\nWould deploy openhabian.conf:")
            if openhabian_local_path.exists():
                print(f"  {openhabian_local_path} -> $HOME/openhabian.conf")
            else:
                print(
                    f"  {openhabian_local_path} -> $HOME/openhabian.conf "
                    "(LOCAL FILE NOT FOUND)"
                )
        if restart_service and deploy_openhab_config:
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

        # Safety check: ensure the remote user does NOT have unrestricted sudo.
        ensure_restricted_sudo(ssh, expected_user=ssh_config.get('user'))
        
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
        
        # Create temp directory parent (home) used by both OpenHAB deploy and receiver
        exit_status, stdout_text, stderr_text = execute_ssh_command(ssh, "echo $HOME")
        home_dir = stdout_text.strip()
        # #region agent log
        log_debug("deploy_openhab.py:deploy_files", "Home directory retrieved", {"home_dir": home_dir}, "A")
        # #endregion

        if deploy_openhab_config:
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
            
            # Deploy OpenHAB configuration files using SCP
            print("\nDeploying OpenHAB configuration files...")
            scp = SCPClient(ssh.get_transport())
            
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
        if deploy_openhab_config and restart_service and deployed_count > 0:
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
        
        if deploy_openhab_config:
            # Final verification: Check if files are actually in the expected location
            # #region agent log
            log_debug(
                "deploy_openhab.py:deploy_files",
                "Final file existence check",
                {},
                "A",
            )
            # #endregion
            for local_file, remote_path in file_mappings.items():
                exit_status, stdout_text, stderr_text = execute_ssh_command(
                    ssh,
                    f"test -f {remote_path} && echo 'EXISTS' || echo 'MISSING'",
                )
                exists_check = stdout_text.strip()
                # #region agent log
                log_debug(
                    "deploy_openhab.py:deploy_files",
                    "Final file check",
                    {
                        "local_file": local_file,
                        "remote_path": remote_path,
                        "exists": exists_check,
                    },
                    "A",
                )
                # #endregion

                # Check for syntax errors in rules/items files (Hypothesis E)
                if local_file.endswith('.rules') or local_file.endswith('.items'):
                    exit_status, stdout_text2, stderr_text2 = execute_ssh_command(
                        ssh, f"head -5 {remote_path} 2>&1"
                    )
                    file_preview = stdout_text2.strip()[:200]
                    # #region agent log
                    log_debug(
                        "deploy_openhab.py:deploy_files",
                        "File content preview",
                        {"local_file": local_file, "preview": file_preview},
                        "E",
                    )
                    # #endregion

        # Resolve receiver remote directory (expand ~ to home if needed)
        receiver_remote_dir_resolved = receiver_remote_dir
        if deploy_receiver:
            if receiver_remote_dir == "~" and home_dir:
                receiver_remote_dir_resolved = home_dir
            elif receiver_remote_dir.startswith("~/") and home_dir:
                receiver_remote_dir_resolved = (
                    f"{home_dir}/{receiver_remote_dir[2:]}"
                )

        # Optionally deploy openhabian.conf into the remote user's home directory.
        if deploy_openhabian_conf:
            openhabian_local_path = local_config_path / "openhabian.conf"
            print("\nDeploying openhabian.conf...")
            if not openhabian_local_path.exists():
                print(
                    f"  Warning: {openhabian_local_path} not found, "
                    "skipping openhabian.conf deployment."
                )
                log_debug(
                    "deploy_openhab.py:deploy_files",
                    "openhabian.conf missing locally",
                    {"local_path": str(openhabian_local_path)},
                    "A",
                )
            elif not home_dir:
                print(
                    "  Warning: could not determine remote home directory; "
                    "skipping openhabian.conf deployment."
                )
                log_debug(
                    "deploy_openhab.py:deploy_files",
                    "Remote home directory not available for openhabian.conf",
                    {},
                    "A",
                )
            else:
                scp = SCPClient(ssh.get_transport())
                remote_openhabian_path = f"{home_dir.rstrip('/')}/openhabian.conf"
                try:
                    log_debug(
                        "deploy_openhab.py:deploy_files",
                        "Deploying openhabian.conf",
                        {
                            "local_path": str(openhabian_local_path),
                            "remote_path": remote_openhabian_path,
                        },
                        "A",
                    )
                    scp.put(str(openhabian_local_path), remote_openhabian_path)
                    print(
                        f"  ✓ {openhabian_local_path.name} -> "
                        f"{remote_openhabian_path}"
                    )
                except Exception as e:
                    print(f"  ✗ Failed to deploy openhabian.conf: {e}")
                    log_debug(
                        "deploy_openhab.py:deploy_files",
                        "openhabian.conf deployment failed",
                        {
                            "local_path": str(openhabian_local_path),
                            "remote_path": remote_openhabian_path,
                            "error": str(e),
                        },
                        "A",
                    )
                finally:
                    try:
                        scp.close()
                    except Exception:
                        pass

        receiver_ok = True
        if deploy_receiver:
            receiver_ok = deploy_receiver_service(
                ssh=ssh,
                project_root=project_root,
                remote_dir=receiver_remote_dir_resolved,
                service_name=receiver_service_name,
                deploy_config=deploy_receiver_config,
            )

        print(f"\n✓ Deployment complete! ({deployed_count} OpenHAB files deployed)")
        if deploy_receiver:
            if receiver_ok:
                print(
                    f"✓ Receiver files deployed and service "
                    f"'{receiver_service_name}' restarted"
                )
            else:
                print(
                    f"✗ Receiver deployment encountered issues (see output above)"
                )
        
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
        description='Deploy OpenHAB configuration files and receiver application to the server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy files and restart services (uses server-deploy host by default)
  python deploy_openhab.py
  
  # Dry run (see what would be done)
  python deploy_openhab.py --dry-run
  
  # Deploy without restarting OpenHAB service
  python deploy_openhab.py --no-restart
  
  # Deploy only OpenHAB config (skip receiver deployment)
  python deploy_openhab.py --skip-receiver
  
  # Deploy only receiver (skip OpenHAB config files and OpenHAB restart)
  python deploy_openhab.py --skip-openhab
  
  # Use custom remote directory
  python deploy_openhab.py --remote-dir /opt/openhab
  
  # Use a different SSH config host
  python deploy_openhab.py --host server

Note: This script requires a dedicated deployment user (openhab-deploy) with:
  - Group write permissions to OpenHAB config directories
  - Passwordless sudo access for restarting the OpenHAB and weather-station services

The receiver deployment assumes the weather-station systemd service already exists
on the server. This script does NOT create or modify systemd unit files; it only
deploys receiver.py and config.json, then restarts the existing service.

See server/SETUP_DEPLOY_USER.md for setup instructions (including creating the
weather-station service once as root in Step 7).
        """
    )
    parser.add_argument(
        '--ssh-config',
        default='.ssh/config',
        help='Path to SSH config file (default: .ssh/config)'
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
    parser.add_argument(
        '--skip-receiver',
        action='store_true',
        help='Skip receiver deployment (do not deploy receiver.py/config.json or restart weather-station service)'
    )
    parser.add_argument(
        '--skip-openhab',
        action='store_true',
        help='Skip OpenHAB config deployment (do not deploy items/rules/sitemap or restart OpenHAB service)'
    )
    parser.add_argument(
        '--receiver-dir',
        default='~/weather_station/server/src',
        help='Remote directory for receiver.py and config.json '
             '(default: ~/weather_station/server/src)'
    )
    parser.add_argument(
        '--receiver-service-name',
        default='weather-station',
        help='Name of the existing systemd service for the receiver '
             '(default: weather-station). Service must already exist on server.'
    )
    parser.add_argument(
        '--receiver_config',
        action='store_true',
        help='Also deploy receiver config.json alongside receiver.py (off by default)'
    )
    parser.add_argument(
        '--openhab-config',
        action='store_true',
        dest='openhab_config',
        help='Deploy openhabian.conf to the remote host (off by default)'
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
        host=args.host,
        deploy_receiver=not args.skip_receiver,
        receiver_remote_dir=args.receiver_dir,
        receiver_service_name=args.receiver_service_name,
        deploy_openhab_config=not args.skip_openhab,
        deploy_receiver_config=args.receiver_config,
        deploy_openhabian_conf=args.openhab_config,
    )


if __name__ == '__main__':
    main()

