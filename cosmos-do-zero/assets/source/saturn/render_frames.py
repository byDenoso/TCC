"""Run in Blender background mode with the existing packed saturn.blend open."""
import hashlib
import json
import math
import shutil
from pathlib import Path

import bpy

source = Path(__file__).resolve().parent
blend = source / 'saturn.blend'
assert Path(bpy.data.filepath).resolve() == blend
media = source.parents[2] / 'public/models/saturn'
frames = media / 'frames'
frames.mkdir(exist_ok=True)
scene = bpy.context.scene
camera = scene.camera
distance = camera.location.length
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.render.threads_mode = 'FIXED'
scene.render.threads = 3
scene.cycles.samples = 8
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.denoising_use_gpu = False
scene.render.use_persistent_data = True
scene.render.resolution_x = 704
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
camera.data.ortho_scale = 6.8
scene.render.image_settings.file_format = 'WEBP'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.quality = 88

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

records = []
for degree in range(91):
    angle = math.radians(degree)
    camera.location = (0, -distance * math.cos(angle), distance * math.sin(angle))
    camera.rotation_euler = (math.pi / 2 - angle, 0, 0)
    frame = frames / f'{degree:02}.webp'
    scene.render.filepath = str(frame)
    bpy.ops.render.render(write_still=True)
    records.append({'degree': degree, 'file': 'frames/' + frame.name, 'sha256': digest(frame)})

shutil.copyfile(frames / '30.webp', media / 'poster.webp')
manifest = {
    'source': 'assets/source/saturn/saturn.blend', 'sourceSha256': digest(blend),
    'blender': bpy.app.version_string, 'engine': 'Cycles', 'device': 'CPU', 'threads': 3,
    'samples': 8, 'denoiser': 'OpenImageDenoise CPU', 'resolution': [704, 512],
    'orthoWidth': camera.data.ortho_scale, 'webpQuality': 88,
    'poster': {'file': 'poster.webp', 'degree': 30, 'sha256': digest(media / 'poster.webp')},
    'frames': records,
}
(media / 'frames.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

