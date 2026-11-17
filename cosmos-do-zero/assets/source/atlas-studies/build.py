"""Run plates.py first, then blender -b -P assets/source/atlas-studies/build.py.
Use COSMOS_STUDY_MAPS to override the intermediate map directory.
"""
from math import cos, sin, tau, radians
from pathlib import Path

import bpy
import os

maps = Path(os.environ.get("COSMOS_STUDY_MAPS", "/tmp/cosmos-study-maps"))

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
    if min(dims) > .08:
        bevel=obj.modifiers.new("Arestas torneadas", "BEVEL"); bevel.width=min(dims)*.12; bevel.segments=3
        bpy.ops.object.modifier_apply(modifier=bevel.name)
    return obj


def sphere(name, pos, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=pos)
    obj = bind(bpy.context.object, name, mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


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


def image_material(name,path,emission,transparent=False):
    mat=material(name,(1,1,1),0,emission)
    nodes=mat.node_tree.nodes
    surface=nodes["Principled BSDF"]
    image=nodes.new("ShaderNodeTexImage")
    image.image=bpy.data.images.load(str(maps/path))
    links=mat.node_tree.links
    links.new(image.outputs["Color"],surface.inputs["Base Color"])
    if emission:
        links.new(image.outputs["Color"],surface.inputs["Emission Color"])
    if transparent:
        links.new(image.outputs["Alpha"],surface.inputs["Alpha"])
        mat.surface_render_method='BLENDED'
    surface.inputs["Roughness"].default_value=.87
    surface.inputs["Specular IOR Level"].default_value=.12
    return mat

def plane(name,pos,size,mat):
    bpy.ops.mesh.primitive_plane_add(size=size,location=pos)
    return bind(bpy.context.object,name,mat)

def cylinder(name,pos,radius,depth,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=radius,depth=depth,location=pos)
    return bind(bpy.context.object,name,mat)

for key in ["redshift","lens","star","orbit","air"]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    graphite=material("Anodização grafite",(.035,.058,.076),.24)
    brass=material("Bronze escovado",(.55,.34,.17),.32,.04)
    amber=material("Sinal âmbar",(.97,.39,.085),.08,.60)
    cyan=material("Calibração em ciano",(.14,.62,.81),.17,.35)
    silver=material("Escala gravada",(.56,.65,.69),.14,.16)
    static=[graphite,brass,amber,cyan,silver]
    if key=="redshift":
        for y,mat in [(1,cyan),(-1,amber)]:
            box("Trilho polido",(0,y,-.13),(6.9,1.36,.18),graphite)
            for off in [-.68,.68]:
                line("Perfil do trilho",[(-3.43,y+off,-.015),(3.43,y+off,-.015)],brass,.012)
            for q in range(25):
                xx=-3+q*.25
                line("Graduação",[(xx,y-.65,0),(xx,y-.65+(.15 if q%4==0 else .06),0)],silver,.011)
            box("Emissor",(-3.22,y,.085),(.16,.97,.28),graphite)
            box("Fenda luminosa",(-3.12,y,.086),(.021,.65,.09),mat)
        path=[(i/64,.41*sin(i*tau/64),.13) for i in range(129)]
        line("Reference",path,cyan,.027,origin=(-3,1,.03))
        line("Measure",path,amber,.040,origin=(-3,-1,.03))
    elif key=="lens":
        center=image_material("Luz da galáxia-lente","lens-galaxy.png",.68,True)
        ring=image_material("Imagem anular","einstein.png",.92,True)
        plane("Galáxia-lente",(0,0,.012),3.1,center)
        plane("Measure",(0,0,.06),.95*2.8,ring)
        for k in range(32):
            arc=[(.95*cos((k+i/14*.52)*tau/32),.95*sin((k+i/14*.52)*tau/32),.095) for i in range(15)]
            line("Referência angular",arc,brass,.009)
    elif key=="star" or key=="orbit":
        surface=image_material("Granulação da fotosfera","photosphere.jpg",.56)
        corona=image_material("Emissão coronal","corona.png",.75,True)
        if key=="star":
            sphere("Sol de referência",(-1.63,0,0),.72,surface)
            sphere("Measure",(1.25,0,0),.72,surface)
            for label,xx in [("HaloRef",-1.63),("HaloMeasure",1.25)]:
                plane(label,(xx,0,0),.72*2.8,corona).rotation_euler.x=radians(88)
        else:
            circle("Measure",amber,1.24,.014,(0,0,-.03))
            for k in range(48):
                arc=[(1.24*cos((k+i/6*.53)*tau/48),1.24*sin((k+i/6*.53)*tau/48),0) for i in range(7)]
                line("Órbita de referência",arc,cyan,.009)
            sphere("Sol",(0,0,0),.39,surface)
            plane("HaloRef",(0,0,0),.39*2.8,corona).rotation_euler.x=radians(45)
            globe=image_material("Terra NASA Blue Marble","earth.jpg",0)
            sphere("Planet",(1.24,0,0),.20,globe)
    else:
        for xx,mat,name in [(-1.15,cyan,"Reference"),(1.15,amber,"Measure")]:
            cylinder("Base",(xx,0,.075),.48,.15,graphite)
            cylinder("Aro de bronze",(xx,0,.14),.45,.045,brass)
            cylinder(name,(xx,0,1.15),.325,2,mat)
            for k in range(11):
                h=.15+k*.2
                for side in [-1,1]:
                    line("Graduação",[(xx+side*.41,-.005,h),(xx+side*(.63 if k%5==0 else .51),-.005,h)],silver,.011)
            for side in [-1,1]:
                line("Montante",[(xx+side*.42,0,.12),(xx+side*.42,0,2.25)],brass,.015)
            circle("Aro superior",silver,.42,.022,(xx,0,2.18))
    for mat in static:
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'
                and o.name not in ("Measure","Planet") and o.active_material==mat]
        if len(meshes)>1:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in meshes: obj.select_set(True)
            bpy.context.view_layer.objects.active=meshes[0]
            bpy.ops.object.join()
            bpy.context.object.name=mat.name
    bpy.ops.export_scene.gltf(filepath=str(output/(key+".glb")),export_format="GLB",
                              export_cameras=False,export_lights=False)
