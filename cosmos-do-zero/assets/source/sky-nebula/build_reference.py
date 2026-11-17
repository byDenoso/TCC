"""Build the editable Blender reference for the PlayCanvas nebula on /ceu/."""

import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np


def axis_convert(point):
    x, y, z = point
    return Vector((x, -z, y))


def smooth(edge0, edge1, value):
    t = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, amount):
    return (1.0 - amount) * a + amount * b


def lattice(x, y):
    # Integer hashing keeps the same landmarks across GLSL and CPU evaluation.
    x = x.astype(np.int32).view(np.uint32)
    y = y.astype(np.int32).view(np.uint32)
    bits = x * np.uint32(1664525) + y * np.uint32(1013904223)
    bits = (bits ^ (bits >> 16)) * np.uint32(2246822519)
    bits = (bits ^ (bits >> 13)) * np.uint32(3266489917)
    return ((bits ^ (bits >> 16)) & 0xFFFFFF).astype(np.float32) / 16777216


def noise(x, y):
    i, j = np.floor(x), np.floor(y)
    u, v = smooth(0, 1, x - i), smooth(0, 1, y - j)
    return mix(mix(lattice(i, j), lattice(i + 1, j), u),
               mix(lattice(i, j + 1), lattice(i + 1, j + 1), u), v)


def fbm(x, y):
    value = np.zeros_like(x)
    amplitude = 0.5
    for _ in range(5):
        value += amplitude * noise(x, y)
        x, y = (0.8 * x - 0.6 * y) * 2.02 + 3.1, (0.6 * x + 0.8 * y) * 2.02 + 3.1
        amplitude *= 0.5
    return value


def linear_srgb(value):
    return np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4)


def nebula_texture(width, height):
    # The web shader's reference frame fixes the pointer, time and scroll.
    u, v = np.meshgrid((np.arange(width, dtype=np.float32) + .5) / width,
                       (np.arange(height, dtype=np.float32) + .5) / height)
    x, y = (u - .5) * (width / height) * 2.2, (v - .5) * 2.2
    qx, qy = fbm(x, y), fbm(x + 5.2, y + 1.3)
    rx = fbm(x + 3.5 * qx + 1.7, y + 3.5 * qy + 9.2)
    ry = fbm(x + 3.5 * qx + 8.3, y + 3.5 * qy + 2.4)
    f = fbm(x + 3.0 * rx, y + 3.0 * ry)[..., None]
    mx, my = (.62 - .5) * (width / height) * 2.2, (.42 - .5) * 2.2
    glow = np.exp(-2.6 * np.hypot(x - mx, y - my))[..., None]
    rgb = mix(np.array([.018, .025, .075]), np.array([.045, .11, .25]), smooth(.25, .9, f))
    rgb = mix(rgb, np.array([.025, .30, .38]), smooth(.2, .7, f * f) * glow * .55)
    rgb = mix(rgb, np.array([.27, .13, .50]), smooth(.45, 1, f) * .45)
    rgb += np.array([.32, .62, .88]) * smooth(.55, 1, f * f) ** 2 * .65
    rgb += np.array([.20, .48, .65]) * glow * .18
    vignette = 1 - smooth(.25, 1.55, np.hypot((u - .68) * 1.25, v - .55))
    rgba = np.concatenate([linear_srgb(rgb), (.18 + .82 * f) * (.35 + .65 * vignette[..., None]) * .92], axis=2)

    image = bpy.data.images.new('Campo de emissão da nebulosa', width, height, alpha=True, float_buffer=True)
    image.colorspace_settings.name = 'Non-Color'
    image.pixels.foreach_set(rgba.astype(np.float32).ravel())
    image.pack()
    return image


def emissive_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    edges = material.node_tree.links
    output = nodes.new('ShaderNodeOutputMaterial')
    emission = nodes.new('ShaderNodeEmission')
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    blend = nodes.new('ShaderNodeMixShader')
    edges.new(transparent.outputs[0], blend.inputs[1])
    edges.new(emission.outputs[0], blend.inputs[2])
    edges.new(blend.outputs[0], output.inputs[0])
    output.location = (560, 0)
    blend.location = (360, 0)
    emission.location = (100, -80)
    transparent.location = (100, 80)
    return material, nodes, edges, emission, blend


def create_backdrop(camera, width, height, angle):
    distance = 40.0
    half_height = math.tan(angle / 2) * distance
    half_width = half_height * width / height
    bpy.ops.mesh.primitive_plane_add(size=2)
    plane = bpy.context.object
    plane.name = 'Fundo da nebulosa'
    plane.parent = camera
    plane.scale = (half_width, half_height, 1)
    plane.location = (0, 0, -distance)
    material, nodes, edges, emission, blend = emissive_material('Emissão azul e violeta')
    image = nodes.new('ShaderNodeTexImage')
    image.image = nebula_texture(width, height)
    image.location = (-360, 0)
    edges.new(image.outputs['Color'], emission.inputs['Color'])
    edges.new(image.outputs['Alpha'], blend.inputs[0])
    plane.data.materials.append(material)


def create_starfield(camera, height, angle, count, resolution_scale):
    # Seed, world positions and palette match the PlayCanvas reference pose.
    seed = 20261101
    def random():
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        return seed / 2**32

    palette = [(0.75, 0.86, 1), (0.54, 0.77, 1), (0.62, 0.64, 1), (0.91, 0.91, 1)]
    rotation = camera.rotation_quaternion
    right = rotation @ Vector((1, 0, 0))
    up = rotation @ Vector((0, 1, 0))
    forward = rotation @ Vector((0, 0, -1))
    vertices, faces, colors = [], [], []
    for _ in range(count):
        point = axis_convert((random() * 22 - 11, random() * 14 - 7, 3 - random() * 26))
        color = palette[int(random() * len(palette))]
        size = .6 + random() ** 6 * 3.1
        phase = random() * math.tau
        depth = (point - camera.location).dot(forward)
        if depth <= .1:
            continue
        pixels = max(1, size * resolution_scale * 14 / depth)
        half_extent = pixels * math.tan(angle / 2) * depth / height
        offset = len(vertices)
        vertices.extend(point + half_extent * (x * right + y * up) for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)])
        faces.append(tuple(range(offset, offset + 4)))
        brightness = .7 + .3 * math.sin(phase)
        colors.append((*linear_srgb(np.array(color) * brightness), 1))

    mesh = bpy.data.meshes.new('Campo de estrelas')
    mesh.from_pydata(vertices, [], faces)
    uv = mesh.uv_layers.new(name='UVMap')
    colors_attribute = mesh.color_attributes.new(name='Brilho da estrela', type='FLOAT_COLOR', domain='CORNER')
    for face in mesh.polygons:
        for loop, coordinate in zip(face.loop_indices, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            uv.data[loop].uv = coordinate
            colors_attribute.data[loop].color = colors[face.index]

    stars = bpy.data.objects.new('Estrelas em profundidade · distribuição sintética', mesh)
    bpy.context.scene.collection.objects.link(stars)
    material, nodes, edges, emission, blend = emissive_material('Estrelas sintéticas')
    color = nodes.new('ShaderNodeVertexColor')
    color.layer_name = colors_attribute.name
    uv_node = nodes.new('ShaderNodeTexCoord')
    distance = nodes.new('ShaderNodeVectorMath')
    distance.operation = 'DISTANCE'
    distance.inputs[1].default_value = (.5, .5, 0)
    profile = nodes.new('ShaderNodeMapRange')
    profile.interpolation_type = 'SMOOTHSTEP'
    profile.inputs['From Max'].default_value = .5
    profile.inputs['To Min'].default_value = 1
    profile.inputs['To Max'].default_value = 0
    edges.new(color.outputs['Color'], emission.inputs['Color'])
    edges.new(uv_node.outputs['UV'], distance.inputs[0])
    edges.new(distance.outputs['Value'], profile.inputs['Value'])
    edges.new(profile.outputs['Result'], blend.inputs[0])
    mesh.materials.append(material)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--width', type=int, required=True)
    cli.add_argument('--height', type=int, required=True)
    cli.add_argument('--mobile', action='store_true')
    args = cli.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.output.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'Standard'
    scene.world = bpy.data.worlds.new('Fundo transparente')

    angle = math.radians(55)
    bpy.ops.object.camera_add(location=axis_convert((.06, .028, 6)))
    camera = bpy.context.object
    camera.name = 'Câmera da referência'
    camera.data.sensor_fit = 'VERTICAL'
    camera.data.angle = angle
    camera.rotation_mode = 'QUATERNION'
    camera.rotation_quaternion = (axis_convert((0, 0, -8)) - camera.location).to_track_quat('-Z', 'Y')
    scene.camera = camera

    create_backdrop(camera, args.width, args.height, angle)
    create_starfield(camera, args.height, angle, 1400 if args.mobile else 3200, .5 if args.mobile else .65)
    bpy.context.preferences.filepaths.save_version = 0
    scene.render.filepath = str(args.output / 'nebulosa-blender.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output / 'nebulosa.blend'))
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
