"""Run in Blender background mode with the existing packed saturn.blend open."""
import math
from pathlib import Path

import bpy

source = Path(bpy.data.filepath).resolve().parent
blend = source / 'saturn.blend'
assert Path(bpy.data.filepath).resolve() == blend
media = source.parents[2] / 'public/models/worlds-hd'
frames = media / 'saturn-tilt'
frames.mkdir(exist_ok=True)
scene = bpy.context.scene
camera = scene.camera
distance = camera.location.length
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.render.threads_mode = 'FIXED'
scene.render.threads = 4
scene.cycles.samples = 2
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.denoising_use_gpu = False
scene.render.use_persistent_data = True
scene.render.resolution_x = 1408
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
camera.data.ortho_scale = 6.8
scene.render.image_settings.file_format = 'WEBP'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.quality = 88

for degree in range(91):
    scene.cycles.samples = 8 if degree in {0, 30, 90} else 2
    angle = math.radians(degree)
    camera.location = (0, -distance * math.cos(angle), distance * math.sin(angle))
    camera.rotation_euler = (math.pi / 2 - angle, 0, 0)
    frame = frames / f'{degree:02}.webp'
    scene.render.filepath = str(frame.with_suffix('.tmp.webp'))
    bpy.ops.render.render(write_still=True)
    frame.with_suffix('.tmp.webp').replace(frame)
