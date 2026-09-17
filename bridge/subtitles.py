"""Text-only captions: Unicode decoding and non-overlapping display intervals."""
from collections import defaultdict
import html
import re
import pysubs2


def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def load_subtitles(path):
    data = path.read_bytes()
    encoding = 'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        text = data.decode('cp1252')
    return pysubs2.SSAFile.from_string(normalize_newlines(text))


def timeline(subs):
    boundaries = defaultdict(list)
    for i, cue in enumerate(subs):
        text = normalize_newlines(html.unescape(re.sub(r'<[^>]+>', '', cue.plaintext))).strip()
        start, end = max(0, cue.start), cue.end
        if cue.is_comment or not text or end <= start:
            continue
        boundaries[start].append((i, text))
        boundaries[end].append((i, None))
    active, result = {}, []
    times = sorted(boundaries)
    for j, start in enumerate(times[:-1]):
        for i, text in boundaries[start]:
            if text is None:
                active.pop(i, None)
            else:
                active[i] = text
        if active:
            text = '\n'.join(active[i] for i in sorted(active))
            if result and result[-1]['end'] == start and result[-1]['text'] == text:
                result[-1]['end'] = times[j + 1]
            else:
                result.append(dict(start=start, end=times[j + 1], text=text))
    return result
