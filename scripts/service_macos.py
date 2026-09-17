#!/usr/bin/env python3
"""Install/remove the bridge as a per-user macOS LaunchAgent."""
import argparse
import os
import plistlib
import subprocess
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('action', choices=['install','remove','status'])
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
label='local.noir.syncplay-roku'
plist=Path.home()/'Library/LaunchAgents'/f'{label}.plist'
domain=f'gui/{os.getuid()}'
if a.action=='status':
    raise SystemExit(subprocess.call(['launchctl','print',f'{domain}/{label}']))
if a.action=='remove':
    subprocess.run(['launchctl','bootout',f'{domain}/{label}'],check=False)
    plist.unlink(missing_ok=True)
else:
    (root/'.local').mkdir(exist_ok=True)
    plist.parent.mkdir(parents=True,exist_ok=True)
    config={'Label':label,'ProgramArguments':[str(root/'.venv/bin/python'),str(root/'scripts/run_bridge.py')],
            'WorkingDirectory':str(root),'RunAtLoad':True,'KeepAlive':True,
            'EnvironmentVariables':{'PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'},
            'StandardOutPath':str(root/'.local/bridge.log'),'StandardErrorPath':str(root/'.local/bridge-error.log'),
            'ThrottleInterval':5}
    plist.write_bytes(plistlib.dumps(config))
    subprocess.run(['launchctl','bootout',f'{domain}/{label}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True)
    print('Puente instalado:',plist)
