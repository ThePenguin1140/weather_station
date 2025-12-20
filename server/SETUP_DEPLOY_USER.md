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
sudo mkdir -p /etc/openhab/{items,sitemaps,rules}
sudo chown -R openhab:openhab /etc/openhab
sudo chmod -R g+w /etc/openhab
```

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

Configure sudo to allow the deployment user to restart services without a password. Create a dedicated sudoers drop-in file:

```bash
sudo tee /etc/sudoers.d/openhab-deploy >/dev/null << 'EOF'
openhab-deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart openhab, /bin/systemctl restart weather-station
EOF
sudo chmod 440 /etc/sudoers.d/openhab-deploy
```

- **`restart openhab`**: Needed so the deployment script can restart OpenHAB after pushing new configuration files.
- **`restart weather-station`**: Allows the deployment user to restart the weather station receiver service (see the next step).

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
ssh -F .ssh/config openhab "touch /etc/openhab/items/test.txt && rm /etc/openhab/items/test.txt"
```

If this succeeds, file permissions are correct.

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

## Troubleshooting

### Permission Denied Errors

If you get "Permission denied" when trying to write files:

1. Verify the user is in the `openhab` group:
   ```bash
   groups openhab-deploy
   ```

2. Check directory permissions:
   ```bash
   ls -ld /etc/openhab/items
   ```
   Should show group write permission (`drwxrwxr-x` or similar).

3. Verify group ownership:
   ```bash
   ls -ld /etc/openhab/items | grep openhab
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

   # If you created the weather-station service in Step 7:
   ssh -F .ssh/config openhab "sudo -n systemctl restart weather-station"
   ```
   The `-n` flag tests passwordless sudo.

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
- The sudoers rule is limited to only restarting the OpenHAB and weather-station services, not other system commands

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



