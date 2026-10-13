import * as THREE from 'three';
import { u } from '../../lib/url';
const names=['grand-spiral','barred-spiral','many-arms','lenticular','elliptical','irregular'];
let source:THREE.Texture[]=[];
let pending:Promise<void>|null=null;
/** Original continuous emission maps. Cache owns source maps; scene owns clones. */
export function prepareEmissionGalaxies():Promise<void>{
 return pending??=Promise.all(names.map(n=>new THREE.TextureLoader().loadAsync(u(`/models/galaxies/${n}.png`)))).then(maps=>{source=maps;source.forEach(t=>{t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=4;});});
}
export function emissionPalette():THREE.Texture[]{return source.map(t=>{const c=t.clone();c.needsUpdate=true;return c;});}
export function emissionGalaxy(index:number,palette:THREE.Texture[]):THREE.Group{
 const g=new THREE.Group();
 const map=palette[index%names.length];if(!map)throw new Error('Galaxy emission map unavailable');
 // A thick luminous disc assembled from two original emission sheets, not discrete spheres.
 // No per-frame glow clock: all light is stationary unless the transport changes position.
 const mat=new THREE.MeshBasicMaterial({map,transparent:true,depthWrite:false,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,opacity:.91,toneMapped:false});
 const disc=new THREE.Mesh(new THREE.PlaneGeometry(2,2),mat);g.add(disc);
 const second=new THREE.Mesh(new THREE.PlaneGeometry(2,2),mat.clone());second.material.opacity=.11;second.position.z=.035;second.scale.setScalar(1.035);g.add(second);
 return g;
}
