# AI-assisted installation prompt

Copy the entire prompt below into Codex or another terminal-capable coding agent. This is an alternative to the classic README instructions. Keep credentials in private inputs, not GitHub issues.

---

Install Noir Syncplay for Roku from https://github.com/neura-neura/syncplay-roku through to a working, verified setup. Read README.md and docs/SERVER.md first. Preserve existing settings/services; never assume example addresses are real.

Ask me together for these concrete details, skipping only information already explicitly supplied:

1. Roku IP/hostname, developer username (usually rokudev), developer password and whether developer mode is enabled. Explain that sideloading replaces its one developer channel. Guide the on-TV setup if necessary.
2. Bridge destination: this computer or always-on server/NAS; OS; Docker or native Python; SSH host/port/user and key/password if remote; installation directory; LAN address reachable from Roku; listening port (default 8787). Resolve ambiguous interfaces.
3. Syncplay host, port, username, room, optional password and validated TLS requirement. Use the existing server; do not replace it unless separately requested.
4. Each library: name, SMB/FTP/FTPS, host, port, share, account/password and root relative to share/server. Ask for one test video and optional subtitle path. Explain Windows drive paths versus share-relative paths.
5. Automatic startup preference, existing data to preserve, and permission for brief playback/seek testing in the room.

Then execute the work:

- Inspect the environment and clone the repo. Install necessary dependencies: Docker if selected, otherwise Python 3.11+ in a venv and FFmpeg/FFprobe with libass. Ask only for missing information/actions you cannot perform.
- Write credentials only into ignored private configuration. Never print passwords/tokens, hardcode them in source or commit them. Generate one strong permanent bridge token and preserve it on upgrades. Validate through bridge.config.Config. Map Windows paths correctly.
- Set bridge URL, LAN binding and firewall narrowly for my network. Do not expose it to the Internet or change router forwarding. Preserve unrelated containers and Syncplay. Deploy on the selected remote host and configure restart; the installation computer should not need to stay on afterward.
- Start and verify /health, authenticated configuration, Syncplay connection and library listing. Verify persistence by controlled restart when safe. Do not print token-bearing media URLs.
- Build using scripts/package.py --paired --config PRIVATE_CONFIG_PATH. Run npm ci and npm run check when available. Install using scripts/deploy.py or Roku's developer page. Never publish this ZIP. If Roku remembers an old URL, migrate only it with --migrate-from or update the TV setting; do not blindly reset settings.
- Demonstrate Configuración → Vincular navegador on Roku and a fresh browser loading stored settings without typing the permanent token.
- If authorized, test the video/subtitles, remote controls and synchronization. Prefer direct/text mode when supported. Explain before a large full-file transcode. Report hardware/network blockers and actual evidence, never assumed success.
- Write a private local INSTALLATION.md with actual addresses, directories, service commands, backup/restore/update steps and results, but no passwords. Give me the panel URL, private paired ZIP path and any remaining steps. Complete the authorized installation rather than merely proposing commands.

Do not create repositories/releases, upload secrets, send messages, purchase services or modify unrelated infrastructure. Do not bypass approvals or claim tests you did not run.

---

Developer-mode activation and credentials may require user input. The agent cannot guess passwords or automatically cross isolated networks. The generic ZIP and classic instructions work without AI.
