import asyncio
import hashlib
import json
import mimetypes
import time
from pathlib import Path
from urllib.parse import urlencode
import pysubs2
from .storage import Remote
from .subtitles import load_subtitles, timeline

class Media:
    def __init__(self, store):
        self.store = store
        self.directory = store.directory / 'media'
        self.directory.mkdir(exist_ok=True)
        self.current = None
        self.status = 'idle'
        self.error = ''
        self.task = None
        self.process = None
        self.progress = ''
        self.generation = 0
        self.duration = 0

    def url(self, path):
        return self.store.config.public_url.rstrip('/') + path + ('&' if '?' in path else '?') + urlencode({'token': self.store.config.token})

    async def close(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()

    async def prepare(self, video, subtitle=None):
        await self.close()
        self.generation += 1
        self.status, self.error, self.progress = 'preparing', '', 'Analizando video'
        self.current = None
        self.task = asyncio.create_task(self._prepare(video, subtitle))

    async def _run(self, *args):
        self.process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        if args[0] == 'ffmpeg':
            error_task = asyncio.create_task(self.process.stderr.read())
            while line := await self.process.stdout.readline():
                if line.startswith(b'out_time_us=') and self.duration:
                    try:
                        percent = min(99, int(float(line.split(b'=')[1]) / 1000000 / self.duration * 100))
                        self.progress = f'Preparando video compatible: {percent}%'
                    except ValueError:
                        pass
            await self.process.wait()
            out, err = b'', await error_task
        else:
            out, err = await asyncio.wait_for(self.process.communicate(), 60)
        if self.process.returncode:
            raise ValueError(err.decode(errors='replace')[-1200:])
        return out

    async def _prepare(self, video, subtitle):
        try:
            cfg = self.store.config
            remote = Remote(cfg.sources[video['source']])
            identity = await asyncio.to_thread(remote.identity, video['path'])
            size = identity[0]
            raw_url = self.url('/raw/' + str(video['source']) + '?' + urlencode({'path': video['path']}))
            probe = json.loads(await self._run('ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', raw_url))
            duration = float(probe['format'].get('duration', 0))
            self.duration = duration
            streams = probe['streams']
            v = next(x for x in streams if x['codec_type'] == 'video')
            audio = [x for x in streams if x['codec_type'] == 'audio']
            if audio and cfg.audio_track >= len(audio):
                raise ValueError(f'Pista de audio inválida. Hay {len(audio)} pistas (desde 0).')
            a = audio[cfg.audio_track] if audio else {}
            sub_url = ''
            timeline_path = ''
            sub_file = None
            source_identity = cfg.sources[video['source']].model_dump(exclude={'password'})
            sub_identity = None
            if subtitle:
                sr = Remote(cfg.sources[subtitle['source']])
                sub_identity = [cfg.sources[subtitle['source']].model_dump(exclude={'password'}), await asyncio.to_thread(sr.identity, subtitle['path'])]
            key = hashlib.sha256(json.dumps([video, subtitle, identity, source_identity, sub_identity, cfg.video_mode, cfg.subtitle_mode, cfg.audio_track, cfg.subtitle_offset], sort_keys=True).encode()).hexdigest()[:24]
            if subtitle:
                sub_file = self.directory / (key + Path(subtitle['path']).suffix.lower())
                sr = Remote(cfg.sources[subtitle['source']])
                await asyncio.to_thread(sr.download, subtitle['path'], sub_file, 20 * 1024 * 1024)
                if cfg.subtitle_mode == 'text':
                    srt = self.directory / (key + '.srt')
                    def convert():
                        subs = load_subtitles(sub_file)
                        subs.shift(s=cfg.subtitle_offset)
                        subs.save(str(srt), format_='srt')
                        srt.with_suffix('.json').write_text(json.dumps({'cues': timeline(subs)}, ensure_ascii=False), encoding='utf-8')
                    await asyncio.to_thread(convert)
                    sub_url = self.url('/cache/' + srt.name)
                    timeline_path = '/cache/' + srt.with_suffix('.json').name
                elif cfg.subtitle_offset:
                    shifted = sub_file.with_name(key + '-shifted.ass')
                    subs = load_subtitles(sub_file)
                    subs.shift(s=cfg.subtitle_offset)
                    subs.save(str(shifted))
                    sub_file = shifted
            burn = bool(sub_file and cfg.subtitle_mode == 'burn')
            compatible = v.get('codec_name') in ('h264', 'hevc', 'vp9') and v.get('pix_fmt') in ('yuv420p', 'yuv420p10le')
            if v.get('codec_name') == 'h264' and v.get('pix_fmt') != 'yuv420p':
                compatible = False
            audio_ok = a.get('codec_name') in ('aac', 'ac3', 'eac3', 'mp3', None)
            transcode = cfg.video_mode == 'transcode' or burn or (cfg.video_mode == 'auto' and not compatible)
            remux = cfg.video_mode != 'direct' and (cfg.audio_track != 0 or not audio_ok or Path(video['path']).suffix.lower() not in ('.mp4', '.m4v'))
            url = raw_url
            if transcode or remux:
                dest = self.directory / (key + '.mp4')
                if not dest.exists():
                    self.progress = 'Preparando MP4 compatible. Puede tardar varios minutos.'
                    temporary = self.directory / (key + '.partial.mp4')
                    args = ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-progress', 'pipe:1', '-i', raw_url, '-map', '0:v:0', '-map', f'0:a:{cfg.audio_track}?', '-sn']
                    if transcode:
                        args += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']
                        if burn:
                            # Cache path is generated, never supplied by remote file names.
                            escaped = str(sub_file).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
                            args += ['-vf', "subtitles=filename='" + escaped + "'"]
                    else:
                        args += ['-c:v', 'copy']
                    args += ['-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-movflags', '+faststart', str(temporary)]
                    await self._run(*args)
                    temporary.replace(dest)
                url = self.url('/cache/' + dest.name)
            self.current = dict(id=key + '-' + str(self.generation), title=Path(video['path']).name, url=url,
                                format='mp4' if transcode or remux else ('mkv' if video['path'].lower().endswith('.mkv') else 'mp4'),
                                subtitle=sub_url, subtitleTimeline=timeline_path, duration=duration, size=size, video=video, subtitles=subtitle,
                                audioTracks=[{'index': i, 'codec': x['codec_name'], 'language': x.get('tags', {}).get('language', 'und')} for i, x in enumerate(audio)])
            self.status, self.progress = 'ready', ''
            cfg.last_video, cfg.last_subtitle = video, subtitle
            self.store.save()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.error, self.status = str(e).replace(self.store.config.token, '[token]'), 'error'

    def snapshot(self):
        return {'status': self.status, 'error': self.error, 'progress': self.progress, 'current': self.current}
