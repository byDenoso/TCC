"""python scripts/pack_solar_turntable.py ATLAS_DIR [--verify-only]
Crop offline Cycles sheets, then verify every distributed image and source.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/models/solar-turntable'
MAPS = ROOT / 'assets/source/solar-materials'
NASA = 'https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/'
DEM = ROOT / 'assets/source/solar-turntable/ldem_4_uint.tif'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sources():
    audit = json.loads((MAPS / 'manifest.json').read_text())
    records = []
    for m in audit['materials']:
        source = next(p for p in MAPS.glob(m['world']+'.*'))
        record = dict(m, path=source.relative_to(ROOT).as_posix(), sha256=digest(source))
        original = m.get('original')
        if original:
            record['originalSha256'] = digest(ROOT / original)
            record['licenseUrl'] = audit['policy_url']
        else:
            record['licenseUrl'] = 'https://creativecommons.org/publicdomain/zero/1.0/'
        if m['world'] == 'lua':
            record['downloadUrl'] = NASA + 'lroc_color_2k.jpg'
        records.append(record)
    ring = MAPS / 'saturno-rings.png'
    records.append(dict(world='saturno-rings', path=ring.relative_to(ROOT).as_posix(),
        sha256=digest(ring), credit='Cosmos do Zero', source='assets/source/prepare_solar_materials.py',
        license='Original project artwork; no separate redistribution license stated in the source manifest.'))
    records.append(dict(world='lua-height', path=DEM.relative_to(ROOT).as_posix(),
        sha256=digest(DEM), source_url='https://svs.gsfc.nasa.gov/4720/',
        downloadUrl=NASA+'ldem_4_uint.tif', credit='NASA Scientific Visualization Studio / Ernie Wright; LRO/LOLA',
        license='NASA resource usage policy; retain credit', licenseUrl=audit['policy_url'],
        status='16-bit height map, illustrative bump strength'))
    return records

def pack(directory):
    layout = json.loads((directory/'layout.json').read_text())
    size, rows, names = layout['size'], layout['rows'], layout['worlds']
    frames, sheets = [], []
    for batch in range(36//rows):
        path = directory/f'atlas-{batch}.png'
        atlas = OUT/'atlases'/f'{batch:02}.webp'
        atlas.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(path) as sheet:
            assert sheet.size == (len(names)*size, rows*size)
            sheet.save(atlas, 'WEBP', quality=81, method=4)
            sheets.append(dict(file=atlas.relative_to(OUT).as_posix(), sourcePngSha256=digest(path),
                source=path.name, sha256=digest(atlas), bytes=atlas.stat().st_size, firstDegrees=batch*rows*10))
            for col, name in enumerate(names):
                (OUT/name).mkdir(parents=True, exist_ok=True)
                for row in range(rows):
                    number = batch*rows+row
                    crop = sheet.crop((col*size,row*size,(col+1)*size,(row+1)*size))
                    file = OUT/name/f'{number:02}.webp'
                    crop.save(file, 'WEBP', quality=81, method=5)
                    frames.append(dict(file=file.relative_to(OUT).as_posix(), degrees=number*10,
                        bytes=file.stat().st_size, sha256=digest(file)))
    used = {name: [name.split('-')[0]] for name in names}
    for name in names:
        if name.startswith('terra'):
            used[name].append('terra-roughness')
        if name in ('terra', 'terra-nuvens'):
            used[name].append('terra-clouds')
    used['saturno'].append('saturno-rings')
    used['lua'].append('lua-height')
    data = dict(render=layout, atlases=sheets, sources=sources(), seriesSources=used, frames=frames)
    (OUT/'manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2),encoding='utf8')

def verify():
    data = json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    layout = data['render']
    expected = {f'{name}/{n:02}.webp' for name in layout['worlds'] for n in range(36)}
    assert expected == {p.relative_to(OUT).as_posix() for p in OUT.rglob('*.webp') if p.parent.name != 'atlases'}
    assert len(data['frames']) == len(expected)
    assert {f['file'] for f in data['frames']} == expected
    for s in data['sources']:
        assert digest(ROOT/s['path']) == s['sha256']
        if 'original' in s:
            assert digest(ROOT/s['original']) == s['originalSha256']
    atlases = data['atlases']
    size, rows, worlds = layout['size'], layout['rows'], layout['worlds']
    assert {s['file'] for s in atlases} == {f'atlases/{i:02}.webp' for i in range(36//rows)}
    for sheet in atlases:
        path = OUT/sheet['file']
        assert digest(path) == sheet['sha256'] and path.stat().st_size == sheet['bytes']
        with Image.open(path) as atlas:
            assert atlas.size == (len(worlds)*size, rows*size)
            for col, name in enumerate(worlds):
                for row in range(rows):
                    n = sheet['firstDegrees']//10 + row
                    cell = atlas.crop((col*size,row*size,(col+1)*size,(row+1)*size))
                    with Image.open(OUT/name/f'{n:02}.webp') as frame:
                        error = ImageStat.Stat(ImageChops.difference(cell, frame)).mean
                        assert max(error) < 5, (name, n, error)
    seen = set()
    for f in data['frames']:
        path = OUT/f['file']
        assert path.stat().st_size == f['bytes'] and digest(path) == f['sha256']
        assert int(path.stem)*10 == f['degrees']
        with Image.open(path) as image:
            image.load()
            assert image.format == 'WEBP' and image.mode == 'RGBA'
            assert image.size == (layout['size'],)*2
            alpha = image.getchannel('A')
            x0,y0,x1,y1 = alpha.getbbox()
            assert 0<x0<x1<image.width and 0<y0<y1<image.height
            assert alpha.getpixel((image.width//2,image.height//2)) == 255
            assert ImageStat.Stat(image.convert('L'),mask=alpha).stddev[0] > 4
            key = path.parent.name, hashlib.sha256(image.tobytes()).digest()
            assert key not in seen, path
            seen.add(key)
    return f"{len(seen)} decoded distinct views within their series; {sum(f['bytes'] for f in data['frames'])} WebP bytes"

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', nargs='?', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if not args.verify_only:
        if not args.directory:
            parser.error('atlas directory required')
        pack(args.directory)
    print(verify())

