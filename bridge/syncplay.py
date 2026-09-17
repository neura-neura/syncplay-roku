"""Syncplay JSON-lines transport, compatible with syncplay-noir's wire protocol.

The server carries control messages only. Roku playback telemetry is independent
from user actions, so buffering and remote commands cannot bounce back as seeks.
"""
import asyncio
import hashlib
import json
import time
import ssl
from collections import deque

class Syncplay:
    def __init__(self, store):
        self.store = store
        self.writer = None
        self.task = None
        self.connected = False
        self.error = ''
        self.username = ''
        self.users = {}
        self.chat = deque(maxlen=80)
        self.playlist = []
        self.playlist_index = 0
        self.ready = False
        self.file = None
        self.local = {'position': 0.0, 'paused': True}
        self.reported_at = 0.0
        self.global_state = {'position': 0.0, 'paused': True, 'doSeek': False}
        self.global_at = time.monotonic()
        self.client_ignore = 0
        self.server_ignore = 0
        self.rtt = 0.0
        self.revision = 0
        self.seek_revision = 0
        self.last_ping = {}
        self.confirm_until = 0.0

    async def start(self):
        await self.stop()
        self.task = asyncio.create_task(self.run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        if self.writer:
            self.writer.close()
        self.writer = None
        self.connected = False

    async def send(self, value):
        if self.writer and not self.writer.is_closing():
            self.writer.write((json.dumps(value, ensure_ascii=False) + '\r\n').encode())
            await self.writer.drain()

    async def run(self):
        backoff = 1
        while True:
            try:
                c = self.store.config.server
                reader, self.writer = await asyncio.wait_for(asyncio.open_connection(c.host, c.port), 10)
                self.client_ignore = self.server_ignore = 0
                if c.tls:
                    await self.send({'TLS': {'startTLS': 'send'}})
                    response = json.loads(await asyncio.wait_for(reader.readline(), 10))
                    if response.get('TLS', {}).get('startTLS') != 'true':
                        raise ValueError('El servidor no ofrece TLS')
                    await self.writer.start_tls(ssl.create_default_context(), server_hostname=c.host)
                await self.send({'Hello': {'username': c.username, 'room': {'name': c.room},
                    'password': hashlib.md5(c.password.encode()).hexdigest() if c.password else '',
                    'version': '1.2.255', 'realversion': '1.7.5',
                    'features': {'sharedPlaylists': True, 'chat': True, 'featureList': True,
                                 'readiness': True, 'managedRooms': True}}})
                while True:
                    line = await asyncio.wait_for(reader.readline(), 20)
                    if not line:
                        raise ConnectionError('Conexión cerrada')
                    await self.handle(json.loads(line))
                    backoff = 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.error = str(e)
            finally:
                self.connected = False
                if self.writer:
                    self.writer.close()
                self.writer = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def target(self):
        result = dict(self.global_state)
        if not result['paused']:
            result['position'] += time.monotonic() - self.global_at
        return result

    def telemetry(self, position, paused, active):
        self.local = {'position': max(0, position), 'paused': paused}
        self.reported_at = time.monotonic() if active else 0

    async def state(self, change=False, seek=False):
        state = {'ping': {'clientLatencyCalculation': time.time(), 'clientRtt': self.rtt}}
        if 'latencyCalculation' in self.last_ping:
            state['ping']['latencyCalculation'] = self.last_ping['latencyCalculation']
        if change or (self.reported_at and time.monotonic() - self.reported_at < 5):
            if not self.client_ignore or self.server_ignore or change:
                state['playstate'] = dict(self.local)
                if not change:
                    target = self.target()
                    state['playstate']['paused'] = target['paused']
                    if time.monotonic() < self.confirm_until:
                        state['playstate']['position'] = target['position']
                if seek:
                    state['playstate']['doSeek'] = True
        if change:
            self.client_ignore += 1
        ignore = {}
        if self.server_ignore:
            ignore['server'] = self.server_ignore
            self.server_ignore = 0
        if self.client_ignore:
            ignore['client'] = self.client_ignore
        if ignore:
            state['ignoringOnTheFly'] = ignore
        await self.send({'State': state})

    async def action(self, position, paused, seek=False):
        if not self.connected:
            raise ValueError('Syncplay no está conectado')
        self.telemetry(position, paused, True)
        self.global_state = {'position': position, 'paused': paused, 'doSeek': seek}
        self.global_at = time.monotonic()
        self.revision += 1
        self.confirm_until = time.monotonic() + 4
        if seek:
            self.seek_revision += 1
        await self.state(change=True, seek=seek)

    async def set_file(self, value):
        self.file = value
        await self.send({'Set': {'file': value}})
        await self.send({'List': None})

    async def handle(self, message):
        if 'Error' in message:
            raise ValueError(message['Error'].get('message', 'Error Syncplay'))
        if 'Hello' in message:
            self.connected = True
            self.error = ''
            self.username = message['Hello']['username']
            self.chat.append({'username': 'Syncplay', 'message': 'Conectado a ' + message['Hello']['room']['name']})
            await self.send({'List': None})
            await self.send({'Set': {'ready': {'isReady': self.ready, 'manuallyInitiated': False}}})
            if self.file:
                await self.set_file(self.file)
        if 'Chat' in message:
            self.chat.append(message['Chat'])
        if 'List' in message:
            self.users = message['List']
        if 'Set' in message:
            s = message['Set']
            if 'playlistChange' in s:
                self.playlist = s['playlistChange']['files']
            if 'playlistIndex' in s:
                self.playlist_index = s['playlistIndex']['index']
            if 'ready' in s:
                r = s['ready']
                if r.get('username') == self.username:
                    self.ready = bool(r['isReady'])
            if 'user' in s or 'ready' in s:
                await self.send({'List': None})
            if 'controllerAuth' in s:
                self.chat.append({'username': 'Syncplay', 'message': 'Control de sala: ' + str(s['controllerAuth'].get('success'))})
            if 'room' in s:
                self.store.config.server.room = s['room']['name']
                self.store.save()
        if 'State' in message:
            s = message['State']
            ignore = s.get('ignoringOnTheFly', {})
            if 'server' in ignore:
                self.server_ignore = ignore['server']
                self.client_ignore = 0
            elif ignore.get('client') == self.client_ignore:
                self.client_ignore = 0
            self.last_ping = s.get('ping', {})
            stamp = self.last_ping.get('clientLatencyCalculation')
            if stamp:
                self.rtt = min(10, max(0, time.time() - stamp))
            if 'playstate' in s and not self.client_ignore:
                p = s['playstate']
                paused = bool(p.get('paused', True))
                position = max(0, float(p.get('position', 0)))
                if not paused:
                    position += min(self.rtt / 2, 1)
                if p.get('doSeek') or paused != self.global_state['paused']:
                    self.confirm_until = time.monotonic() + 4
                self.global_state = dict(p, position=position, paused=paused)
                self.global_at = time.monotonic()
                self.revision += 1
                if p.get('doSeek'):
                    self.seek_revision += 1
            await self.state()

    def snapshot(self):
        return {'connected': self.connected, 'error': self.error, 'username': self.username,
                'room': self.store.config.server.room, 'target': self.target(),
                'revision': self.revision, 'seekRevision': self.seek_revision,
                'users': self.users, 'chat': list(self.chat), 'ready': self.ready,
                'playlist': self.playlist, 'playlistIndex': self.playlist_index,
                'player': dict(self.local, active=bool(self.reported_at and time.monotonic() - self.reported_at < 5))}
