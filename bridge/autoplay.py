"""Readiness countdown, armed only by an explicit local ready action."""
import time

class Autoplay:
    def __init__(self):
        self.armed = False
        self.deadline = None
        self.remaining = None

    def arm(self, ready):
        self.armed = bool(ready)
        self.deadline = None
        self.remaining = None

    def tick(self, enabled, seconds, snapshot, media_ready, now=None):
        now = time.monotonic() if now is None else now
        users = snapshot['users'].get(snapshot['room'], {})
        eligible = (enabled and self.armed and media_ready and snapshot['connected']
                    and snapshot['target']['paused'] and snapshot['ready'] and users
                    and all(u.get('isReady') is True and u.get('file') for u in users.values()))
        if not eligible:
            self.deadline = self.remaining = None
            return False
        if self.deadline is None:
            self.deadline = now + seconds
        self.remaining = max(0, int(self.deadline - now + .99))
        if now >= self.deadline:
            self.arm(False)
            return True
        return False
