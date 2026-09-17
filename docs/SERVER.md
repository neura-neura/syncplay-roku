# Server operations

Use Docker Compose as described in README. Set BRIDGE_BIND_IP in .env to the host LAN address. The persistent host .local directory mounts at /data. Preserve the existing Syncplay server.

Commands: docker compose ps; docker compose logs --tail 100; docker compose restart; docker compose stop; docker compose start.

Upgrade with git pull --ff-only and docker compose up -d --build. Back up .local/config.json and .local/fonts privately before upgrading. Stop briefly for a consistent backup. Media cache is optional. Restore into .local and retain restrictive permissions.

For native operation use python scripts/run_bridge.py --data PATH --port 8787. On macOS scripts/service_macos.py supports install, status and remove. On Linux use a supervisor or Docker; on Windows use Docker or Task Scheduler with the venv Python. The service account needs network access and FFmpeg/FFprobe on PATH.

## Connection recovery

The permanent token lives in config.json and does not expire. It is different from all service passwords. Pair browsers using the code shown by Roku. To rotate the token: stop bridge, replace it with a fresh random value, restart, update Roku, re-pair browsers and reopen media.

When moving hosts update public_url and Roku's URL. scripts/package.py --paired --migrate-from OLD_URL migrates only that matching address. Reinstalling alone does not erase Roku's registry settings.

## Troubleshooting

- Empty/new browser: pair it. Saved passwords intentionally display as blank.
- Connection: test /health from Roku's network, then check firewall, port binding, URL and token.
- SMB: separate host and share, use share-relative paths, check account permissions.
- Unsupported media: automatic/transcode modes prepare full files and require time/disk.
- Subtitle appearance: use text mode; burned-in pixels cannot be restyled. Reopen after offset/mode changes.
- macOS service network failure: grant Local Network access to the actual launcher/Python.
- Roku installer failure: try the developer web page; some firmware closes Digest multipart retries.

Caption PNG cleanup runs at startup/hourly: 7 days unused, 256 MiB target, 10-minute active grace. Other cached media, fonts and settings remain intact.

Private paired ZIPs and settings archives are credentials. Keep them in private storage/releases, never in the public repository. Do not change the personal repository to public.
