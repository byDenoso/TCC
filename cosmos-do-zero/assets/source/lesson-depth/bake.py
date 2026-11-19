"""Blender 5.x: blender -b -t 4 -P bake.py -- <output directory>."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector

output = Path(sys.argv[-1])
output.mkdir(parents=True, exist_ok=True)

def material(name, color, texture=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    surface = nodes.get('Principled BSDF')
    surface.inputs['Base Color'].default_value = (*color, 1)
    surface.inputs['Roughness'].default_value = .38
    if texture:
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 32
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = .25
        ramp.color_ramp.elements[0].color = tuple(v*.22 for v in color)+(1,)
        ramp.color_ramp.elements[1].position = .76
        ramp.color_ramp.elements[1].color = (*color, 1)
        mat.node_tree.links.new(noise.outputs['Fac'], ramp.inputs[0])
        mat.node_tree.links.new(ramp.outputs[0], surface.inputs['Base Color'])
        mat.node_tree.links.new(ramp.outputs[0], surface.inputs['Emission Color'])
        surface.inputs['Emission Strength'].default_value = .7
    if name == 'star':
        # Granulation and limb darkening on a luminous photosphere.
        cells = nodes.new('ShaderNodeTexVoronoi')
        cells.inputs['Scale'].default_value = 96
        granules = nodes.new('ShaderNodeValToRGB')
        granules.color_ramp.elements[0].color = (1.0,.83,.45,1)
        granules.color_ramp.elements[1].color = (.38,.13,.035,1)
        mat.node_tree.links.new(cells.outputs['Distance'], granules.inputs[0])
        normal = nodes.new('ShaderNodeNewGeometry')
        facing = nodes.new('ShaderNodeVectorMath')
        facing.operation = 'DOT_PRODUCT'
        mat.node_tree.links.new(normal.outputs['Incoming'], facing.inputs[0])
        mat.node_tree.links.new(normal.outputs['Normal'], facing.inputs[1])
        limb = nodes.new('ShaderNodeMapRange')
        limb.inputs['To Min'].default_value = .32
        limb.inputs['To Max'].default_value = 1.65
        mat.node_tree.links.new(facing.outputs['Value'], limb.inputs['Value'])
        emission = nodes.new('ShaderNodeEmission')
        mat.node_tree.links.new(granules.outputs[0], emission.inputs['Color'])
        mat.node_tree.links.new(limb.outputs['Result'], emission.inputs['Strength'])
        mat.node_tree.links.new(emission.outputs[0], nodes.get('Material Output').inputs['Surface'])
    return mat

def sphere(at, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=at)
    obj = bpy.context.object
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj

for name in ['star', 'proton', 'helium', 'electron', 'disk']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = 320
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'WEBP'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.quality = 93
    bpy.ops.object.camera_add(location=(0,-5,1.8))
    camera = bpy.context.object
    camera.rotation_euler = (-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 2.15
    scene.camera = camera
    for at, energy in [((-3,-4,5),460), ((2,2,1),280)]:
        bpy.ops.object.light_add(type='AREA',location=at)
        lamp=bpy.context.object
        lamp.rotation_euler=(-lamp.location).to_track_quat('-Z','Y').to_euler()
        lamp.data.energy=energy
        lamp.data.shape='DISK'
        lamp.data.size=3
    if name=='helium':
        for pos, color in [((-.33,-.23,.27),(1,.27,.06)),((.34,.22,.28),(.36,.45,.53)),((-.3,.33,-.26),(.36,.45,.53)),((.32,-.28,-.25),(1,.27,.06))]:
            sphere(pos,.53,material('Nucleon',color))
    elif name=='disk':
        sphere((0,0,0),.29,material('Centro',(.002,.002,.003)))
        for i in range(16):
            r=.36+i*.04
            bpy.ops.mesh.primitive_torus_add(major_radius=r,minor_radius=.026,major_segments=96,minor_segments=12)
            bpy.context.object.data.materials.append(material('Anel',(1,.55-.023*i,.10),True))
    else:
        color={'proton':(1,.26,.05),'electron':(.15,.55,1),'star':(.96,.83,.67)}[name]
        sphere((0,0,0),1,material(name,color,name=='star'))
    scene.render.filepath = str(output / (name+'.webp'))
    bpy.ops.render.render(write_still=True)
