#!/usr/bin/env python3
"""Start/stop a detached bridge for the current login session."""
import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=root/'.local'
data.mkdir(exist_ok=True)
pidfile=data/'bridge.pid'
p=argparse.ArgumentParser();p.add_argument('action',choices=['start','stop']);args=p.parse_args()
if pidfile.exists():
    pid=int(pidfile.read_text())
    try:
        os.kill(pid,0)
    except ProcessLookupError:
        pidfile.unlink()
    else:
        if args.action=='stop':
            os.kill(pid,signal.SIGTERM);pidfile.unlink();print('Puente detenido');raise SystemExit()
        print('Puente ya iniciado:',pid);raise SystemExit()
if args.action=='start':
    with (data/'bridge.log').open('ab') as out:
        child=subprocess.Popen([sys.executable,str(root/'scripts/run_bridge.py')],cwd=root,stdin=subprocess.DEVNULL,stdout=out,stderr=out,start_new_session=True)
    pidfile.write_text(str(child.pid))
    print('Puente iniciado:',child.pid)
