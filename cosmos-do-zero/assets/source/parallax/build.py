"""Run with Blender 4.3+: blender -b -P assets/source/parallax/build.py.
The compressed tabletop distances are illustrative. Only the separate angular ruler
reports astrometric measurements. The model represents the default 4 pc setting.
"""
import math
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[3]
out = root / "public/models/parallax"
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.world = bpy.data.worlds.new("Studio")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.12, .16, .22, 1)
scene.world.node_tree.nodes["Background"].inputs[1].default_value = .32


def material(name, color, metal=0, rough=.45, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = rough
    shader.inputs["Emission Color"].default_value = (*color, 1)
    shader.inputs["Emission Strength"].default_value = emission
    return mat


brass = material("Laiton satiné", (.52, .30, .112), .64, .34)
ink = material("Antracite", (.036, .069, .084), .38, .38)
lacquer = material("Esmalte oceano", (.046, .163, .182), .28, .39)
ivory = material("Marfim", (.92, .78, .53), .15, .43, .15)
copper = material("Linha A · cobre", (1, .45, .16), .05, .45, .82)
blue = material("Linha B · gelo", (.28, .80, .95), .05, .40, .94)
star = material("Alvo · porcelana", (.78, .94, 1), .14, .26, 1.4)
earth = material("Terra · NASA BMNG", (.4, .4, .4), .04, .51)
nodes = earth.node_tree.nodes
texture = nodes.new("ShaderNodeTexImage")
tex = bpy.data.images.load(str(root / "assets/source/observed/earth-bmng-200407.jpg"))
tex.scale(512, 256)
tex.filepath_raw = str(Path(tempfile.gettempdir()) / "cosmos_atlas_parallax_earth.jpg")
tex.file_format = "JPEG"
tex.save()
tex.pack()
texture.image = tex
earth.node_tree.links.new(texture.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])


def assign(obj, name, mat, smooth=False):
    obj.name = name
    obj.data.materials.append(mat)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj


def cylinder(name, at, radius, depth, mat, segments=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=radius, depth=depth, location=at)
    obj = assign(bpy.context.object, name, mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def rod(name, start, end, radius, mat, sides=10):
    a, b = Vector(start), Vector(end)
    obj = cylinder(name, (a+b)/2, radius, (b-a).length, mat, sides)
    obj.rotation_euler = (b-a).to_track_quat("Z", "Y").to_euler()
    return obj


def sphere(name, at, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radius, location=at)
    return assign(bpy.context.object, name, mat, True)


def ring(name, at, radius, section, mat, tilt=0):
    bpy.ops.mesh.primitive_torus_add(major_segments=72, minor_segments=6, location=at,
                                    major_radius=radius, minor_radius=section)
    obj = assign(bpy.context.object, name, mat, True)
    obj.rotation_euler.x = tilt
    return obj


def letter(label, x, y, size):
    bpy.ops.object.text_add(location=(x, y, .201))
    obj = bpy.context.object
    obj.data.body = label
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.materials.append(ivory)
    bpy.ops.object.convert(target="MESH")


oy = -1.16
cylinder("Pé circular", (0, oy, -.10), 2.30, .16, ink, 96)
cylinder("Rebordo", (0, oy, .007), 2.29, .09, brass, 96)
cylinder("Mesa azimutal", (0, oy, .116), 2.25, .15, lacquer, 96)
for radius in (2.03, 2.18, 1.53, 1.47):
    ring("Círculo graduado", (0, oy, .2), radius, .009, brass)
for degree in range(0, 360, 3):
    angle = math.radians(degree)
    length = .15 if degree % 30 == 0 else .09 if degree % 15 == 0 else .047
    def tick(r):
        return (r*math.cos(angle), oy+r*math.sin(angle), .199)
    rod("Graduação", tick(2.17-length), tick(2.17), .012 if degree % 30 == 0 else .0065, ivory, 5)
letter("A", -1.5, oy-.51, .19)
letter("B", 1.5, oy-.51, .19)
letter("2  U A", 0, oy-.95, .17)
for x, color, name in [(-1.5, copper, "A"), (1.5, blue, "B")]:
    cylinder("Pé da Terra "+name, (x, oy, .24), .19, .085, brass)
    rod("Eixo "+name, (x,oy,.26), (x,oy,.66), .042, brass)
    globe = sphere("Terra "+name, (x,oy,.87), .24, earth)
    globe.rotation_euler = (.14,.24,.8)
    ring("Moldura "+name, (x,oy,.87), .295, .016, color, math.radians(73))
sphere("Sol", (0,oy,.69), .235, ivory)
cylinder("Eixo do Sol",(0,oy,.38),.055,.36,brass)
rod("Base A–B",(-1.49,oy,.34),(1.49,oy,.34),.022,brass)
# A linear slide makes the compressed movement of the target explicit.
for x in (-.17,.17):
    rod("Trilho",(x,oy+.28,.34),(x,4.0,.34),.028,brass)
for y in (.90, 3.80):
    cylinder("Pé do trilho",(0,y,.08),.29,.22,ink)
    cylinder("Pino",(0,y,.23),.11,.17,brass)
for i in range(10):
    y=.30+.32*(i+1)
    rod("Divisão de distância",(-.16,y,.34),(.16,y,.34),.013,ivory,6)

# Group static meshes by material, reducing exchanges with the GPU.
def join(items, name):
    bpy.ops.object.select_all(action="DESELECT")
    for item in items:
        item.select_set(True)
    bpy.context.view_layer.objects.active = items[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name=name
    return obj


groups = {}
for obj in list(scene.objects):
    if obj.type == "MESH":
        groups.setdefault(obj.data.materials[0].name, []).append(obj)
for name, items in groups.items():
    join(items,name)
base = set(scene.objects)
y0=.30+.32*4
cylinder("Carro",(0,y0,.39),.19,.13,brass)
rod("Eixo do alvo",(0,y0,.42),(0,y0,.91),.038,brass)
sphere("Estrela",(0,y0,1.18),.185,star)
ring("Mira",(0,y0,1.18),.32,.014,brass,math.pi/2)
ring("Meridiano",(0,y0,1.18),.255,.010,blue,math.pi/3)
target=join(list(obj for obj in scene.objects if obj not in base),"Target")
bpy.context.scene.cursor.location=(0,y0,1.18)
bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=str(out/"instrument.glb"), export_format="GLB",
                         use_selection=True, export_image_format="JPEG", export_extras=False,
                         export_yup=True, export_cameras=False, export_lights=False)
# Poster lighting is authored as a still life on dark charcoal; runtime uses key/fill/rim.
for x, mat in [(-1.5,copper),(1.5,blue)]:
    rod("Linha de visada",(x,oy,.87),(0,y0,1.18),.013,mat)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.19))
assign(bpy.context.object,"Mesa de exposição",material("Fundo",(.012,.026,.034),.16,.60))
def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z","Y").to_euler()
for name, pos, energy, tint, size in [
    ("Janela",(-3,-3,7),1400,(1,.85,.65),5.5),
    ("Recorte",(1,5,4),1700,(.38,.69,1),4.0),
    ("Rebatedor",(5,-1,2),550,(.95,.80,.62),3.5)]:
    bpy.ops.object.light_add(type="AREA",location=pos)
    obj=bpy.context.object
    obj.name=name
    obj.data.energy=energy
    obj.data.color=tint
    obj.data.shape="DISK"
    obj.data.size=size
    aim(obj,(0,0,0))
bpy.ops.object.camera_add(location=(3.55,-7.75,6.65))
scene.camera=bpy.context.object
aim(scene.camera,(0,.25,.53))
scene.camera.data.type="ORTHO"
scene.camera.data.ortho_scale=8.7
scene.render.engine="CYCLES"
scene.cycles.samples=28
scene.cycles.use_denoising=False
scene.render.resolution_x=1080
scene.render.resolution_y=672
scene.render.resolution_percentage=100
scene.render.image_settings.file_format="WEBP"
scene.render.image_settings.quality=88
scene.render.filepath=str(out/"instrument.webp")
bpy.ops.render.render(write_still=True)
