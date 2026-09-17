"""Retention for generated subtitle PNGs only; mtime records last use."""
import asyncio
import logging
import os
import re
import threading
import time

NAME = re.compile(r'^caption-[0-9a-f]{64}\.png$')
MAX_AGE = 7 * 24 * 3600
MAX_BYTES = 256 * 1024 * 1024
INTERVAL = 3600
GRACE = 600  # Keep recently served/preloaded images through concurrent requests.

class CaptionCache:
    def __init__(self, directory):
        self.directory = directory
        self.lock = threading.RLock()

    def touch(self, path):
        if not NAME.fullmatch(path.name): return
        with self.lock:
            if path.is_symlink(): return
            try: os.utime(path, None)
            except FileNotFoundError: pass

    def cleanup(self, now=None, max_age=MAX_AGE, max_bytes=MAX_BYTES):
        now = time.time() if now is None else now
        removed = freed = 0
        with self.lock:
            entries = []
            for path in self.directory.iterdir():
                if not NAME.fullmatch(path.name) or path.is_symlink() or not path.is_file(): continue
                try: stat = path.stat()
                except FileNotFoundError: continue
                entries.append((stat.st_mtime, path, stat.st_size))
            total = sum(size for _, _, size in entries)
            for used, path, size in sorted(entries):
                if now - used < GRACE: continue
                if now - used <= max_age and total <= max_bytes: continue
                try: path.unlink()
                except FileNotFoundError: continue
                total -= size
                freed += size
                removed += 1
        return {'removed': removed, 'freedBytes': freed, 'remainingBytes': total}

    async def maintain(self):
        while True:
            try:
                result = await asyncio.to_thread(self.cleanup)
                logging.getLogger(__name__).info('Subtitle image cache cleanup: %s', result)
            except OSError:
                logging.getLogger(__name__).exception('Subtitle image cache cleanup failed; retrying next hour')
            await asyncio.sleep(INTERVAL)
