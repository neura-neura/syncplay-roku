#!/usr/bin/env python3
"""Build a generic channel, or --paired using the private local bridge config."""
import argparse
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--paired', action='store_true')
p.add_argument('--migrate-from', help='Replace only this previous URL in the Roku registry')
p.add_argument('--config', type=Path, default=root / '.local/config.json')
args = p.parse_args()
out = root / 'dist'
out.mkdir(exist_ok=True)
name = out / ('noir-roku-paired.zip' if args.paired else 'noir-roku.zip')
with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED) as archive:
    for f in sorted((root / 'roku').rglob('*')):
        if f.is_file() and f.relative_to(root / 'roku').as_posix() != 'config.json':
            archive.write(f, f.relative_to(root / 'roku'))
    if not args.paired:
        archive.writestr("config.json", json.dumps({"url": "", "token": ""}))
    if args.paired:
        c = json.loads(args.config.read_text())
        paired = {'url': c['public_url'], 'token': c['token']}
        if args.migrate_from:
            paired['migrateFrom'] = args.migrate_from
        archive.writestr('config.json', json.dumps(paired))
if args.paired:
    name.chmod(0o600)
print(name)
