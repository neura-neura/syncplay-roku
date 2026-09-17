import importlib
import threading
import pytest
from fastapi.testclient import TestClient
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from bridge.config import Source
from bridge.storage import Remote

@pytest.fixture
def ftp(tmp_path):
    data = bytes(range(256)) * 100
    (tmp_path / 'clip with spaces.mkv').write_bytes(data)
    (tmp_path / 'captions.ass').write_text('[Script Info]')
    (tmp_path / 'folder').mkdir()
    auth = DummyAuthorizer()
    auth.add_user('test', 'secret', str(tmp_path), perm='elr')
    class Handler(FTPHandler):
        authorizer = auth
    server = FTPServer(('127.0.0.1', 0), Handler)
    stopping = threading.Event()
    def serve():
        while not stopping.is_set():
            server.serve_forever(timeout=.02, blocking=False)
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield Source(protocol='ftp', host='127.0.0.1', port=server.socket.getsockname()[1], username='test', password='secret'), data
    stopping.set()
    thread.join(2)
    server.close_all()

def test_ftp_browse_and_seek(ftp):
    config, data = ftp
    remote = Remote(config)
    entries = remote.browse('/')
    assert entries[0]['name'] == 'folder'
    assert any(e['kind'] == 'subtitle' for e in entries)
    assert remote.size('/clip with spaces.mkv') == len(data)
    assert b''.join(remote.chunks('/clip with spaces.mkv', 501, 1000)) == data[501:1501]

def test_http_auth_ranges_and_redaction(tmp_path, monkeypatch, ftp):
    from bridge import config
    monkeypatch.setattr(config, 'DATA', tmp_path)
    from bridge import app
    from bridge.config import Store
    monkeypatch.setattr(app, 'store', Store(tmp_path))
    app.store.config.sources = [ftp[0]]
    app.store.config.server.password = 'hidden'
    client = TestClient(app.app)
    assert client.get('/api/config').status_code == 401
    headers = {'X-Access-Token': app.store.config.token}
    assert client.get('/api/config', headers=headers).json()['server']['password'] == ''
    params = {'path': '/clip with spaces.mkv'}
    r = client.get('/raw/0', params=params, headers={**headers, 'Range': 'bytes=100-199'})
    assert r.status_code == 206 and r.content == ftp[1][100:200]
    assert r.headers['content-range'] == f'bytes 100-199/{len(ftp[1])}'
    r = client.get('/raw/0', params=params, headers={**headers, 'Range': 'bytes=-50'})
    assert r.content == ftp[1][-50:]
    assert client.head('/raw/0', params=params, headers=headers).content == b''
    for value in ['bytes=9999999-', 'bytes=1-2,3-4', 'bytes=-0', 'bad']:
        assert client.get('/raw/0', params=params, headers={**headers, 'Range': value}).status_code == 416
