import * as THREE from 'three';
import { u } from '../../lib/url';
const names=['grand-spiral','barred-spiral','many-arms','lenticular','elliptical','irregular'];
const sources=new Map<number,THREE.Texture[]>(),loading=new Map<number,Promise<void>>();
export type EmissionSize=512|768|1536;
export const emissionSize=(width:number,quality:'auto'|'low'='auto'):EmissionSize=>quality==='low'?512:width<600?768:1536;
/** Cache owns CPU source images only. Each exhibit owns six shared GPU texture clones. */
export function prepareEmissionGalaxies(size:EmissionSize=1536):Promise<void>{
 if(!loading.has(size))loading.set(size,Promise.all(names.map(n=>new THREE.TextureLoader().loadAsync(u(`/models/galaxies-v4/${size===1536?'':size+'/'}${n}.webp`)))).then(maps=>{sources.set(size,maps);maps.forEach(t=>{t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=4;});}).catch(error=>{loading.delete(size);throw error;}));
 return loading.get(size)!;
}
export const emissionReady=(size:EmissionSize)=>sources.has(size);
export function emissionPalette(size:EmissionSize=1536):THREE.Texture[]{const source=sources.get(size);if(!source)throw new Error('Galaxy emission map unavailable');return source.map(t=>{const c=t.clone();c.needsUpdate=true;return c;});}
export function emissionGalaxy(index:number,palette:THREE.Texture[],discGeometry:THREE.PlaneGeometry,detailed=true):THREE.Group{
 const g=new THREE.Group();
 const map=palette[index%names.length];if(!map)throw new Error('Galaxy emission map unavailable');
 const mat=new THREE.MeshBasicMaterial({map,transparent:true,depthWrite:false,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,opacity:detailed?.94:.88,toneMapped:false});
 const disc=new THREE.Mesh(discGeometry,mat);g.add(disc);
 if(detailed){
  // Project the emission map through a tapered stellar envelope. It keeps a
  // line-of-sight thickness when the observer turns the disc edge-on.
  const body = new THREE.SphereGeometry(1,56,32);
  const pos=body.getAttribute('position'), uv=body.getAttribute('uv');
  const elliptical=index===4;
  for(let i=0;i<pos.count;i++){
    const x=pos.getX(i), y=pos.getY(i), radius=Math.hypot(x,y);
    uv.setXY(i,.5+x*.5,.5+y*.5);
    const height=elliptical?.52:.035+.18*Math.exp(-radius*8.);
    pos.setZ(i,pos.getZ(i)*height);
  }
  const envelopeMaterial=mat.clone();
  envelopeMaterial.side=THREE.FrontSide;
  envelopeMaterial.opacity=elliptical?.40:.25;
  g.add(new THREE.Mesh(body,envelopeMaterial));
 }
 return g;
}

const bareSources=new Map<EmissionSize,THREE.Texture>(),bareLoading=new Map<EmissionSize,Promise<void>>();
export function prepareStarsOnly(size:EmissionSize){if(!bareLoading.has(size))bareLoading.set(size,new THREE.TextureLoader().loadAsync(u(`/models/galaxies-v4/${size===1536?'':size+'/'}stars-only.webp`)).then(map=>{map.colorSpace=THREE.SRGBColorSpace;map.anisotropy=4;bareSources.set(size,map);}).catch(error=>{bareLoading.delete(size);throw error;}));return bareLoading.get(size)!;}
export function starsOnlyMap(size:EmissionSize){const source=bareSources.get(size);if(!source)throw Error('Stellar map unavailable');const map=source.clone();map.needsUpdate=true;return map;}

export const starsOnlyReady=(size:EmissionSize)=>bareSources.has(size);
