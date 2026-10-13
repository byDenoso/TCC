import type * as THREE from 'three';
import type {Exhibit} from './runtime';
/** Opt-in measurement seam. It exists only when the QA harness provides the registry. */
export function registerDiagnostics(stage:HTMLElement,renderer:THREE.WebGLRenderer,exhibit:Exhibit){
 const qa=(window as unknown as {__COSMOS_QA?:{scenes:Map<number,()=>unknown>;history:unknown[];sequence:number}}).__COSMOS_QA;
 if(!qa)return {enabled:false,frame(_ms:number,_updateMs?:number){},dispose(){}};
 const id=++qa.sequence, times:number[]=[],updateTimes:number[]=[];let frames=0;
 const name=stage.closest<HTMLElement>('[data-mx]')?.dataset.mx??(stage.hasAttribute('data-e-volume')?'expansao':stage.hasAttribute('data-t-3d')?'tempo':stage.hasAttribute('data-solar-stage')?'solar':stage.hasAttribute('data-lens-stage')?'lente':'cena');
 const stats=()=>{
  const geometries=new Set<THREE.BufferGeometry>(),textures=new Set<THREE.Texture>(),materials=new Set<THREE.Material>();
  exhibit.group.traverse(o=>{const mesh=o as THREE.Mesh;if(mesh.geometry)geometries.add(mesh.geometry);for(const m of mesh.material?(Array.isArray(mesh.material)?mesh.material:[mesh.material]):[]){materials.add(m);for(const v of Object.values(m))if(v&&typeof v==='object'&&'isTexture' in v)textures.add(v as THREE.Texture);if('uniforms' in m)for(const u of Object.values((m as THREE.ShaderMaterial).uniforms))if(u.value?.isTexture)textures.add(u.value);}});
  const visibleTextures=new Set<THREE.Texture>();exhibit.group.traverseVisible(o=>{const mesh=o as THREE.Mesh;for(const m of mesh.material?(Array.isArray(mesh.material)?mesh.material:[mesh.material]):[]){for(const v of Object.values(m))if(v&&typeof v==='object'&&'isTexture' in v)visibleTextures.add(v as THREE.Texture);if('uniforms' in m)for(const u of Object.values((m as THREE.ShaderMaterial).uniforms))if(u.value?.isTexture)visibleTextures.add(u.value);}});
  let geometryBytes=0,textureBytes=0,textureStorageBytes=0;
  for(const g of geometries){for(const a of Object.values(g.attributes))geometryBytes+=a.array.byteLength;if(g.index)geometryBytes+=g.index.array.byteLength;}
  for(const t of textures){for(const image of(Array.isArray(t.image)?t.image:[t.image]) as {width?:number;height?:number;depth?:number;data?:ArrayBufferView}[]){const rgba=(image?.width??0)*(image?.height??0)*(image?.depth??1)*4;textureBytes+=rgba;textureStorageBytes+=image?.data?.byteLength??rgba;}}
  return {id,name,frames,visibleTextureDimensions:[...visibleTextures].map(t=>({source:t.source.id,name:t.name,width:t.image?.width??0,height:t.image?.height??0,depth:t.image?.depth??1})),textureDimensions:[...textures].map(t=>({source:t.source.id,name:t.name,width:t.image?.width??0,height:t.image?.height??0,depth:t.image?.depth??1})),readback:exhibit.inspect?.(),frameCpuMs:[...times],updateCpuMs:[...updateTimes],rendererMemory:{...renderer.info.memory},render:{...renderer.info.render},owned:{geometries:geometries.size,materials:materials.size,textures:textures.size,geometryBytes,textureRgbaBytesWithoutMips:textureBytes,textureStorageBytesWithoutMips:textureStorageBytes},objects:exhibit.group.children.filter(g=>g.name.startsWith('galaxy-')||g.name.startsWith('world-')).map(g=>({name:g.name,position:g.position.toArray(),scale:g.scale.toArray(),rotation:g.rotation.toArray()})),quality:stage.dataset.textureQuality};
 };
 qa.scenes.set(id,stats);
 return {enabled:true,frame(ms:number,updateMs=0){frames++;times.push(ms);updateTimes.push(updateMs);if(times.length>600){times.shift();updateTimes.shift();}},dispose(){qa.history.push(stats());if(qa.history.length>500)qa.history.shift();qa.scenes.delete(id);}};
}
