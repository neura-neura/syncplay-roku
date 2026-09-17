"""Render small transparent subtitle overlays only; never decode the video."""
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fontTools.ttLib import TTFont
from .caption_fonts import BUNDLED
from .subtitles import normalize_newlines

RENDER_VERSION = "2-newlines"

@lru_cache(maxsize=128)
def cmap(path):
    with TTFont(path) as font: return frozenset(font.getBestCmap())

@lru_cache(maxsize=128)
def font(path, size):
    return ImageFont.truetype(path, size)


def render(text, style, fonts):
    # Also normalize already-cached timelines created by previous versions.
    text = normalize_newlines(text)
    size = style.size
    paths = fonts.choices(style.font_family, style.weight, style.css_id)
    paths += [BUNDLED / ('NotoSansCJKsc-Bold.otf' if style.weight >= 600 else 'NotoSansCJKsc-Regular.otf')]
    loaded = [(font(str(p),size), cmap(str(p))) for p in paths]
    def pick(c): return next((f for f, chars in loaded if ord(c) in chars), loaded[-1][0])
    def advance(c): return max(.1, pick(c).getlength(c) + style.letter_spacing)
    limit = 1920 * (min(92,style.max_width) if style.custom_width else 92) / 100 - 2*style.padding_x
    lines = []
    for paragraph in text.split('\n'):
        current = ''
        for c in paragraph:
            if current and sum(advance(x) for x in current+c) > limit:
                split = current.rfind(' ')
                if split > 0:
                    lines.append(current[:split]); current=current[split+1:]+c
                else:
                    lines.append(current); current=c
            else: current+=c
        lines.append(current)
    widths = [sum(advance(c) for c in line) for line in lines]
    step = size * style.line_height
    width = min(1920, max(1, int((limit if style.custom_width else max(widths, default=1))+2*style.padding_x+4)))
    height = min(1080, max(1,int(step*len(lines)+2*style.padding_y+8)))
    image = Image.new('RGBA',(width,height))
    draw=ImageDraw.Draw(image)
    bg=tuple(bytes.fromhex(style.background[1:]))+(round(style.opacity*255/100),)
    draw.rounded_rectangle((0,0,width-1,height-1),radius=style.radius,fill=bg)
    ink=Image.new('RGBA',image.size); d=ImageDraw.Draw(ink)
    for i,line in enumerate(lines):
        x=(width-widths[i])/2
        baseline=style.padding_y + i*step + (step-size)/2 + size*.85
        for c in line:
            d.text((x,baseline),c,font=pick(c),fill=style.color,anchor='ls')
            x+=advance(c)
    if style.shadow:
        for blur, alpha in [(7, 255), (18, 204)]:
            mask=ink.getchannel('A').filter(ImageFilter.GaussianBlur(blur)).point(lambda a: a*alpha//255)
            shadow=Image.new('RGBA',image.size,(0,0,0,0));shadow.putalpha(mask)
            image.alpha_composite(shadow)
    image.alpha_composite(ink)
    return image
