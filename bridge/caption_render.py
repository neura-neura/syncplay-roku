"""Render small transparent subtitle overlays only; never decode the video."""
from functools import lru_cache
import numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fontTools.ttLib import TTFont
from .caption_fonts import BUNDLED
from .subtitles import normalize_newlines

RENDER_VERSION = "4-continuous-font-weights"

@lru_cache(maxsize=128)
def cmap(path):
    with TTFont(path) as font: return frozenset(font.getBestCmap())

@lru_cache(maxsize=128)
def font(path, size):
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=512)
def glyph_field(path, size, char):
    """Supersampled signed distance to a glyph edge, aligned to its baseline."""
    scale = 3
    face = font(path, size * scale)
    left, top, right, bottom = face.getbbox(char, anchor='ls')
    pad = 6
    # Snap to the output pixel grid so adjacent weights share sampling alignment.
    bounds = ((left-pad)//scale*scale, (top-pad)//scale*scale,
              -(-(right+pad)//scale)*scale, -(-(bottom+pad)//scale)*scale)
    mask = Image.new('L', (bounds[2]-bounds[0], bounds[3]-bounds[1]))
    ImageDraw.Draw(mask).text((-bounds[0], -bounds[1]), char, font=face, fill=255, anchor='ls')
    alpha = np.asarray(mask, dtype=np.float32) / 255
    inside = alpha >= .5
    field = distance_transform_edt(inside) - distance_transform_edt(~inside)
    field -= np.where(inside, .5, -.5)
    edges = (alpha > 0) & (alpha < 1)
    field[edges] = alpha[edges] - .5
    return bounds, field.astype(np.float32), mask


@lru_cache(maxsize=512)
def glyph_mask(low, high, size, char, fraction):
    if fraction == 1:
        return glyph_mask(high, high, size, char, 0)
    a, af, am = glyph_field(low, size, char)
    if fraction == 0 or low == high:
        bounds, mask = a, am
    else:
        b, bf, bm = glyph_field(high, size, char)
        bounds = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
        shape = (bounds[3]-bounds[1], bounds[2]-bounds[0])
        # Extend distances into the common canvas without introducing mask edges.
        fields = []
        for box, field in [(a, af), (b, bf)]:
            ys = np.arange(shape[0]) + bounds[1] - box[1]
            xs = np.arange(shape[1]) + bounds[0] - box[0]
            fields.append(field[np.clip(ys, 0, field.shape[0]-1)[:, None],
                                np.clip(xs, 0, field.shape[1]-1)[None, :]])
        mixed = fields[0] * (1-fraction) + fields[1] * fraction
        mask = Image.fromarray((np.clip(mixed + .5, 0, 1)*255).astype('uint8'))
    width = max(1, round(mask.width/3)); height = max(1, round(mask.height/3))
    return (bounds[0]/3, bounds[1]/3), mask.resize((width,height), Image.Resampling.LANCZOS)


def render(text, style, fonts):
    # Also normalize already-cached timelines created by previous versions.
    text = normalize_newlines(text)
    size = style.size
    pairs = fonts.blend_choices(style.font_family, style.weight, style.css_id)
    pairs += fonts.blend_choices('Noto Sans CJK', style.weight)
    loaded = [(str(a), str(b), t, cmap(str(a)), cmap(str(b))) for a,b,t in pairs]
    def pick(c):
        return next((p for p in loaded if ord(c) in p[3] and ord(c) in p[4]),
                    next((p for p in loaded if ord(c) in p[3]), loaded[-1]))
    def advance(c):
        a,b,t,ca,cb = pick(c)
        if ord(c) not in cb: b,t = a,0
        return max(.1, font(a,size).getlength(c)*(1-t) + font(b,size).getlength(c)*t + style.letter_spacing)
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
            a,b,t,ca,cb = pick(c)
            if ord(c) not in cb: b,t = a,0
            offset, mask = glyph_mask(a,b,size,c,t)
            d.bitmap((round(x+offset[0]), round(baseline+offset[1])), mask, fill=style.color)
            x+=advance(c)
    if style.shadow:
        for blur, alpha in [(7, 255), (18, 204)]:
            mask=ink.getchannel('A').filter(ImageFilter.GaussianBlur(blur)).point(lambda a: a*alpha//255)
            shadow=Image.new('RGBA',image.size,(0,0,0,0));shadow.putalpha(mask)
            image.alpha_composite(shadow)
    image.alpha_composite(ink)
    return image
