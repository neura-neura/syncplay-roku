#!/usr/bin/env python3
import argparse
import getpass
import os
from pathlib import Path
import requests
from requests.auth import HTTPDigestAuth
p = argparse.ArgumentParser(description='Install the channel in the Roku developer slot')
p.add_argument('host')
p.add_argument('archive', type=Path)
p.add_argument('--username', default='rokudev')
a = p.parse_args()
password = os.environ.get('ROKU_PASSWORD') or getpass.getpass('Roku developer password: ')
# Prime Digest auth before posting; Roku can close a multipart auth retry.
session = requests.Session()
session.auth = HTTPDigestAuth(a.username, password)
session.get('http://' + a.host + '/plugin_install', timeout=15).raise_for_status()
with a.archive.open('rb') as f:
    r = session.post('http://' + a.host + '/plugin_install',
                     data={'mysubmit': 'Install'}, files={'archive': (a.archive.name, f, 'application/zip')}, timeout=120)
r.raise_for_status()
import re
messages = re.findall(r'Install (?:Success|Failure)\.|Compilation Failed', r.text, re.I)
print('\n'.join(messages) if messages else 'Unrecognized installer response')
if not any('Install Success' in message for message in messages):
    raise SystemExit(1)
