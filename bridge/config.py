"""Persistent configuration. Secrets stay outside the channel and source control."""
import json
import os
import secrets
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlsplit

DATA = Path(os.environ.get('SYNCPLAY_ROKU_DATA', '.local')).resolve()

class Server(BaseModel):
    host: str = ''
    port: int = Field(default=8999, ge=1, le=65535)
    username: str = 'Roku'
    password: str = ''
    room: str = 'default'
    tls: bool = False

class Source(BaseModel):
    name: str = 'Media library'
    protocol: Literal['smb', 'ftp', 'ftps'] = 'smb'
    host: str = ''
    port: int = Field(default=445, ge=1, le=65535)
    share: str = ''
    username: str = ''
    password: str = ''
    root: str = '/'

class SubtitleStyle(BaseModel):
    size: int = Field(default=38, ge=8, le=200)
    bold: bool = False  # Compatibility with earlier paired channels.
    color: str = Field(default='#ffffff', pattern=r'^#[0-9a-fA-F]{6}$')
    opacity: int = Field(default=23, ge=0, le=100)
    background: str = Field(default='#000000', pattern=r'^#[0-9a-fA-F]{6}$')
    bottom: float = Field(default=4, ge=0, le=100, allow_inf_nan=False)
    weight: int = Field(default=500, ge=100, le=900)
    font_family: str = Field(default='GothamPro', max_length=120)
    css_id: str = Field(default='', pattern=r'^[a-f0-9]{0,16}$')
    custom_width: bool = False
    max_width: float = Field(default=78, ge=10, le=100, allow_inf_nan=False)
    padding_x: int = Field(default=12, ge=0, le=80)
    padding_y: int = Field(default=8, ge=0, le=80)
    radius: int = Field(default=8, ge=0, le=80)
    line_height: float = Field(default=1.18, ge=.5, le=3, allow_inf_nan=False)
    letter_spacing: float = Field(default=.2, ge=-5, le=10, allow_inf_nan=False)
    shadow: bool = True
    preset_version: int = 2

class Config(BaseModel):
    server: Server = Field(default_factory=Server)
    sources: list[Source] = Field(default_factory=lambda: [Source()])
    public_url: str = 'http://127.0.0.1:8787'
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(24))
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)
    subtitle_mode: Literal['text', 'burn'] = 'text'
    video_mode: Literal['auto', 'direct', 'transcode'] = 'auto'
    audio_track: int = Field(default=0, ge=0, le=32)
    subtitle_offset: float = Field(default=0, ge=-3600, le=3600, allow_inf_nan=False)
    follow_playlist: bool = True
    autoplay: bool = False
    autoplay_delay: int = Field(default=3, ge=0, le=30)
    last_video: dict | None = None
    last_subtitle: dict | None = None

    @field_validator('public_url')
    @classmethod
    def valid_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('Usa una URL del puente como http://bridge-host:8787')
        return value.rstrip('/')

class Store:
    def __init__(self, directory=DATA):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / 'config.json'
        self.config = Config.model_validate_json(self.path.read_text()) if self.path.exists() else Config()
        self.save()

    def save(self):
        temp = self.path.with_suffix('.tmp')
        # Create with restrictive permissions from the beginning, including first run.
        fd = os.open(temp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(self.config.model_dump_json(indent=2))
        os.replace(temp, self.path)
        os.chmod(self.path, 0o600)
