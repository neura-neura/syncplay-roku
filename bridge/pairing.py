"""Single-use browser pairing, initiated by an authenticated Roku."""
import hmac
import secrets
import time

class Pairing:
    def __init__(self):
        self.code = None
        self.expires = 0
        self.attempts = 0

    def create(self):
        self.code = f'{secrets.randbelow(1000000):06d}'
        self.expires = time.monotonic() + 300
        self.attempts = 5
        return {'code': self.code, 'expiresIn': 300}

    def redeem(self, code):
        if not self.code or time.monotonic() >= self.expires or self.attempts <= 0:
            return False
        self.attempts -= 1
        if not hmac.compare_digest(code, self.code):
            return False
        self.code = None
        return True
