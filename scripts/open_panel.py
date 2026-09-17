#!/usr/bin/env python3
import sys
import webbrowser
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge.config import Store
c=Store(Path(__file__).resolve().parents[1]/'.local').config
webbrowser.open(c.public_url + '/#' + c.token)
