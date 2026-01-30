# Setting Up the OpenHAB Deployment User

This guide explains how to set up a dedicated deployment user (`openhab-deploy`) on your OpenHAB server. This user will have the necessary permissions to:

- Deploy OpenHAB configuration files
- Deploy receiver application files (`receiver.py` and `config.json`)
- Restart the OpenHAB and weather-station services (without sudo password prompts)

**Design Note**: The deployment script (`deploy_openhab.py`) does NOT create or modify systemd unit files. The weather-station service must be created once as root (see Step 7). After that, the deployment script only updates application files and restarts the existing service.

## Prerequisites

- Root or sudo access to the OpenHAB server
- OpenHAB installed and running
- SSH access to the server

## Step 1: Create the Deployment User

Create a new user account specifically for deployments:

```bash
sudo useradd -r -m -s /bin/bash openhab-deploy
```

- `-r`: Create a system user (no login by default)
- `-m`: Create home directory
- `-s /bin/bash`: Set bash as shell (needed for SSH operations)

## Step 2: Add User to OpenHAB Group

Add the deployment user to the `openhab` group to grant write access to OpenHAB configuration directories:

```bash
sudo usermod -a -G openhab,spi,gpio openhab-deploy
```

Verify the user was added to the group:

```bash
groups openhab-deploy
```

You should see `openhab` in the output.

## Step 3: Set Up Directory Permissions

Ensure OpenHAB configuration directories are group-writable and owned by the `openhab` group:

```bash
# Set group ownership on OpenHAB config directories
sudo chgrp -R openhab /etc/openhab

# Make directories group-writable
sudo find /etc/openhab -type d -exec chmod g+w {} \;

# Ensure files are group-readable
sudo find /etc/openhab -type f -exec chmod g+r {} \;
```

If the directories don't exist yet, create them with proper permissions:

```bash
sudo mkdir -p /etc/openhab/{items,sitemaps,rules,persistence,services}
sudo chown -R openhab:openhab /etc/openhab
sudo chmod -R g+w /etc/openhab
```

**Also set up permissions for OpenHAB userdata directory (for JSONDB files like UI components):**

```bash
# Ensure jsondb directory exists and is group-writable
sudo mkdir -p /var/lib/openhab/jsondb

# Set group ownership on jsondb directory
sudo chgrp openhab /var/lib/openhab/jsondb

# Make jsondb directory group-writable
sudo chmod g+w /var/lib/openhab/jsondb

# Ensure existing files in jsondb are group-readable (if any)
sudo find /var/lib/openhab/jsondb -type f -exec chmod g+r {} \; 2>/dev/null || true
```

**Note**: The `/var/lib/openhab` directory is typically owned by the `openhab` user. By adding the deployment user to the `openhab` group (Step 2) and making the `jsondb` subdirectory group-writable, the deployment user can deploy UI component files (`uicomponents_ui_page.json`) to this location.

## Step 4: Generate SSH Key Pair

On your **local machine** (where you'll run the deployment script), generate a new SSH key pair for the deployment user:

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -f .ssh/openhab_key -C "openhab-deploy-key" -N ""

# Or if ed25519 is not available, use RSA:
# ssh-keygen -t rsa -b 4096 -f .ssh/openhab_key -C "openhab-deploy-key" -N ""
```

This creates:

- `.ssh/openhab_key` (private key - keep this secure, do NOT commit to git)
- `.ssh/openhab_key.pub` (public key - safe to share)

**Important**: Ensure `.ssh/openhab_key` is listed in your `.gitignore` file to prevent accidentally committing the private key.

## Step 5: Install Public Key on Server

Copy the public key to the server and add it to the deployment user's authorized_keys:

### Option A: Using ssh-copy-id (if you have password access)

```bash
ssh-copy-id -i .ssh/openhab_key.pub openhab-deploy@YOUR_SERVER_IP
```

### Option B: Manual Installation

1. Display the public key:

   ```bash
   cat .ssh/openhab_key.pub
   ```

2. On the server, as root or with sudo:

   ```bash
   # Create .ssh directory if it doesn't exist
   sudo mkdir -p /home/openhab-deploy/.ssh

   # Add the public key to authorized_keys
   sudo sh -c "cat >> /home/openhab-deploy/.ssh/authorized_keys" << 'EOF'
   # Paste your public key here (from .ssh/openhab_key.pub)
   EOF

   # Set proper permissions
   sudo chown -R openhab-deploy:openhab-deploy /home/openhab-deploy/.ssh
   sudo chmod 700 /home/openhab-deploy/.ssh
   sudo chmod 600 /home/openhab-deploy/.ssh/authorized_keys
   ```

### Option C: Copy via Existing SSH Access

If you already have SSH access to the server:

```bash
# Copy public key to server
scp .ssh/openhab_key.pub admin@YOUR_SERVER_IP:/tmp/

# On the server, install the key
ssh admin@YOUR_SERVER_IP
sudo mkdir -p /home/openhab-deploy/.ssh
sudo sh -c "cat /tmp/openhab_key.pub >> /home/openhab-deploy/.ssh/authorized_keys"
sudo chown -R openhab-deploy:openhab-deploy /home/openhab-deploy/.ssh
sudo chmod 700 /home/openhab-deploy/.ssh
sudo chmod 600 /home/openhab-deploy/.ssh/authorized_keys
sudo rm /tmp/openhab_key.pub
```

## Step 6: Configure Sudoers

Configure sudo to allow the deployment user to restart services and check their status without a password. Create a dedicated sudoers drop-in file:

```bash
sudo tee /etc/sudoers.d/openhab-deploy >/dev/null << 'EOF'
# Sudoers configuration for openhab-deploy user
# Allows the openhab-deploy user to restart openHAB service without password
# Also allows checking service status (needed for proper restart verification)
openhab-deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart openhab
openhab-deploy ALL=(ALL) NOPASSWD: /bin/systemctl is-active openhab
openhab-deploy ALL=(ALL) NOPASSWD: /bin/systemctl status openhab
openhab-deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart weather-station
EOF
sudo chmod 440 /etc/sudoers.d/openhab-deploy
```

**Required permissions:**

- **`restart openhab`**: Needed so the deployment script can restart OpenHAB after pushing new configuration files.
- **`is-active openhab`**: Allows the deployment script to verify OpenHAB service status during restart verification.
- **`status openhab`**: Allows checking detailed service status for troubleshooting.
- **`restart weather-station`**: Allows the deployment user to restart the weather station receiver service (see the next step).

**Important**: The `is-active` and `status` permissions are critical for proper restart verification. Without these, the deployment script cannot properly verify that OpenHAB has fully initialized after a restart, which can lead to rapid successive restarts and bundle lock timeouts.

You can verify the syntax is correct with:

```bash
sudo visudo -c
```

## Step 7: Create the Weather Station Receiver Service (Required for Receiver Deployment)

If you want the deployment script to manage the receiver application, you must create the `weather-station.service` systemd unit on the server **once as root**. The deployment script (`deploy_openhab.py`) will then:

- Deploy `receiver.py` and `config.json` to the remote directory
- Restart the existing service

**Important**: The deployment script does NOT create or modify systemd unit files. It only deploys application files and restarts the pre-existing service. You must create the service unit manually using the instructions below.

You can create it with `tee`:

```bash
sudo tee /etc/systemd/system/weather-station.service >/dev/null << 'EOF'
[Unit]
Description=Weather Station Receiver
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/weather_station/server/src
ExecStart=/usr/bin/python3 /home/pi/weather_station/server/src/receiver.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

Or edit the file manually with your preferred editor and paste the same content:

```ini
[Unit]
Description=Weather Station Receiver
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/weather_station/server/src
ExecStart=/usr/bin/python3 /home/pi/weather_station/server/src/receiver.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Make sure `User` and `WorkingDirectory` match how you have cloned this repository on the Raspberry Pi (for example, use a different user instead of `pi` if needed).

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable weather-station
sudo systemctl start weather-station
```

After this, the `openhab-deploy` user will be able to restart the service non‑interactively via:

```bash
sudo systemctl restart weather-station
```

For additional background, see the **Running as a Service** section in `server/README.md`.

## Step 8: Update SSH Config

Update your local SSH configuration file (`.ssh/config`) to use the new deployment user:

```bash
# Edit .ssh/config
```

Change the `User` line to:

```
Host openhab
    HostName 192.168.86.45
    User openhab-deploy
    Port 22
    IdentityFile .ssh/openhab_key
```

## Step 9: Test the Setup

Test SSH connection to the server:

```bash
ssh -F .ssh/config openhab
```

You should be able to connect without a password prompt.

Test file deployment permissions:

```bash
# Test config directory permissions
ssh -F .ssh/config openhab "touch /etc/openhab/items/test.txt && rm /etc/openhab/items/test.txt"

# Test jsondb directory permissions (for UI components)
ssh -F .ssh/config openhab "touch /var/lib/openhab/jsondb/test.txt && rm /var/lib/openhab/jsondb/test.txt"
```

If both commands succeed, file permissions are correct.

Test service restart permission:

```bash
ssh -F .ssh/config openhab "sudo systemctl restart openhab"

# If you created the weather-station service in Step 7:
ssh -F .ssh/config openhab "sudo systemctl restart weather-station"
```

These should execute without prompting for a password (assuming the corresponding services exist).

## Step 10: Verify Deployment Script

Run a dry-run of the deployment script to verify everything is configured correctly:

```bash
cd server
python deploy_openhab.py --dry-run
```

Then run an actual deployment:

```bash
python deploy_openhab.py
```

**Important Deployment Notes:**

1. **OpenHAB Initialization Time**: OpenHAB takes 30-60 seconds to fully initialize after a restart. The deployment script now properly waits for:
   - Systemd to report the service as "active" (up to 30 seconds)
   - OpenHAB REST API to respond (up to 60 seconds)

   This ensures OpenHAB is fully ready before considering the deployment successful.

2. **Avoid Rapid Successive Deployments**:
   - Do not deploy multiple times in quick succession (within 5-10 minutes)
   - Wait for the previous deployment to complete fully before starting another
   - Rapid restarts can cause bundle lock contention and `BundleException` timeouts
   - If you need to deploy multiple changes, batch them into a single deployment

3. **Monitor Deployment Output**:
   - Watch for "OpenHAB service restarted and fully initialized" message
   - If you see warnings about initialization taking longer than expected, wait before deploying again
   - Check OpenHAB logs if deployments fail: `sudo journalctl -u openhab -f`

4. **Deployment Best Practices**:
   - Use `--dry-run` first to preview changes
   - Deploy during low-traffic periods when possible
   - Test configuration changes in a staging environment first
   - Keep deployments focused - avoid deploying everything at once if possible

## Troubleshooting

### Permission Denied Errors

If you get "Permission denied" when trying to write files:

1. **If the error is for `services/rrd4j.cfg`** (or similar): the directory may already be group-writable (`openhab:openhab`, 775), but the _file_ may already exist and be root-owned, so the deploy user cannot overwrite it. Fix by either:
   - **Option A:** Delete the file and re-run the deployment (the deploy will create it with correct ownership), or
   - **Option B:** Change ownership so the deploy user can overwrite it:

   ```bash
   sudo chown openhab:openhab /etc/openhab/services/rrd4j.cfg
   sudo chown openhab:openhab /etc/openhab/services
   sudo chmod g+w /etc/openhab/services
   ```

   Then re-run the deployment.

2. Verify the user is in the `openhab` group:

   ```bash
   groups openhab-deploy
   ```

3. Check directory permissions for config directories:

   ```bash
   ls -ld /etc/openhab/items
   ```

   Should show group write permission (`drwxrwxr-x` or similar).

4. Verify group ownership for config directories:

   ```bash
   ls -ld /etc/openhab/items | grep openhab
   ```

5. Check jsondb directory permissions (for UI components):

   ```bash
   ls -ld /var/lib/openhab/jsondb
   ```

   Should show group write permission (`drwxrwxr-x` or similar).

6. Verify group ownership for jsondb directory:

   ```bash
   ls -ld /var/lib/openhab/jsondb | grep openhab
   ```

7. If jsondb directory permissions are incorrect, fix them:
   ```bash
   sudo chgrp openhab /var/lib/openhab/jsondb
   sudo chmod g+w /var/lib/openhab/jsondb
   ```

### SSH Connection Issues

If SSH connection fails:

1. Check that the public key is in `~openhab-deploy/.ssh/authorized_keys`:

   ```bash
   sudo cat /home/openhab-deploy/.ssh/authorized_keys
   ```

2. Verify file permissions:

   ```bash
   sudo ls -la /home/openhab-deploy/.ssh/
   ```

   Should show `700` for `.ssh` and `600` for `authorized_keys`.

3. Check SSH server logs:
   ```bash
   sudo tail -f /var/log/auth.log
   ```

### Sudo Permission Issues

If service restart fails:

1. Verify sudoers entry:

   ```bash
   sudo visudo -c
   ```

2. Test sudo access:

   ```bash
   ssh -F .ssh/config openhab "sudo -n systemctl restart openhab"
   ssh -F .ssh/config openhab "sudo -n systemctl is-active openhab"
   ssh -F .ssh/config openhab "sudo -n systemctl status openhab"

   # If you created the weather-station service in Step 7:
   ssh -F .ssh/config openhab "sudo -n systemctl restart weather-station"
   ```

   The `-n` flag tests passwordless sudo.

3. **Important**: If you see "command not allowed" errors for `is-active` or `status`, the sudoers file needs to be updated with the additional permissions shown in Step 6. This is critical for proper restart verification.

### OpenHAB Restart Issues

If OpenHAB fails to restart or experiences `BundleException` timeouts:

1. **Check if OpenHAB is still initializing**:

   ```bash
   sudo systemctl status openhab
   ```

   If status shows "activating", wait for it to complete before attempting another restart.

2. **Check for rapid successive restarts**:

   ```bash
   sudo journalctl -u openhab --since "1 hour ago" | grep -E "(Started|Stopped)"
   ```

   If you see multiple restarts within a short time period, wait at least 5-10 minutes between deployments.

3. **Verify OpenHAB is fully ready**:

   ```bash
   curl -s http://localhost:8080/rest/ | head -5
   ```

   If this doesn't return a response, OpenHAB is still initializing.

4. **Check for bundle lock errors**:

   ```bash
   sudo journalctl -u openhab --since "1 hour ago" | grep -i "bundleexception\|timeout\|lock"
   ```

   If you see these errors, OpenHAB was restarted too quickly. Wait longer between deployments.

5. **See `server/DEPLOYMENT_RESTART_FIX.md`** for detailed information about restart issues and solutions.

### Weather Station Service Not Found

If the deployment script fails with an error like "Unit weather-station.service not found" or the service is not active:

1. The systemd service unit must be created manually as root (see Step 7 above).

2. Verify the service exists:

   ```bash
   sudo systemctl status weather-station
   ```

3. If the service doesn't exist, create it using the instructions in Step 7, then run:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable weather-station
   sudo systemctl start weather-station
   ```

4. After the service is created, subsequent runs of `deploy_openhab.py` will deploy updated files and restart the service automatically.

## Security Notes

- The deployment user should only have the minimum permissions necessary
- The private SSH key (`.ssh/openhab_key`) should never be committed to version control
- Consider using a passphrase-protected SSH key for additional security
- Regularly rotate SSH keys as part of your security practices
- The sudoers rules are limited to:
  - Restarting the OpenHAB and weather-station services
  - Checking service status (is-active, status)
  - These commands do not allow arbitrary system commands or file access

## Cleanup (If Needed)

If you need to remove the deployment user:

```bash
# Remove sudoers entry
sudo rm /etc/sudoers.d/openhab-deploy

# Remove user and home directory
sudo userdel -r openhab-deploy

# Remove from group (if needed)
sudo gpasswd -d openhab-deploy openhab
```
