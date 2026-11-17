"""Build the packed Blender reference and isolated web/Unity GLB for Saturn."""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SOURCE = Path(__file__).resolve().parent
SITE = SOURCE.parents[2]
MAPS = SOURCE.parent / 'solar-materials'
PUBLIC = SITE / 'public' / 'models' / 'saturn'
SETTINGS = json.loads((PUBLIC / 'scene.json').read_text(encoding='utf-8'))
GEO = SETTINGS['geometry']
CAMERA = SETTINGS['camera']


def blender_axes(web_vector):
    x, y, z = web_vector
    return Vector((x, -z, y))


def material(name, texture_name=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    surface = nodes.get('Principled BSDF')
    surface.inputs['Roughness'].default_value = 0.92
    surface.inputs['Specular IOR Level'].default_value = 0.15
    if texture_name:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(MAPS / texture_name), check_existing=True)
        tex.image.pack()
        tex.location = (-350, 20)
        mat.node_tree.links.new(tex.outputs['Color'], surface.inputs['Base Color'])
        return mat, tex
    return mat, None


def sphere(name, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=radius)
    obj = bpy.context.object
    obj.name = name
    obj.scale.z = GEO['polarRadius'] / GEO['equatorRadius']
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for face in obj.data.polygons:
        face.use_smooth = True
    obj.data.materials.append(mat)
    return obj


def annulus(mat):
    count = 256
    inner = GEO['ringInnerRadius']
    outer = GEO['ringOuterRadius']
    points = [
        (radius * math.cos(i * math.tau / count), radius * math.sin(i * math.tau / count), 0)
        for radius in (inner, outer)
        for i in range(count)
    ]
    faces = [(i, count + i, count + (i + 1) % count, (i + 1) % count) for i in range(count)]
    mesh = bpy.data.meshes.new('Annulus · radial texture coordinates')
    mesh.from_pydata(points, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:
        uv.data[loop.index].uv = (float(loop.vertex_index >= count), 0.5)
    obj = bpy.data.objects.new(SETTINGS['ringsNode'], mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def add_limb(mat):
    nodes = mat.node_tree.nodes
    link = mat.node_tree.links.new
    nodes.remove(nodes.get('Principled BSDF'))
    layer = nodes.new('ShaderNodeLayerWeight')
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 1
    ramp.color_ramp.elements[1].color = (0.22, 0.22, 0.22, 1)
    geom = nodes.new('ShaderNodeNewGeometry')
    dot = nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.inputs[1].default_value = blender_axes(SETTINGS['sunDirection']).normalized()
    sun = nodes.new('ShaderNodeMapRange')
    sun.inputs['From Min'].default_value = -0.32
    sun.inputs['From Max'].default_value = 1
    sun.inputs['To Min'].default_value = 0.14
    limb = nodes.new('ShaderNodeMath')
    limb.operation = 'MULTIPLY'
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    scatter = nodes.new('ShaderNodeEmission')
    scatter.inputs['Color'].default_value = (0.66, 0.38, 0.22, 1)
    mix = nodes.new('ShaderNodeMixShader')
    link(layer.outputs['Facing'], ramp.inputs['Fac'])
    link(geom.outputs['Normal'], dot.inputs[0])
    link(dot.outputs['Value'], sun.inputs['Value'])
    link(ramp.outputs['Color'], limb.inputs[0])
    link(sun.outputs['Result'], limb.inputs[1])
    link(limb.outputs[0], mix.inputs[0])
    link(transparent.outputs[0], mix.inputs[1])
    link(scatter.outputs[0], mix.inputs[2])
    link(mix.outputs[0], nodes.get('Material Output').inputs['Surface'])


def orbit_camera(cam, degrees):
    angle = math.radians(degrees)
    cam.location = blender_axes((0, CAMERA['distance'] * math.sin(angle), CAMERA['distance'] * math.cos(angle)))
    cam.rotation_euler = (-cam.location).to_track_quat('-Z', 'Y').to_euler()


def srgb(channel):
    return channel / 12.92 if channel < 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def background(scene):
    world = bpy.data.worlds.new('Saturno · ambiente e fundo')
    world.use_nodes = True
    nodes = world.node_tree.nodes
    link = world.node_tree.links.new
    ambient = nodes.get('Background')
    ambient.inputs['Color'].default_value = (0.43, 0.46, 0.57, 1)
    ambient.inputs['Strength'].default_value = 0.09
    ray = nodes.new('ShaderNodeLightPath')
    backdrop = nodes.new('ShaderNodeBackground')
    hex_color = SETTINGS['background'].removeprefix('#')
    backdrop.inputs['Color'].default_value = (*[srgb(int(hex_color[i:i + 2], 16) / 255) for i in (0, 2, 4)], 1)
    mix = nodes.new('ShaderNodeMixShader')
    link(ray.outputs['Is Camera Ray'], mix.inputs[0])
    link(ambient.outputs[0], mix.inputs[1])
    link(backdrop.outputs[0], mix.inputs[2])
    link(mix.outputs[0], nodes.get('World Output').inputs['Surface'])
    scene.world = world


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'Saturno · plano dos anéis'
    globe, _ = material('Saturno · faixas atmosféricas', 'saturno.jpg')
    ring, profile = material('Saturno · densidade radial', 'saturno-rings.png')
    ring.use_backface_culling = False
    ring.surface_render_method = 'BLENDED'
    ring.node_tree.links.new(profile.outputs['Alpha'], ring.node_tree.nodes.get('Principled BSDF').inputs['Alpha'])
    atmosphere, _ = material('Saturno · limbo')
    atmosphere.surface_render_method = 'BLENDED'
    atmosphere.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value = 0.03
    sphere(SETTINGS['globeNode'], GEO['equatorRadius'], globe)
    annulus(ring)
    shell = sphere(SETTINGS['atmosphereNode'], GEO['atmosphereRadius'], atmosphere)

    bpy.ops.export_scene.gltf(filepath=str(PUBLIC / SETTINGS['model']), export_format='GLB',
                              export_yup=True, export_cameras=False, export_lights=False)

    add_limb(atmosphere)
    shell.visible_shadow = False
    shell.visible_diffuse = False
    shell.visible_glossy = False
    shell.visible_transmission = False
    background(scene)
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 3))
    sun = bpy.context.object
    sun.name = 'Sol · posição fixa'
    sun.rotation_euler = (-blender_axes(SETTINGS['sunDirection'])).to_track_quat('-Z', 'Y').to_euler()
    sun.data.energy = 3.05
    sun.data.angle = math.radians(0.65)

    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = 'Câmera · vista ortográfica'
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = CAMERA['frameWidth']
    scene.camera = camera
    orbit_camera(camera, CAMERA['openAngle'])
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 8
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.view_settings.view_transform = 'Standard'
    scene.render.filepath = '//blender-open.png'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / 'saturn.blend'))

    if '--render' in sys.argv:
        for tag, angle in (('open', CAMERA['openAngle']), ('edge', CAMERA['edgeAngle'])):
            orbit_camera(camera, angle)
            scene.render.filepath = str(SOURCE / f'blender-{tag}.png')
            bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    build()
