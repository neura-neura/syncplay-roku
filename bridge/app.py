import asyncio
import hashlib
import json
import io
import tempfile
import os
import hmac
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from .config import Store, Config, SubtitleStyle
from .storage import Remote, clean_path
from .syncplay import Syncplay
from .media import Media
from .autoplay import Autoplay
from .caption_fonts import Fonts
from .caption_render import render, RENDER_VERSION
from .caption_cache import CaptionCache, NAME as CAPTION_NAME
from .pairing import Pairing
pairing = Pairing()

store = Store()
fonts = Fonts(store.directory)
caption_styles = {}
sync = Syncplay(store)
media = Media(store)
caption_cache = CaptionCache(media.directory)
open_lock = asyncio.Lock()
autoplay = Autoplay()

async def follow_playlist():
    """Resolve shared filenames beside the selected local copy, across sources."""
    previous = None
    while True:
        await asyncio.sleep(1)
        current = media.current
        if autoplay.tick(store.config.autoplay, store.config.autoplay_delay, sync.snapshot(),
                         bool(current and sync.snapshot()['player']['active'])):
            await sync.action(sync.target()['position'], False)
        if current:
            global last_announced
            if current['id'] != last_announced:
                await sync.set_file({'name': current['title'], 'duration': current['duration'], 'size': current['size']})
                last_announced = current['id']
        if not store.config.follow_playlist or not sync.connected:
            continue
        index = sync.playlist_index
        if index is None or index < 0 or index >= len(sync.playlist):
            continue
        name = sync.playlist[index]
        key = (tuple(sync.playlist), index)
        if key == previous:
            continue
        previous = key
        selected = store.config.last_video
        if not selected or (current and current['title'] == name):
            continue
        # A shared entry is a filename, never an arbitrary network URL to fetch.
        filename = name.replace('\\', '/').split('/')[-1]
        folder = str(Path(selected['path']).parent)
        for source_id in [selected['source']] + [i for i in range(len(store.config.sources)) if i != selected['source']]:
            try:
                entries = await asyncio.to_thread(source(source_id).browse, folder)
                match = next((e for e in entries if e['name'] == filename and e['kind'] == 'video'), None)
                if match:
                    subtitle = None
                    old_subtitle = store.config.last_subtitle
                    if old_subtitle:
                        sub_folder = str(Path(old_subtitle['path']).parent)
                        subs = await asyncio.to_thread(source(old_subtitle['source']).browse, sub_folder)
                        # Resolution tags may differ, as in the supplied 1080p/360p files.
                        stem = Path(filename).stem.split(' [')[0]
                        found = next((e for e in subs if e['kind'] == 'subtitle' and Path(e['name']).stem.split(' [')[0] == stem), None)
                        if found:
                            subtitle = {'source': old_subtitle['source'], 'path': found['path']}
                    async with open_lock:
                        await media.prepare({'source': source_id, 'path': match['path']}, subtitle)
                    break
            except (OSError, ValueError):
                continue
        else:
            sync.chat.append({'username': 'Roku', 'message': 'Selecciona la copia local de: ' + filename})

@asynccontextmanager
async def lifespan(app):
    await sync.start()
    if store.config.last_video:
        await media.prepare(store.config.last_video, store.config.last_subtitle)
    follower = asyncio.create_task(follow_playlist())
    cleaner = asyncio.create_task(caption_cache.maintain())
    try:
        yield
    finally:
        cleaner.cancel()
        try:
            await cleaner
        except asyncio.CancelledError:
            pass
    follower.cancel()
    try:
        await follower
    except asyncio.CancelledError:
        pass
    await media.close()
    await sync.stop()

app = FastAPI(title='Syncplay Noir · Roku', lifespan=lifespan)

@app.middleware('http')
async def authorize(request, call_next):
    if request.url.path not in ('/', '/health', '/api/pair/redeem'):
        supplied = request.headers.get('X-Access-Token', request.query_params.get('token', ''))
        if not hmac.compare_digest(supplied, store.config.token):
            return JSONResponse({'detail': 'Token de acceso incorrecto'}, status_code=401)
    try:
        return await call_next(request)
    except (OSError, ValueError) as e:
        return JSONResponse({'detail': str(e)}, status_code=400)

@app.get('/')
def index():
    return HTMLResponse(Path(__file__).with_name('index.html').read_text())

@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'syncplay-roku'}

class PairCode(BaseModel):
    code: str = Field(pattern=r'^\d{6}$')

@app.post('/api/pair/create')
async def create_pairing():
    return pairing.create()

@app.post('/api/pair/redeem')
async def redeem_pairing(body: PairCode):
    if not pairing.redeem(body.code):
        raise HTTPException(403, 'Código incorrecto, vencido o agotado. Genera otro desde Roku.')
    return JSONResponse({'token': store.config.token}, headers={'Cache-Control': 'no-store'})

@app.put('/api/subtitle-style')
def put_subtitle_style(style: SubtitleStyle):
    store.config.subtitle_style = style
    store.save()
    return style.model_dump()

@app.get('/api/config')
def get_config():
    c = store.config.model_dump()
    c.pop('token')
    c['server']['password'] = ''
    for s in c['sources']:
        s['password'] = ''
    return c

@app.put('/api/config')
async def put_config(config: Config):
    config.token = store.config.token
    if not config.server.password:
        config.server.password = store.config.server.password
    for s in config.sources:
        if not s.password:
            old = next((o for o in store.config.sources if (o.host, o.username, o.protocol) == (s.host, s.username, s.protocol)), None)
            if old:
                s.password = old.password
    store.config = config
    store.save()
    await sync.start()
    return {'ok': True}

def source(index):
    if index < 0 or index >= len(store.config.sources):
        raise HTTPException(404, 'Origen no encontrado')
    return Remote(store.config.sources[index])

@app.get('/api/browse')
def browse(source_id: int = 0, path: str = '/'):
    try:
        return {'path': clean_path(path), 'entries': source(source_id).browse(path)}
    except Exception as e:
        raise HTTPException(400, str(e)) from e

class Selection(BaseModel):
    source: int = Field(ge=0)
    path: str

class Open(BaseModel):
    video: Selection
    subtitle: Selection | None = None

@app.post('/api/open')
async def open_media(value: Open):
    source(value.video.source)
    clean_path(value.video.path)
    if value.subtitle:
        source(value.subtitle.source)
        clean_path(value.subtitle.path)
    async with open_lock:
        autoplay.arm(False)
        await media.prepare(value.video.model_dump(), value.subtitle.model_dump() if value.subtitle else None)
    return {'ok': True}

last_announced = None

@app.get('/api/state')
async def state():
    global last_announced
    current = media.current
    if current and current['id'] != last_announced:
        await sync.set_file({'name': current['title'], 'duration': current['duration'], 'size': current['size']})
        last_announced = current['id']
    snapshot = sync.snapshot()
    snapshot['countdown'] = autoplay.remaining
    style = store.config.subtitle_style
    revision = hashlib.sha256((RENDER_VERSION + style.model_dump_json()).encode()).hexdigest()[:16]
    caption_styles[revision] = style
    if len(caption_styles) > 32: caption_styles.pop(next(iter(caption_styles)))
    return {'sync': snapshot, 'media': media.snapshot(), 'subtitleStyle': style.model_dump(), 'captionRevision': revision}

class Telemetry(BaseModel):
    position: float = Field(default=0, ge=0, allow_inf_nan=False)
    paused: bool = True
    active: bool = True

@app.post('/api/telemetry')
def telemetry(value: Telemetry):
    sync.telemetry(value.position, value.paused, value.active)
    return {'ok': True}

class Action(Telemetry):
    seek: bool = False

@app.post('/api/action')
async def action(value: Action):
    autoplay.arm(False)
    await sync.action(value.position, value.paused, value.seek)
    return {'ok': True}

class Command(BaseModel):
    kind: Literal['chat', 'ready', 'room', 'playlist', 'playlistIndex', 'controller', 'reconnect']
    text: str = ''
    ready: bool = False
    files: list[str] = Field(default_factory=list)
    index: int = Field(default=0, ge=0)

@app.post('/api/command')
async def command(c: Command):
    if c.kind == 'reconnect':
        await sync.start()
    elif c.kind == 'chat':
        await sync.send({'Chat': c.text[:500]})
    elif c.kind == 'ready':
        sync.ready = c.ready
        autoplay.arm(c.ready)
        await sync.send({'Set': {'ready': {'isReady': c.ready, 'manuallyInitiated': True}}})
    elif c.kind == 'room':
        if not c.text.strip():
            raise HTTPException(400, 'La sala no puede estar vacía')
        store.config.server.room = c.text.strip()
        store.save()
        await sync.send({'Set': {'room': {'name': c.text.strip()}}})
    elif c.kind == 'playlist':
        await sync.send({'Set': {'playlistChange': {'files': c.files}}})
    elif c.kind == 'playlistIndex':
        if c.index >= len(sync.playlist):
            raise HTTPException(400, 'Índice inválido')
        await sync.send({'Set': {'playlistIndex': {'index': c.index}}})
        await sync.action(0, True, True)
    elif c.kind == 'controller':
        await sync.send({'Set': {'controllerAuth': {'room': store.config.server.room, 'password': c.text}}})
    return {'ok': True}

def byte_range(header, size):
    if not header:
        return 0, size - 1, False
    try:
        unit, value = header.split('=', 1)
        if unit != 'bytes' or ',' in value:
            raise ValueError()
        a, b = value.split('-', 1)
        if not a:
            suffix = int(b)
            if suffix <= 0:
                raise ValueError()
            start, end = max(0, size - suffix), size - 1
        else:
            start, end = int(a), min(int(b), size - 1) if b else size - 1
        if start < 0 or start >= size or end < start:
            raise ValueError()
        return start, end, True
    except (ValueError, TypeError):
        raise HTTPException(416, 'Rango inválido', headers={'Content-Range': f'bytes */{size}'})

@app.api_route('/raw/{source_id}', methods=['GET', 'HEAD'])
def raw(source_id: int, path: str, request: Request):
    remote = source(source_id)
    size = remote.size(path)
    start, end, partial = byte_range(request.headers.get('range'), size)
    headers = {'Accept-Ranges': 'bytes', 'Content-Length': str(max(0, end-start+1))}
    if partial:
        headers['Content-Range'] = f'bytes {start}-{end}/{size}'
    status = 206 if partial else 200
    mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    if request.method == 'HEAD':
        return Response(headers=headers, status_code=status, media_type=mime)
    return StreamingResponse(remote.chunks(path, start, end-start+1), headers=headers, status_code=status, media_type=mime)

@app.api_route('/cache/{name}', methods=['GET', 'HEAD'])
def cache(name: str):
    path = media.directory / name
    if Path(name).name != name or not path.is_file() or name.endswith('.partial.mp4'):
        raise HTTPException(404)
    if CAPTION_NAME.fullmatch(name):
        with caption_cache.lock:
            if not path.is_file(): raise HTTPException(404)
            caption_cache.touch(path)
            return Response(path.read_bytes(), media_type='image/png')
    return FileResponse(path, media_type='application/x-subrip' if path.suffix == '.srt' else None)


class FontCSS(BaseModel):
    url: str = Field(max_length=2048)

@app.get('/api/fonts')
def get_fonts():
    return fonts.catalog

@app.post('/api/fonts/css')
def import_font_css(body: FontCSS):
    return fonts.import_css(body.url)

def caption_png(text, style, key):
    with caption_cache.lock:
        return _caption_png(text, style, key)

def _caption_png(text, style, key):
    path = media.directory / ('caption-' + key + '.png')
    if not path.exists():
        result = render(text, style, fonts)
        buffer = io.BytesIO()
        result.save(buffer, format='PNG')
        with tempfile.NamedTemporaryFile(dir=media.directory, delete=False) as temporary:
            temporary.write(buffer.getvalue())
        os.replace(temporary.name, path)
    caption_cache.touch(path)
    return path

@app.post('/api/subtitle-preview')
def subtitle_preview(style: SubtitleStyle):
    text = '你好，世界。\nAsí se verán tus subtítulos.'
    key = hashlib.sha256((RENDER_VERSION+style.model_dump_json()+text).encode()).hexdigest()
    path = caption_png(text, style, key)
    return {'url': media.url('/cache/' + path.name)}

@app.get('/api/caption/{media_id}/{index}/{revision}.png')
def caption_image(media_id: str, index: int, revision: str):
    item = media.current
    if not item or item['id'] != media_id or revision not in caption_styles:
        raise HTTPException(404, 'Subtítulo no disponible')
    timeline_path = item.get('subtitleTimeline', '')
    if not timeline_path: raise HTTPException(404, 'Sin subtítulos de texto')
    cues = json.loads((media.directory / Path(timeline_path).name).read_text())['cues']
    if index < 0 or index >= len(cues): raise HTTPException(404, 'Subtítulo no disponible')
    key = hashlib.sha256((media_id+str(index)+revision).encode()).hexdigest()
    path = caption_png(cues[index]['text'], caption_styles[revision], key)
    return FileResponse(path, media_type='image/png')
