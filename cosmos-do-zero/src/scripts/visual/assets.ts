import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { u } from '../../lib/url';
let models: THREE.Group | null=null;
let loading: Promise<void> | null=null;let closed=false;
export function prepareWorlds(): Promise<void> {
  if(closed)return Promise.reject(new Error('Documento encerrado'));
  return loading ??= new GLTFLoader().loadAsync(u('/models/mundos.glb')).then(g=>{if(closed)releaseOriginals(g.scene);else models=g.scene;});
}
/** One ownership cache per exhibit: repeated worlds share uploads, disposed as a Set. */
export function createWorldFactory(): ((name:string)=>THREE.Group)&{quality(size:number):void;inspectSources():unknown} {
 const geometries=new Map<THREE.BufferGeometry,THREE.BufferGeometry>(),materials=new Map<THREE.Material,THREE.Material>(),textures=new Map<THREE.Texture,THREE.Texture>();
 let maximum=2048;
 const resizeMap=(source:THREE.Texture,target:THREE.Texture)=>{const image=source.image as {width:number;height:number};if(!image?.width)return;let nextImage:THREE.Texture['image'];if(image.width<=maximum){nextImage=source.image;}else{const canvas=document.createElement('canvas');canvas.width=maximum;canvas.height=Math.max(1,Math.round(image.height*maximum/image.width));canvas.getContext('2d')!.drawImage(source.image as CanvasImageSource,0,0,canvas.width,canvas.height);nextImage=canvas;}
  // Immutable GL storage must be released before changing image dimensions.
  target.dispose();target.source=new THREE.Source(nextImage);target.anisotropy=maximum<=512?1:4;target.needsUpdate=true;
 };
 const cloneMaterial=(source:THREE.Material)=>{
  if(materials.has(source))return materials.get(source)!;
  const clone=source.clone() as THREE.MeshStandardMaterial;
  for(const [key,value] of Object.entries(clone))if(value instanceof THREE.Texture){if(!textures.has(value)){const texture=value.clone();texture.source=new THREE.Source(value.image);textures.set(value,texture);resizeMap(value,texture);}(clone as unknown as Record<string,unknown>)[key]=textures.get(value);}
  clone.roughness=source.name.includes('surface')?Math.max(clone.roughness,.7):clone.roughness;
  if(source.name.includes('cloud')){clone.transparent=true;clone.depthWrite=false;clone.opacity=.72;}
  if(source.name.includes('ring')){clone.side=THREE.DoubleSide;clone.alphaTest=.12;clone.transparent=true;clone.depthWrite=true;}
  materials.set(source,clone);return clone;
 };
 const make=(name:string)=>{
  const original=models?.getObjectByName(name);
  if(!original)throw new Error('Asset de mundo ausente: '+name);
  const group=new THREE.Group();const obj=original.clone(true);
  obj.traverse(o=>{const m=o as THREE.Mesh;if(!m.isMesh)return;
    if(!geometries.has(m.geometry))geometries.set(m.geometry,m.geometry.clone());m.geometry=geometries.get(m.geometry)!;
    m.material=Array.isArray(m.material)?m.material.map(cloneMaterial):cloneMaterial(m.material);m.castShadow=!m.name.includes('nuvens');m.receiveShadow=true;
  });group.add(obj);return group;
 };
 make.inspectSources=()=>[...textures.keys()].map(source=>{const image=source.image as {width?:number;height?:number};if(image&&typeof image==='object'&&!bitmapIds.has(image))bitmapIds.set(image,++nextBitmap);return {source:source.source.id,bitmap:bitmapIds.get(image)??0,width:image?.width??0,height:image?.height??0};});
 make.quality=(size:number)=>{if(size===maximum)return;maximum=size;textures.forEach((target,source)=>resizeMap(source,target));};return make;
}
export function world(name:string):THREE.Group{return createWorldFactory()(name);}

/** Read-only seam used by the browser regression; the cached original images stay immutable. */
const bitmapIds=new WeakMap<object,number>();let nextBitmap=0;
export function worldSourceDiagnostics(){const rows:{name:string;source:number;bitmap:number;width:number;height:number}[]=[],seen=new Set<THREE.Texture>();models?.traverse(o=>{const m=o as THREE.Mesh;for(const material of m.material?(Array.isArray(m.material)?m.material:[m.material]):[])for(const value of Object.values(material)){if(!(value instanceof THREE.Texture)||seen.has(value))continue;seen.add(value);const image=value.image as {width?:number;height?:number};if(image&&typeof image==='object'&&!bitmapIds.has(image))bitmapIds.set(image,++nextBitmap);rows.push({name:value.name||m.name,source:value.source.id,bitmap:bitmapIds.get(image)??0,width:image?.width??0,height:image?.height??0});}});return rows;}

function releaseOriginals(root:THREE.Object3D){const textures=new Set<THREE.Texture>(),images=new Set<{close?:()=>void}>();root.traverse(o=>{const m=o as THREE.Mesh;for(const material of m.material?(Array.isArray(m.material)?m.material:[m.material]):[])for(const value of Object.values(material))if(value instanceof THREE.Texture)textures.add(value);});textures.forEach(t=>{const image=t.image as {close?:()=>void};if(image)images.add(image);t.dispose();});images.forEach(image=>image.close?.());}
if(typeof window!=='undefined')window.addEventListener('pagehide',e=>{if(e.persisted)return;closed=true;if(models)releaseOriginals(models);models=null;loading=null;});
