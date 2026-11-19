"""Render mineral and ice-rich aggregates. Run from Blender with -b -t 3 -P."""
from pathlib import Path
import math
import bpy
from mathutils import Vector, noise

here = Path(__file__).resolve().parent
out = here.parents[2] / 'public/renders/formation'
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = 384
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'WEBP'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.quality = 90
world = bpy.data.worlds.new('Diffuse sky')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.24,.33,.48,1)
world.node_tree.nodes['Background'].inputs[1].default_value = .28
scene.world = world

def aim(obj):
    obj.rotation_euler = (-obj.location).to_track_quat('-Z','Y').to_euler()

bpy.ops.object.camera_add(location=(0,-5,2.35))
camera = bpy.context.object
aim(camera)
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2.85
scene.camera = camera
for position, energy, color, size in [((-3,-3.5,4.5),430,(1,.81,.61),3),((3,1.6,2.5),270,(.68,.81,1),2.2)]:
    bpy.ops.object.light_add(type='AREA', location=position)
    lamp=bpy.context.object
    lamp.data.energy, lamp.data.color, lamp.data.shape, lamp.data.size = energy,color,'DISK',size
    aim(lamp)

for n,kind in enumerate(('mineral','ice')):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1)
    stone=bpy.context.object
    stone.name=kind
    for pt in stone.data.vertices:
        v=pt.co.normalized()
        shift=Vector((4.32*n,1.2,7.41))
        k=.19*noise.noise(v*2.3+shift)+.1*noise.noise(v*4.8+shift)+.057*noise.noise(v*11.4+shift)+.021*noise.noise(v*40+shift)
        pt.co=v*(1+k)
    stone.scale=(1.03,.95,.75+n*.10)
    stone.rotation_euler=(.15,-.29+n*.5,.2+n)
    mat=bpy.data.materials.new(kind)
    mat.use_nodes=True
    nodes,link=mat.node_tree.nodes,mat.node_tree.links.new
    bs=nodes['Principled BSDF']
    bs.inputs['Roughness'].default_value=.75 if not n else .31
    bs.inputs['Transmission Weight'].default_value=.08 if n else 0
    coord=nodes.new('ShaderNodeTexCoord')
    texture=nodes.new('ShaderNodeTexNoise')
    texture.inputs['Scale'].default_value=7
    texture.inputs['Detail'].default_value=7
    texture.inputs['Roughness'].default_value=.72
    link(coord.outputs['Generated'],texture.inputs['Vector'])
    ramp=nodes.new('ShaderNodeValToRGB').color_ramp
    ramp.elements[0].position=.27
    ramp.elements[0].color=(.035,.023,.021,1) if not n else (.031,.09,.13,1)
    ramp.elements[1].position=.74
    ramp.elements[1].color=(.43,.31,.18,1) if not n else (.76,.89,.91,1)
    link(texture.outputs['Fac'],nodes.get('Color Ramp').inputs[0])
    link(nodes.get('Color Ramp').outputs[0],bs.inputs['Base Color'])
    grain=nodes.new('ShaderNodeTexNoise')
    grain.inputs['Scale'].default_value=114
    grain.inputs['Detail'].default_value=3
    link(coord.outputs['Generated'],grain.inputs['Vector'])
    fine=nodes.new('ShaderNodeBump')
    fine.inputs['Strength'].default_value=.52
    fine.inputs['Distance'].default_value=.023
    link(grain.outputs['Fac'],fine.inputs['Height'])
    coarse=nodes.new('ShaderNodeBump')
    coarse.inputs['Strength'].default_value=.55
    coarse.inputs['Distance'].default_value=.115
    link(texture.outputs['Fac'],coarse.inputs['Height'])
    link(fine.outputs['Normal'],coarse.inputs['Normal'])
    link(coarse.outputs['Normal'],bs.inputs['Normal'])
    stone.data.materials.append(mat)
    scene.render.filepath=str(out/(kind+'.webp'))
    bpy.ops.render.render(write_still=True)
    stone.hide_render=True
bpy.data.objects['mineral'].hide_render=False
bpy.ops.wm.save_as_mainfile(filepath=str(here/'aggregates.blend'),compress=True)

