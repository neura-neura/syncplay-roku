import pysubs2
from bridge.subtitles import load_subtitles, timeline


def test_overlap_unsorted_and_offset():
    subs = pysubs2.SSAFile()
    subs.events = [pysubs2.SSAEvent(start=1500, end=3000, text='中文\\N¡Español!'),
                   pysubs2.SSAEvent(start=0, end=2000, text='Primero'),
                   pysubs2.SSAEvent(start=0, end=9000, text='comment', type='Comment')]
    subs.shift(ms=-500)
    assert timeline(subs) == [dict(start=0,end=1000,text='Primero'),
                             dict(start=1000,end=1500,text='中文\n¡Español!\nPrimero'),
                             dict(start=1500,end=2500,text='中文\n¡Español!')]


def test_unicode_encodings(tmp_path):
    text = '1\n00:00:01,000 --> 00:00:03,000\n中文\n¡Qué tal!\n'
    for encoding in ['utf-8', 'utf-8-sig', 'utf-16']:
        path = tmp_path / 'captions.srt'
        path.write_bytes(text.encode(encoding))
        assert timeline(load_subtitles(path)) == [dict(start=1000,end=3000,text='中文\n¡Qué tal!')]


def test_boundaries_tags_and_empty():
    subs = pysubs2.SSAFile.from_string('1\n00:00:00,000 --> 00:00:01,000\n<i>A &amp; B</i>\n\n2\n00:00:01,000 --> 00:00:02,000\nC\n')
    assert timeline(subs) == [dict(start=0,end=1000,text='A & B'), dict(start=1000,end=2000,text='C')]


def test_windows_multiline_srt(tmp_path):
    path = tmp_path / 'windows.srt'
    path.write_bytes(b'1\r\n00:12:20,080 --> 00:12:25,640\r\nThe Yumura family of three bought this \r\nhouse half a year ago and moved in.\r\n')
    cues = timeline(load_subtitles(path))
    assert cues == [dict(start=740080, end=745640, text='The Yumura family of three bought this \nhouse half a year ago and moved in.')]
