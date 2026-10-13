"""Editable normalized worlds; provenance: solar-materials/manifest.json."""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[2]
maps=root/'assets/source/solar-materials'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
names=['mercurio','venus','terra','marte','jupiter','saturno','urano','netuno','lua']
def texture(mat,file,slot,noncolor=False):
    bs=mat.node_tree.nodes.get('Principled BSDF')
    image=bpy.data.images.load(str(maps/file),check_existing=True)
    if noncolor:image.colorspace_settings.name='Non-Color'
    image.pack();node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
    mat.node_tree.links.new(node.outputs['Color'],bs.inputs[slot]);return node
def material(name,file,rough=.94):
    m=bpy.data.materials.new(name);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=rough
    bs.inputs['Specular IOR Level'].default_value=.18
    texture(m,file,'Base Color');return m
worlds=[]
for name in names:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=1)
    obj=bpy.context.object;obj.name=name
    for f in obj.data.polygons:f.use_smooth=True
    mat=material(name+'_surface',name+'.jpg',.85 if name=='terra' else .97)
    if name=='terra':texture(mat,'terra-roughness.png','Roughness',True)
    if name=='lua':
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(maps/(name+'-normal.png')),check_existing=True);tex.image.colorspace_settings.name='Non-Color';tex.image.pack()
        normal=mat.node_tree.nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.32
        mat.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color']);mat.node_tree.links.new(normal.outputs['Normal'],mat.node_tree.nodes.get('Principled BSDF').inputs['Normal'])
    obj.data.materials.append(mat);worlds.append(obj)
    if name=='terra':
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=1.006)
        cloud=bpy.context.object;cloud.name='terra_nuvens';cloud.parent=obj
        for f in cloud.data.polygons:f.use_smooth=True
        cm=material('terra_clouds','terra-clouds.png',1)
        cn=next(n for n in cm.node_tree.nodes if n.type=='TEX_IMAGE');cm.node_tree.links.new(cn.outputs['Alpha'],cm.node_tree.nodes.get('Principled BSDF').inputs['Alpha'])
        cm.surface_render_method='DITHERED';cloud.data.materials.append(cm)
    if name=='saturno':
        vertices=[];uvs=[];faces=[];n=256
        for radius in [1.11,2.32]:
            for i in range(n):
                angle=i/n*math.tau;vertices.append((radius*math.cos(angle),radius*math.sin(angle),0));uvs.append(((radius-1.11)/1.21,i/n))
        for i in range(n):j=(i+1)%n;faces.append((i,j,j+n,i+n))
        mesh=bpy.data.meshes.new('saturn_radial_annulus');mesh.from_pydata(vertices,[],faces);mesh.update()
        ring=bpy.data.objects.new('saturno_aneis',mesh);bpy.context.collection.objects.link(ring);ring.parent=obj
        uv=mesh.uv_layers.new(name='UVMap')
        for p in mesh.polygons:
            for li in p.loop_indices:uv.data[li].uv=uvs[mesh.loops[li].vertex_index]
        rm=material('saturn_ring_density','saturno-rings.png',1);rt=next(n for n in rm.node_tree.nodes if n.type=='TEX_IMAGE');rm.node_tree.links.new(rt.outputs['Alpha'],rm.node_tree.nodes.get('Principled BSDF').inputs['Alpha']);rm.surface_render_method='DITHERED';rm.use_backface_culling=False;ring.data.materials.append(rm)
bpy.ops.wm.save_as_mainfile(filepath=str(root/'assets/source/mundos.blend'))
bpy.ops.export_scene.gltf(filepath=str(root/'public/models/mundos.glb'),export_format='GLB',export_yup=True,export_apply=True,export_cameras=False,export_lights=False)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.world.color=(.012,.015,.022);scene.view_settings.view_transform='AgX'
bpy.ops.object.light_add(type='AREA',location=(-4,-5,5));light=bpy.context.object;light.data.energy=650;light.data.shape='DISK';light.data.size=2.4
bpy.ops.object.camera_add(location=(0,-5.5,2.5));camera=bpy.context.object;camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera;camera.data.type='ORTHO'
portraits=root/'assets/source/solar-portraits';portraits.mkdir(exist_ok=True)
for obj in worlds:
    for other in worlds:
        other.hide_render=other!=obj
        for child in other.children:child.hide_render=other!=obj
    obj.rotation_euler=(0,math.radians(18) if obj.name=='saturno' else 0,math.radians(-100) if obj.name=='terra' else .3)
    camera.data.ortho_scale=5.5 if obj.name=='saturno' else 2.65
    scene.render.filepath=str(portraits/(obj.name+'.png'));bpy.ops.render.render(write_still=True)
    if obj.name=='saturno':
        obj.children[0].hide_render=True;camera.data.ortho_scale=2.65;scene.render.filepath=str(portraits/'saturno-globo.png');bpy.ops.render.render(write_still=True)
manifest=json.loads((maps/'manifest.json').read_text(encoding='utf-8'))
manifest.update({'blender':bpy.app.version_string,'reproduction':'blender --background --python assets/source/build_worlds.py','geometry':'Original normalized spheres, cloud shell and flat radial annulus; sizes, lighting and normal strength illustrative.'})
for file in [root/'assets/source/mundos.blend',root/'public/models/mundos.glb']+list(portraits.glob('*.png')):
    manifest['files'].append({'path':str(file.relative_to(root)).replace('\\','/'),'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
(root/'assets/source/manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
