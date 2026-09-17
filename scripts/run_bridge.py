#!/usr/bin/env python3
"""Run from any directory. Requires requirements.txt and ffmpeg on PATH."""
import argparse
import os
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.chdir(root)
p = argparse.ArgumentParser()
p.add_argument('--host', default='0.0.0.0')
p.add_argument('--port', type=int, default=8787)
p.add_argument('--data', default=str(root / '.local'))
a = p.parse_args()
os.environ['SYNCPLAY_ROKU_DATA'] = a.data
import uvicorn
uvicorn.run('bridge.app:app', host=a.host, port=a.port, access_log=False, timeout_graceful_shutdown=5)
