"""Verify the public arrays and decoded images. Optionally test a running local origin."""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen
import numpy as np
from PIL import Image, ImageOps, ImageStat

here = Path(__file__).resolve().parent
root = here.parents[2]
manifest_path = root/'public/renders/journey-hd/manifest.json'
rows = json.loads(manifest_path.read_bytes())
origins = json.loads((here/'provenance.json').read_bytes())
journey = (root/'src/lib/journey.ts').read_text(encoding='utf-8')
decl = re.search(r'JOURNEY_ERAS\s*=\s*\[(.*?)\]',journey,re.S).group(1)
assert [row['id'] for row in rows] == [s for s in re.findall(r"""['"]([\w-]+)['"]""",decl) if s!='galaxies']
assert len(rows) == len(origins) == 11
hashes = set()
total = 0
if len(sys.argv)>1:
    assert json.load(urlopen(sys.argv[1]+'/renders/journey-hd/manifest.json',timeout=5)) == rows
for row, origin in zip(rows,origins,strict=True):
    assert origin['id']==row['id'] and row['caption'] and row['credit'] and row['license']
    assert row['kind'] in ('observation','illustration')
    assert hashlib.sha256((root/origin['input']).read_bytes()).hexdigest()==origin['inputSha256']
    for field,expected,variant in zip(('small','large'),((880,495),(1600,900)),origin['variants'],strict=True):
        url=row[field]
        assert url == variant['url'] == f"/renders/journey-hd/{row['id']}-{expected[0]}.webp"
        path=root/'public'/url[1:]
        with Image.open(path) as im:
            im.load()
            assert im.format=='WEBP' and im.size==expected and max(ImageStat.Stat(im).stddev)>12
        data=path.read_bytes()
        digest=hashlib.sha256(data).hexdigest()
        assert digest==variant['sha256'] and digest not in hashes
        hashes.add(digest)
        if len(sys.argv)>1:
            with urlopen(sys.argv[1]+url,timeout=5) as response:
                assert response.headers.get_content_type()=='image/webp' and response.read()==data
        total+=len(data)
print(f'{len(rows)} eras, {len(hashes)} distinct WebP files decoded, {total} bytes. HTTP origin: {sys.argv[1:]}.')


def colored_extent(image):
    rgb = np.asarray(image.convert('RGB')).astype('int16')
    y, x = np.where(rgb.max(axis=2) - rgb.min(axis=2) > 45)
    return int(np.ptp(x))+1, int(np.ptp(y))+1


with Image.open(here/'ilc_9yr_moll4096.png') as wmap:
    original_width, original_height = colored_extent(wmap)
    ratio = original_width/original_height
with Image.open(here/'soudan.jpg') as rock:
    crop = ImageOps.fit(rock.convert('RGB'), (1600,900), Image.Resampling.LANCZOS)
for width in (880,1600):
    with Image.open(root/f'public/renders/journey-hd/cmb-{width}.webp') as cmb:
        w,h = colored_extent(cmb)
        assert abs((w/h)/ratio-1)<.01
        print(f'WMAP {width}: colored extent {w}x{h}, source ratio {ratio:.3f}, output {w/h:.3f}')
    with Image.open(root/f'public/renders/journey-hd/oxygen-{width}.webp') as public_rock:
        expected = crop.resize(public_rock.size, Image.Resampling.LANCZOS)
        error = np.abs(np.asarray(expected).astype('int16') - np.asarray(public_rock)).mean()
        assert error<6
        print(f'Soudan {width}: mean RGB error vs archival crop {error:.2f}/255')
for row in rows:
    if not row['source']:
        assert row['license']=='Material autoral do projeto'
