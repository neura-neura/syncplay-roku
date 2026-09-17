import asyncio
import json
import time
import pytest
from fastapi import HTTPException
from bridge.config import Store
from bridge.storage import clean_path
from bridge.syncplay import Syncplay

@pytest.mark.parametrize('path', ['../secret', '/a/../b', 'a\\..\\b', '\x00'])
def test_remote_traversal_rejected(path):
    with pytest.raises(ValueError):
        clean_path(path)

def test_config_survives_restart_and_is_private(tmp_path):
    s = Store(tmp_path)
    s.config.server.password = 'private'
    s.config.sources[0].password = 'smb-secret'
    s.save()
    restored = Store(tmp_path)
    assert restored.config.server.password == 'private'
    assert restored.config.sources[0].password == 'smb-secret'
    assert restored.config.token == s.config.token
    assert s.path.stat().st_mode & 0o777 == 0o600

class Capture:
    def __init__(self):
        self.messages = []
    def write(self, data):
        assert data.endswith(b'\r\n')
        self.messages.append(json.loads(data))
    async def drain(self):
        pass
    def is_closing(self):
        return False

def client(tmp_path):
    c = Syncplay(Store(tmp_path))
    c.writer = Capture()
    c.connected = True
    return c

def test_remote_unpause_does_not_bounce_stale_paused_telemetry(tmp_path):
    async def scenario():
        c = client(tmp_path)
        c.telemetry(12, True, True)
        await c.handle({'State': {'playstate': {'position': 50, 'paused': False, 'doSeek': True},
                                  'ignoringOnTheFly': {'server': 4}, 'ping': {'latencyCalculation': 123}}})
        reply = c.writer.messages[-1]['State']
        assert reply['playstate']['paused'] is False
        assert reply['playstate']['position'] >= 50
        assert reply['ignoringOnTheFly']['server'] == 4
        assert reply['ping']['latencyCalculation'] == 123
        assert c.seek_revision == 1
    asyncio.run(scenario())

def test_local_seek_ignores_stale_state_until_ack(tmp_path):
    async def scenario():
        c = client(tmp_path)
        await c.action(100, False, True)
        assert c.writer.messages[-1]['State']['ignoringOnTheFly']['client'] == 1
        assert c.writer.messages[-1]['State']['playstate']['doSeek'] is True
        await c.handle({'State': {'playstate': {'position': 1, 'paused': True}}})
        assert c.target()['position'] >= 100
        assert 'playstate' not in c.writer.messages[-1]['State']
        await c.handle({'State': {'playstate': {'position': 101, 'paused': False}, 'ignoringOnTheFly': {'client': 1}}})
        assert c.client_ignore == 0
        assert c.target()['position'] >= 101
    asyncio.run(scenario())

def test_inactive_player_cannot_pause_room(tmp_path):
    async def scenario():
        c = client(tmp_path)
        c.telemetry(0, True, False)
        await c.handle({'State': {'playstate': {'position': 10, 'paused': False}}})
        assert 'playstate' not in c.writer.messages[-1]['State']
    asyncio.run(scenario())

def test_server_null_readiness_is_safe(tmp_path):
    async def scenario():
        c = client(tmp_path)
        c.username = 'Roku'
        await c.handle({'Set': {'ready': {'username': 'Roku', 'isReady': None}}})
        assert c.ready is False
    asyncio.run(scenario())

def test_protocol_socket_auth_and_reconnect(tmp_path):
    async def scenario():
        hello = asyncio.Queue()
        async def server(reader, writer):
            hello.put_nowait(json.loads(await reader.readline()))
            writer.write(b'{"Hello":{"username":"Roku","room":{"name":"movies"},"version":"1.7.5"}}\r\n')
            await writer.drain()
            await asyncio.sleep(.05)
            writer.close()
        listener = await asyncio.start_server(server, '127.0.0.1', 0)
        s = Store(tmp_path)
        s.config.server.host = '127.0.0.1'
        s.config.server.port = listener.sockets[0].getsockname()[1]
        s.config.server.password = '321'
        c = Syncplay(s)
        await c.start()
        first = await asyncio.wait_for(hello.get(), 2)
        assert first['Hello']['password'] == 'caf1a3dfb505ffed0d024130f58c5cfa'
        await asyncio.wait_for(hello.get(), 3)
        await c.stop()
        listener.close()
        await listener.wait_closed()
    asyncio.run(scenario())
