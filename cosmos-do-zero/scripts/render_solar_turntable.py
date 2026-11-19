"""Run with Blender -b -t 4 --python-exit-code 1 -P scripts/render_solar_turntable.py.
Set SOLAR_ATLAS_DIR to the intermediate PNG directory; SOLAR_BATCH selects one batch.
Set SOLAR_SAVE_SCENE=1 to save the packed editable scene instead of rendering.
"""
import hashlib
import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / 'assets/source/solar-materials'
DEM = ROOT / 'assets/source/solar-turntable/ldem_4_uint.tif'
OUT = Path(os.environ['SOLAR_ATLAS_DIR'])
OUT.mkdir(parents=True, exist_ok=True)
WORLDS = 'mercurio venus terra marte jupiter saturno urano netuno lua saturno-globo terra-solo terra-nuvens terra-ar'.split()
SIZE, GAP, ROWS = 320, 2.4, 4
audit = json.loads((MAPS / 'manifest.json').read_text())
for entry in audit['files']:
    if hashlib.sha256((ROOT / entry['path']).read_bytes()).hexdigest() != entry['sha256']:
        raise ValueError(entry['path'])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 4
scene.cycles.max_bounces = 2
scene.render.threads_mode = 'FIXED'
scene.render.threads = 4
scene.render.resolution_x = len(WORLDS) * SIZE
scene.render.resolution_y = ROWS * SIZE
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.view_settings.view_transform = 'AgX'
scene.world = bpy.data.worlds.new('Ambient')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.22, .25, .31, 1)

angle = math.radians(17)
up = Vector((0, math.sin(angle), math.cos(angle)))
forward = Vector((0, math.cos(angle), -math.sin(angle)))
bpy.ops.object.camera_add(location=-forward * 35)
camera = bpy.context.object
camera.rotation_euler = forward.to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = len(WORLDS) * GAP
scene.camera = camera
bpy.ops.object.light_add(type='SUN')
sun = bpy.context.object
sun.rotation_euler = Vector((.42, 1, -.7)).to_track_quat('-Z', 'Y').to_euler()
sun.data.energy = 3
sun.data.angle = .035

def material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = .76
    def texture(path, data=False):
        node = nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(path), check_existing=True)
        if data:
            node.image.colorspace_settings.name = 'Non-Color'
        return node
    link = mat.node_tree.links.new
    base = name.split('-')[0]
    tex = texture(MAPS / (base + '.jpg'))
    color = tex.outputs['Color']
    if base == 'terra':
        rough = texture(MAPS / 'terra-roughness.png', True)
        link(rough.outputs['Color'], shader.inputs['Roughness'])
        if name in ('terra', 'terra-nuvens'):
            cloud = texture(MAPS / 'terra-clouds.png')
            mix = nodes.new('ShaderNodeMixRGB')
            link(cloud.outputs['Alpha'], mix.inputs[0])
            link(color, mix.inputs[1])
            link(cloud.outputs['Color'], mix.inputs[2])
            color = mix.outputs[0]
        if name in ('terra', 'terra-ar'):
            rim = nodes.new('ShaderNodeLayerWeight')
            mix = nodes.new('ShaderNodeMixRGB')
            link(rim.outputs['Fresnel'], mix.inputs[0])
            link(color, mix.inputs[1])
            mix.inputs[2].default_value = (.08, .35, .76, 1)
            color = mix.outputs[0]
    if base == 'lua':
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Distance'].default_value = .009
        link(texture(DEM, True).outputs['Color'], bump.inputs['Height'])
        link(bump.outputs[0], shader.inputs['Normal'])
    link(color, shader.inputs['Base Color'])
    return mat

def ring_mesh():
    vertices, faces = [], []
    for i in range(160):
        theta = math.tau * i / 160
        for r in (1.11, 2.32):
            vertices.append((r * math.cos(theta), r * math.sin(theta), 0))
        a, b = 2*i, 2*((i+1) % 160)
        faces.append((a, a+1, b+1, b))
    mesh = bpy.data.meshes.new('Radial ring')
    mesh.from_pydata(vertices, [], faces)
    uv = mesh.uv_layers.new()
    for loop in mesh.loops:
        uv.data[loop.index].uv = (float(loop.vertex_index % 2), .5)
    mat = bpy.data.materials.new('Ring opacity')
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(MAPS / 'saturno-rings.png'))
    shader = mat.node_tree.nodes.get('Principled BSDF')
    for socket, dest in [('Color', 'Base Color'), ('Alpha', 'Alpha')]:
        mat.node_tree.links.new(tex.outputs[socket], shader.inputs[dest])
    mesh.materials.append(mat)
    return mesh

rings = ring_mesh()
instances = []
for col, name in enumerate(WORLDS):
    mat = material(name)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48)
    template = bpy.context.object
    template.data.materials.append(mat)
    for face in template.data.polygons:
        face.use_smooth = True
    for row in range(ROWS):
        body = template if row == 0 else template.copy()
        if row:
            scene.collection.objects.link(body)
        body.name = f'{name} - faixa {row + 1}'
        body.location = Vector(((col-(len(WORLDS)-1)/2)*GAP, 0, 0)) + up*((ROWS-1)/2-row)*GAP
        if name == 'saturno':
            body.scale = (.45,)*3
            ring = bpy.data.objects.new('Anéis', rings)
            scene.collection.objects.link(ring)
            ring.location, ring.scale = body.location, body.scale
        instances.append((row, body))

if os.environ.get('SOLAR_SAVE_SCENE') == '1':
    scene.frame_start, scene.frame_end = 1, 9
    for batch in range(9):
        for row, body in instances:
            body.rotation_euler.z = math.radians((batch*ROWS+row)*10)
            body.keyframe_insert(data_path='rotation_euler', index=2, frame=batch + 1)
    scene.frame_set(1)
    scene.render.filepath = '//renders/atlas-'
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(DEM.parent / 'solar-turntable.blend'), compress=True)
else:
    batches = [int(os.environ['SOLAR_BATCH'])] if 'SOLAR_BATCH' in os.environ else range(9)
    for batch in batches:
        for row, body in instances:
            body.rotation_euler.z = math.radians((batch*ROWS+row)*10)
        scene.render.filepath = str(OUT / f'atlas-{batch}.png')
        bpy.ops.render.render(write_still=True)
    (OUT / 'layout.json').write_text(json.dumps(dict(worlds=WORLDS, size=SIZE, rows=ROWS,
        renderer='Cycles', blender=bpy.app.version_string, device=scene.cycles.device,
        threads=scene.render.threads, samples=scene.cycles.samples, stepDegrees=10)))
