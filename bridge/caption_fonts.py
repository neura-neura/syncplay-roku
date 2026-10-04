"""Import only font-face data from CSS; never execute or inject remote styles."""
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
import tinycss2
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

BUNDLED = Path(__file__).with_name('fonts')
GOTHAM_VARIANTS = {300: 'Light', 400: 'Regular', 500: 'Medium', 700: 'Bold', 900: 'Black'}


def match_weight(available, requested):
    """CSS font matching for static faces, including the special 400–500 range."""
    weights = sorted(set(available))
    if 400 <= requested <= 500:
        order = ([w for w in weights if requested <= w <= 500]
                 + sorted((w for w in weights if w < requested), reverse=True)
                 + [w for w in weights if w > 500])
    elif requested < 400:
        order = (sorted((w for w in weights if w <= requested), reverse=True)
                 + [w for w in weights if w > requested])
    else:
        order = ([w for w in weights if w >= requested]
                 + sorted((w for w in weights if w < requested), reverse=True))
    return order[0]


class Fonts:
    def __init__(self, directory):
        self.directory = directory / 'fonts'
        self.directory.mkdir(exist_ok=True)
        self.manifest = self.directory / 'catalog.json'
        self.catalog = json.loads(self.manifest.read_text()) if self.manifest.exists() else {}
        installed = []
        for path in Path('/usr/share/fonts').rglob('*'):
            if path.suffix.lower() not in ('.ttf', '.otf'): continue
            try:
                with TTFont(path) as f:
                    family = f['name'].getDebugName(1)
                    if family:
                        installed.append(dict(family=family, weight=f['OS/2'].usWeightClass, file=str(path)))
            except Exception:
                continue
        if installed: self.catalog['0000000000000000'] = {'url': 'Fuentes instaladas en el puente', 'faces': installed}

    def fetch(self, url, limit):
        if urlsplit(url).scheme not in ('http', 'https'):
            raise ValueError('La URL debe empezar con http:// o https://')
        with requests.get(url, timeout=(5, 20), stream=True, headers={'User-Agent': 'Noir-Roku/1.0'}) as r:
            r.raise_for_status()
            data = bytearray()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data) > limit:
                    raise ValueError('Archivo de fuente demasiado grande')
            return bytes(data), r.url

    def import_css(self, url):
        raw, base = self.fetch(url, 1024 * 1024)
        faces = []
        for rule in tinycss2.parse_stylesheet(raw.decode('utf-8-sig'), skip_comments=True, skip_whitespace=True):
            if rule.type != 'at-rule' or rule.lower_at_keyword != 'font-face' or rule.content is None:
                continue
            props = {x.lower_name: x.value for x in tinycss2.parse_declaration_list(rule.content) if x.type == 'declaration'}
            family = tinycss2.serialize(props.get('font-family', [])).strip().strip('\"\'')
            if not family or len(family) > 120: continue
            if tinycss2.serialize(props.get('font-style', [])).strip() not in ('', 'normal'): continue
            weight_text = tinycss2.serialize(props.get('font-weight', [])).strip()
            try: weight = int(weight_text.split()[0])
            except (ValueError, IndexError): weight = 700 if weight_text == 'bold' else 400
            urls = []
            for token in props.get('src', []):
                if token.type == 'url': urls.append(urljoin(base, token.value))
                elif token.type == 'function' and token.lower_name == 'url':
                    urls.append(urljoin(base, tinycss2.serialize(token.arguments).strip().strip('\"\'')))
            # Prefer sfnt/webfonts over legacy EOT and SVG resources.
            urls.sort(key=lambda u: 1 if urlsplit(u).path.lower().endswith(('.eot', '.svg')) else 0)
            for source in urls:
                try:
                    data, _ = self.fetch(source, 24 * 1024 * 1024)
                    font = TTFont(io.BytesIO(data))
                    variable = 'fvar' in font
                    font.flavor = None
                    filename = hashlib.sha256(data + str(weight).encode()).hexdigest() + '.ttf'
                    font.save(self.directory / filename)
                    faces.append(dict(family=family, weight=weight, file=filename, variable=variable))
                    break
                except Exception:
                    continue
            if len(faces) >= 64: break
        if not faces: raise ValueError('No encontré fuentes TTF, OTF, WOFF o WOFF2 válidas en @font-face.')
        key = hashlib.sha256((url + json.dumps(faces, sort_keys=True)).encode()).hexdigest()[:16]
        self.catalog[key] = {'url': url, 'faces': faces}
        temp = self.manifest.with_suffix('.tmp')
        temp.write_text(json.dumps(self.catalog, ensure_ascii=False))
        temp.replace(self.manifest)
        return {'id': key, 'families': sorted(set(f['family'] for f in faces))}

    def choices(self, family, weight, css_id=''):
        if css_id in self.catalog:
            faces = [f for f in self.catalog[css_id]['faces'] if f['family'] == family]
            if faces:
                # Keep all subsets of the nearest weight (Google Fonts unicode-range).
                variable_faces = [f for f in faces if f.get('variable')]
                if variable_faces:
                    paths = []
                    for face in variable_faces:
                        source = self.directory / face['file']
                        target = self.directory / (source.stem + '-' + str(weight) + '.ttf')
                        if not target.exists():
                            with TTFont(source) as vf:
                                axes = {a.axisTag: (max(a.minValue, min(weight, a.maxValue)) if a.axisTag == 'wght' else a.defaultValue) for a in vf['fvar'].axes}
                                instance = instantiateVariableFont(vf, axes, inplace=True)
                                instance.save(target)
                        paths.append(target)
                    return paths
                nearest = match_weight([f['weight'] for f in faces], weight)
                return [self.directory / f['file'] for f in faces if f['weight'] == nearest]
        if family == 'Noto Sans CJK':
            return [BUNDLED / ('NotoSansCJKsc-Bold.otf' if weight >= 600 else 'NotoSansCJKsc-Regular.otf')]
        nearest = match_weight(GOTHAM_VARIANTS, weight)
        return [BUNDLED / f'GothamPro-{nearest}.ttf']
