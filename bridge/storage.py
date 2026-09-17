"""Seekable SMB and streaming FTP sources; no credentials appear in media URLs."""
import ftplib
import posixpath
import ssl
from contextlib import contextmanager
from pathlib import PurePosixPath
import smbclient
from .config import Source

VIDEO = {'.mkv', '.mp4', '.m4v', '.mov', '.webm', '.avi', '.ts', '.m2ts'}
SUBTITLE = {'.ass', '.ssa', '.srt', '.vtt'}

def clean_path(path):
    path = path.replace('\\', '/')
    if '\x00' in path or any(x == '..' for x in path.split('/')):
        raise ValueError('Ruta inválida')
    return '/' + str(PurePosixPath('/' + path.lstrip('/'))).lstrip('/')

class Remote:
    def __init__(self, source: Source):
        self.source = source

    def path(self, path):
        p = clean_path(self.source.root).rstrip('/') + clean_path(path)
        if self.source.protocol == 'smb':
            return '\\\\' + self.source.host + '\\' + self.source.share.strip('/\\') + p.replace('/', '\\')
        return p

    def smb(self):
        s = self.source
        smbclient.register_session(s.host, username=s.username, password=s.password, port=s.port, connection_timeout=10)

    @contextmanager
    def ftp(self):
        s = self.source
        f = ftplib.FTP_TLS(context=ssl.create_default_context()) if s.protocol == 'ftps' else ftplib.FTP()
        try:
            f.connect(s.host, s.port, timeout=20)
            f.login(s.username, s.password)
            if s.protocol == 'ftps':
                f.prot_p()
            f.voidcmd('TYPE I')
            yield f
        finally:
            f.close()

    def browse(self, path='/'):
        rows = []
        if self.source.protocol == 'smb':
            self.smb()
            with smbclient.scandir(self.path(path), port=self.source.port) as entries:
                for e in entries:
                    rows.append((e.name, e.is_dir(), e.smb_info.end_of_file))
        else:
            with self.ftp() as f:
                for name, facts in f.mlsd(self.path(path)):
                    if facts.get('type') not in ('cdir', 'pdir'):
                        rows.append((name, facts.get('type') == 'dir', int(facts.get('size', 0))))
        result = []
        for name, directory, size in rows:
            ext = PurePosixPath(name).suffix.lower()
            if directory or ext in VIDEO | SUBTITLE:
                result.append(dict(name=name, path=clean_path(posixpath.join(path, name)), directory=directory,
                                   size=size, kind='folder' if directory else 'subtitle' if ext in SUBTITLE else 'video'))
        return sorted(result, key=lambda x: (not x['directory'], x['name'].casefold()))

    def size(self, path):
        if self.source.protocol == 'smb':
            self.smb()
            with smbclient.open_file(self.path(path), mode='rb', share_access='r', port=self.source.port) as f:
                return f.seek(0, 2)
        with self.ftp() as f:
            return f.size(self.path(path))

    def identity(self, path):
        """Cache fingerprint including remote modification time when available."""
        if self.source.protocol == 'smb':
            self.smb()
            with smbclient.scandir(self.path(posixpath.dirname(path)), port=self.source.port) as entries:
                for entry in entries:
                    if entry.name == posixpath.basename(path):
                        return [entry.smb_info.end_of_file, str(entry.smb_info.last_write_time)]
            raise FileNotFoundError(path)
        with self.ftp() as f:
            try:
                modified = f.sendcmd('MDTM ' + self.path(path))
            except ftplib.error_perm:
                modified = ''
            return [f.size(self.path(path)), modified]

    def chunks(self, path, start=0, length=None):
        remaining = length
        if self.source.protocol == 'smb':
            self.smb()
            with smbclient.open_file(self.path(path), mode='rb', share_access='r', port=self.source.port) as f:
                f.seek(start)
                while remaining is None or remaining > 0:
                    b = f.read(min(262144, remaining) if remaining is not None else 262144)
                    if not b:
                        break
                    yield b
                    if remaining is not None:
                        remaining -= len(b)
        else:
            with self.ftp() as f:
                with f.transfercmd('RETR ' + self.path(path), rest=start if start else None) as conn:
                    while remaining is None or remaining > 0:
                        b = conn.recv(min(262144, remaining) if remaining is not None else 262144)
                        if not b:
                            break
                        yield b
                        if remaining is not None:
                            remaining -= len(b)

    def download(self, path, destination, limit=None):
        size = self.size(path)
        if limit and size > limit:
            raise ValueError('El archivo de subtítulos es demasiado grande')
        with open(destination, 'wb') as f:
            for chunk in self.chunks(path):
                f.write(chunk)
        return size
