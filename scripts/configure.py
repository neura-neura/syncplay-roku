#!/usr/bin/env python3
import getpass
import socket
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge.config import Store
s=Store(Path(__file__).resolve().parents[1]/'.local')
def ask(label,value):
    return input(f'{label} [{value}]: ').strip() or value
c=s.config
c.public_url=ask('Bridge URL reachable from Roku (http://HOST:8787)',c.public_url).rstrip('/')
c.server.host=ask('Syncplay server host',c.server.host)
c.server.port=int(ask('Port',str(c.server.port)))
c.server.username=ask('Username',c.server.username)
c.server.room=ask('Room',c.server.room)
c.server.password=getpass.getpass('Syncplay password (blank keeps existing): ') or c.server.password
if c.sources:
    r=c.sources[0]
    r.name=ask('Library display name',r.name)
    r.protocol=ask('Protocol smb/ftp/ftps',r.protocol)
    r.host=ask('File server host',r.host)
    r.port=int(ask('File server port',str(445 if r.protocol=='smb' else 21)))
    r.share=ask('SMB share name',r.share)
    r.username=ask('File server username',r.username)
    r.password=getpass.getpass('File server password (blank keeps existing): ') or r.password
    r.root=ask('Root folder (relative to share or FTP root)',r.root)
# Validate all assignments before saving.
from bridge.config import Config
s.config=Config.model_validate(c.model_dump())
s.save()
print('Configuration saved. Start scripts/run_bridge.py and open scripts/open_panel.py.')
