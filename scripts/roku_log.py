#!/usr/bin/env python3
import socket
import sys
s=socket.create_connection((sys.argv[1],8085),5)
s.settimeout(60)
try:
 while True:
  b=s.recv(65536)
  if not b:break
  print(b.decode(errors='replace'),end='',flush=True)
except TimeoutError:
 pass
