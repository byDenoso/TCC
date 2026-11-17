"""Blender 4.3+. Run: blender -b -P assets/source/atlas-studies/build.py"""
from math import cos, sin, tau
from pathlib import Path

import bpy

output = Path(__file__).resolve().parents[3] / "public/models/atlas-studies"
output.mkdir(parents=True, exist_ok=True)


def material(name, color, metallic=0, emission=0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    shader = m.node_tree.nodes["Principled BSDF"]
    for field, value in [("Base Color", (*color, 1)), ("Metallic", metallic),
                         ("Roughness", .42), ("Emission Color", (*color, 1)),
                         ("Emission Strength", emission)]:
        shader.inputs[field].default_value = value
    return m


def bind(obj, name, mat):
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def box(name, pos, dims, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bind(bpy.context.object, name, mat)
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def sphere(name, pos, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=36, ring_count=18, radius=radius, location=pos)
    obj = bind(bpy.context.object, name, mat)
    for face in obj.data.polygons:
        face.use_smooth = True


def line(name, points, mat, radius=.022, close=False, origin=(0, 0, 0)):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 1
    poly = curve.splines.new("POLY")
    poly.points.add(len(points)-1)
    for vertex, xyz in zip(poly.points, points):
        vertex.co = (*xyz, 1)
    poly.use_cyclic_u = close
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj.location = origin
    bind(obj, name, mat)


def circle(name, mat, radius, depth, pos):
    line(name, [(radius*cos(i*tau/96), radius*sin(i*tau/96), 0) for i in range(96)],
         mat, depth, True, pos)


for key in ["redshift", "lens", "star", "orbit", "air"]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ink = material("Ardósia", (.025, .048, .055), .14)
    brass = material("Latão", (.55, .35, .15), .4, .12)
    amber = material("Emissão", (.98, .38, .09), .06, .5)
    cyan = material("Referência", (.22, .7, .78), .15, .35)
    bone = material("Cerâmica", (.76, .78, .68), .14)
    box("Mesa", (0, 0, -.10), (7, 4.8, .18), ink)
    for y in [-2.26, 2.26]:
        line("Régua", [(-3.35, y, .012), (3.35, y, .012)], brass, .012)
        for n in range(-12, 13):
            size = .15 if n % 4 == 0 else .07
            line("Divisão", [(n/4, y, .014), (n/4, y+size*(1 if y < 0 else -1), .014)], brass, .009)
    if key == "redshift":
        # Two wave crests per unit length. Deformation changes wavelength in X only.
        path = [(i/64, .42*sin(i/64*tau), .03) for i in range(129)]
        line("Reference", path, cyan, .04, origin=(-3, 1.0, .04))
        line("Measure", path, amber, .048, origin=(-3, -.8, .04))
    elif key == "lens":
        circle("Reference", cyan, .95, .018, (0, 0, .025))
        circle("Measure", amber, .95, .052, (0, 0, .09))
        sphere("Lente", (0, 0, .12), .18, bone)
    elif key == "star":
        sphere("Sol de referência", (-1.55, 0, .65), .62, bone)
        sphere("Measure", (1.25, 0, .65), .62, amber)
    elif key == "orbit":
        circle("Reference", cyan, .94, .018, (0, 0, .025))
        circle("Measure", amber, .94, .025, (0, 0, .075))
        sphere("Sol", (0, 0, .22), .20, amber)
        sphere("Planet", (.94, 0, .14), .09, cyan)
    elif key == "air":
        # Two open manometer scales. Moving floor-anchored bar height is P/P0.
        for x in [-1.1, 1.1]:
            box("Suporte", (x, 0, .11), (.90, .82, .22), brass)
            for i in range(6):
                box("Graduação", (x+.56, 0, .22+i*.38), (.17, .14, .025), bone)
        box("Referência ao nível do mar", (-1.1, 0, 1.17), (.65, .58, 1.9), cyan)
        box("Measure", (1.1, 0, 1.17), (.65, .58, 1.9), amber)
    # Static meshes sharing one material become a single draw call.
    for mat in [ink, brass, amber, cyan, bone]:
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH'
                  and o.name not in ('Measure', 'Planet') and o.active_material == mat]
        if len(meshes) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in meshes:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = meshes[0]
            bpy.ops.object.join()
            bpy.context.object.name = mat.name
    bpy.ops.export_scene.gltf(filepath=str(output / (key+".glb")), export_format="GLB",
                              export_texcoords=False, export_cameras=False, export_lights=False)
