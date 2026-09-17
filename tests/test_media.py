import asyncio
import functools
import json
import shutil
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest
import pysubs2
from bridge.config import Store
from bridge.media import Media

@pytest.mark.parametrize('mode,video_mode', [('text', 'transcode'), ('burn', 'transcode'), ('text', 'direct')])
def test_actual_ffmpeg_subtitle_pipeline(tmp_path, monkeypatch, mode, video_mode):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg is required for media integration tests')
    remote = tmp_path / 'remote'
    remote.mkdir()
    clip = remote / 'clip.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=black:s=320x180:r=24',
                    '-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(clip)],check=True)
    subs = pysubs2.SSAFile()
    subs.events.append(pysubs2.SSAEvent(start=100,end=1000,text='{\\i1}Noir test'))
    subs.save(str(remote/'captions.ass'))
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
    server = ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(remote)))
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    class LocalRemote:
        def __init__(self, source): pass
        def identity(self, path): return [(remote/Path(path).name).stat().st_size,'v1']
        def download(self,path,destination,limit): shutil.copyfile(remote/Path(path).name,destination)
    monkeypatch.setattr('bridge.media.Remote',LocalRemote)
    store=Store(tmp_path/'data')
    store.config.subtitle_mode=mode
    store.config.subtitle_offset=.5
    store.config.video_mode=video_mode
    media=Media(store)
    original_url=media.url
    media.url=lambda path: f'http://127.0.0.1:{server.server_port}/clip.mp4' if path.startswith('/raw/') else original_url(path)
    try:
        asyncio.run(media._prepare({'source':0,'path':'/clip.mp4'},{'source':0,'path':'/captions.ass'}))
        assert media.status=='ready', media.error
        if video_mode == 'direct':
            assert not list(media.directory.glob('*.mp4'))
            assert media.current['url'].endswith('/clip.mp4')
        else:
            output=next(media.directory.glob('*.mp4'))
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))
            assert probe['streams'][0]['codec_name']=='h264'
        if mode=='text':
            converted=pysubs2.load(str(next(media.directory.glob('*.srt'))))
            assert converted[0].start==600
            assert converted[0].plaintext=='Noir test'
            cues=json.loads(next(media.directory.glob('*.json')).read_text())['cues']
            assert cues == [dict(start=600,end=1500,text='Noir test')]
            assert media.current['subtitleTimeline'].endswith('.json')
        else:
            assert media.current['subtitle']==''
            pixels=subprocess.check_output(['ffmpeg','-v','error','-ss','0.8','-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'])
            assert max(pixels)>180  # White ASS glyphs were burned onto the black test frame.
        assert store.config.last_video['path']=='/clip.mp4'
    finally:
        server.shutdown();server.server_close();thread.join(2)
