import bpy, math, os, json, hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'mercurio':(.42,.36,.31),'venus':(.74,.60,.37),'terra':(.035,.19,.34),'marte':(.49,.15,.07),'jupiter':(.65,.48,.31),'saturno':(.66,.59,.39),'urano':(.23,.58,.63),'netuno':(.07,.23,.49),'lua':(.41,.43,.46)}
for name,base in colors.items():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=1)
    obj=bpy.context.object;obj.name=name
    for f in obj.data.polygons:f.use_smooth=True
    mat=bpy.data.materials.new(name+'_material');mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.84
    image=bpy.data.images.new(name+'_original_illustrative',width=512,height=256)
    pixels=[]
    for y in range(256):
      v=y/255
      for x in range(512):
        u=x/511
        noise=math.sin(u*76+math.sin(v*45))*math.cos(v*93+u*17)
        bands=math.sin(v*58+math.sin(u*20)*.13)
        k=.85+.13*noise
        if name in ['jupiter','saturno','urano','netuno']:k=.86+.15*bands+.05*noise
        col=tuple(min(1,max(0,c*k)) for c in base)
        if name=='terra':
          land=math.sin(u*18+math.sin(v*13)*2)+math.sin(u*31-v*19)*.45
          if land>.5:col=(.12*k,.25*k,.13*k)
          if abs(v-.5)>.4:col=(.72,.76,.78)
          if math.sin(u*51+v*61)+math.sin(v*91-u*30)>1.3:col=tuple(c*.4+.5 for c in col)
        pixels.extend((*col,1))
    image.pixels=pixels;image.filepath_raw=str(root/'assets/source'/f'{name}.png');image.file_format='PNG';image.save();image.pack()
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
    mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
    obj.data.materials.append(mat)
    if name=='saturno':
      bpy.ops.mesh.primitive_torus_add(major_radius=1.65,minor_radius=.24,major_segments=64,minor_segments=4)
      ring=bpy.context.object;ring.name='saturno_aneis';ring.scale.z=.035
      rm=bpy.data.materials.new('poeira_dos_aneis');rm.diffuse_color=(.43,.37,.24,1);ring.data.materials.append(rm)
      ring.parent=obj
bpy.ops.wm.save_as_mainfile(filepath=str(root/'assets/source'/'mundos.blend'))
bpy.ops.export_scene.gltf(filepath=str(root/'public/models'/'mundos.glb'),export_format='GLB',use_selection=False,export_yup=True,export_apply=True)
manifest={'author':'Cosmos do Zero / original procedural authoring','license':'CC0-1.0','scientific_status':'Illustrative materials, normalized spheres; no observed terrain data. Sizes are set by the lesson, not the mesh.','blender':bpy.app.version_string,'reproduction':'blender --background --python assets/source/build_worlds.py','files':[]}
for file in [root/'assets/source'/'mundos.blend',root/'public/models'/'mundos.glb']+list((root/'assets/source').glob('*.png')):
    manifest['files'].append({'path':str(file.relative_to(root)).replace('\\','/'),'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
(root/'assets/source'/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
