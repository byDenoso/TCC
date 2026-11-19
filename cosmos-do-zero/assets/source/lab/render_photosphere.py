"""Blender -b -t 3 --python-exit-code 1 -P assets/source/lab/render_photosphere.py"""
from pathlib import Path

import bpy

root = Path(__file__).resolve().parents[3]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.render.resolution_x = scene.render.resolution_y = 384
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'WEBP'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.quality = 94

bpy.ops.object.camera_add(location=(0, 0, 4))
camera = bpy.context.object
camera.rotation_euler = (0, 0, 0)
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2.12
scene.camera = camera
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64)
star = bpy.context.object
bpy.ops.object.shade_smooth()
mat = bpy.data.materials.new('Granulação e escurecimento de bordo ilustrativos')
mat.use_nodes = True
star.data.materials.append(mat)
nodes, links = mat.node_tree.nodes, mat.node_tree.links
grain = nodes.new('ShaderNodeTexImage')
grain.image = bpy.data.images.load(str(root / 'public/models/stellar/granulation.png'))
grain.image.colorspace_settings.name = 'Non-Color'
noise = nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 9
noise.inputs['Detail'].default_value = 4
mix = nodes.new('ShaderNodeMixRGB')
mix.inputs[0].default_value = .37
links.new(grain.outputs['Color'], mix.inputs[1])
links.new(noise.outputs['Fac'], mix.inputs[2])
color = nodes.new('ShaderNodeValToRGB')
stops = color.color_ramp.elements
stops[0].position, stops[0].color = .30, (.19,.068,.018,1)
stops[1].position, stops[1].color = .92, (1,.86,.52,1)
stops.new(.72).color = (.80,.43,.16,1)
links.new(mix.outputs[0], color.inputs[0])
facing = nodes.new('ShaderNodeLayerWeight')
limb = nodes.new('ShaderNodeValToRGB')
limb.color_ramp.elements[0].color = (1,1,1,1)
limb.color_ramp.elements[1].color = (.30,.30,.30,1)
links.new(facing.outputs['Facing'],limb.inputs[0])
emission = nodes.new('ShaderNodeEmission')
links.new(color.outputs[0], emission.inputs['Color'])
links.new(limb.outputs[0], emission.inputs['Strength'])
links.new(emission.outputs[0],nodes.get('Material Output').inputs['Surface'])
scene.view_settings.view_transform = 'Standard'
scene.render.filepath = str(root / 'public/models/lab/photosphere.webp')
bpy.ops.render.render(write_still=True)
