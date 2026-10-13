"""Original authoring export: exact downsampled derivatives of our V3 mathematical raster.
No morphology/color change; source PNGs stay untouched. NumPy/Pillow already used by generator.
"""
from pathlib import Path
from PIL import Image
import json,hashlib
root=Path(__file__).resolve().parents[2];folder=root/'public/models/galaxies-v3';manifest=json.loads((folder/'manifest.json').read_text());variants=[]
for size in [768,512]:
 target=folder/str(size);target.mkdir(exist_ok=True)
 for asset in manifest['assets']:
  image=Image.open(folder/asset['file']).resize((size,size),Image.Resampling.LANCZOS);out=target/(Path(asset['file']).stem+'.webp');image.save(out,quality=94,method=4)
  variants.append(dict(size=size,file=str(out.relative_to(folder)).replace('\\','/'),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest()))
manifest['quality_variants']=variants;manifest['quality_export']='assets/source/export_galaxy_quality.py';(folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print({s:sum(v['bytes'] for v in variants if v['size']==s) for s in [512,768]})
