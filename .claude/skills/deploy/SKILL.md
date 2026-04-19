---
name: deploy
description: Deploy weather station server code and OpenHAB config to the Raspberry Pi. Use this skill when the user asks to deploy, push changes to the server, update the receiver, or run deploy_openhab.py. Handles venv activation and running the deploy script correctly.
---

# Deploy Weather Station Skill

## Virtual Environment

The venv is a Windows Python venv at `venv/Scripts/`. In WSL, invoke it directly via the `.exe`:

```bash
/mnt/f/Projects/weather_station/venv/Scripts/python.exe server/deploy_openhab.py
```

Do **not** use `source venv/Scripts/activate` — it sets `PATH` to a Windows pyenv shim that fails in WSL. Call `python.exe` directly every time.

**Do not run `pip install` or modify dependencies unless the user explicitly asks.** The venv is already set up.

## Running the Deploy Script

Always run from the project root:

```bash
cd /mnt/f/Projects/weather_station
/mnt/f/Projects/weather_station/venv/Scripts/python.exe server/deploy_openhab.py
```

## Common Deploy Commands

| Task | Command |
|------|---------|
| Full deploy (OpenHAB config + receiver) | `python.exe server/deploy_openhab.py` |
| OpenHAB config only | `python.exe server/deploy_openhab.py --skip-receiver` |
| Receiver only | `python.exe server/deploy_openhab.py --skip-openhab` |
| Preview without deploying | `python.exe server/deploy_openhab.py --dry-run` |
| Deploy without restarting services | `python.exe server/deploy_openhab.py --no-restart` |
| Include config.json (careful — overwrites remote) | `python.exe server/deploy_openhab.py --receiver_config` |

Where `python.exe` = `/mnt/f/Projects/weather_station/venv/Scripts/python.exe`. SSH host alias for all operations: `server-deploy` (defined in `.ssh/config`).

## Post-Deploy Verification

```bash
ssh -F /mnt/f/Projects/weather_station/.ssh/config server-deploy \
  "sudo systemctl is-active openhab weather-station"
```

Expected: `active` on both lines.

## Notes

- SSH key: `.ssh/deploy_key` — never commit it
- Remote receiver venv lives at `~/weather_station/server/src/.venv` on the Pi; the deploy script manages it automatically
- See `server/DEPLOYMENT.md` for full option reference and troubleshooting
