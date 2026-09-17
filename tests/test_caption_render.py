from pathlib import Path
import io
import pytest
from PIL import Image
from fontTools.ttLib import TTFont
from bridge.caption_fonts import Fonts, BUNDLED
from bridge.caption_render import render
from bridge.config import SubtitleStyle


def test_noir_defaults_geometry_and_unicode(tmp_path):
    f=Fonts(tmp_path)
    style=SubtitleStyle()
    assert (style.size,style.weight,style.opacity,style.bottom)==(38,500,23,4)
    image=render('你好\nEspañol',style,f)
    assert image.getbbox()
    assert image.width<600
    large=render('你好\nEspañol',style.model_copy(update={'size':72}),f)
    assert large.width>image.width and large.height>image.height
    wide=render('Hola',style.model_copy(update={'custom_width':True}),f)
    assert wide.width>1400
    transparent=render('Hola',style.model_copy(update={'opacity':0,'shadow':False}),f)
    assert transparent.getpixel((0,0))[3]==0
    colored=render('Hola',style.model_copy(update={'background':'#ff0000','opacity':100,'radius':0,'shadow':False}),f)
    assert colored.getpixel((0,0))==(255,0,0,255)


def test_css_relative_woff_and_persistence(tmp_path,monkeypatch):
    font=TTFont(BUNDLED/'GothamPro-400.ttf');font.flavor='woff2';buffer=io.BytesIO();font.save(buffer)
    f=Fonts(tmp_path)
    def fetch(url,limit):
        if url.endswith('.css'):
            return b'@font-face {font-family:"Test Family";font-weight:400;src:url("fonts/test.woff2") format("woff2")}',url
        assert url=='https://example.test/fonts/test.woff2'
        return buffer.getvalue(),url
    monkeypatch.setattr(f,'fetch',fetch)
    result=f.import_css('https://example.test/style.css')
    assert result['families']==['Test Family']
    restored=Fonts(tmp_path)
    paths=restored.choices('Test Family',400,result['id'])
    assert len(paths)==1 and paths[0].exists()
    assert TTFont(paths[0]).flavor is None
    assert render('中文 y texto',SubtitleStyle(font_family='Test Family',css_id=result['id']),restored).getbbox()


def test_windows_line_endings_render_identically(tmp_path):
    fonts = Fonts(tmp_path)
    style = SubtitleStyle()
    text = 'The Yumura family of three bought this \nhouse half a year ago and moved in.'
    expected = render(text, style, fonts)
    for separator in ['\r\n', '\r']:
        actual = render(text.replace('\n', separator), style, fonts)
        assert actual.size == expected.size
        assert actual.tobytes() == expected.tobytes()
