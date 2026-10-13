import * as THREE from 'three';
import {emissionGalaxy,emissionPalette,emissionSize,prepareEmissionGalaxies,type EmissionSize} from './galaxy-emission';
/** Each exhibit shares one palette and one disc geometry, with a cheap distant level. */
export function createGalaxyFactory(initialSize:EmissionSize=1536){
 let palette=emissionPalette(initialSize),size=initialSize,request=0,disposed=false;const geometry=new THREE.PlaneGeometry(2,2),groups:THREE.Group[]=[];
 const make=(seed:number,type:'spiral'|'elliptical'|'irregular'='spiral',distant=false)=>{const index=type==='elliptical'?4:type==='irregular'?5:Math.abs(seed)%3,group=emissionGalaxy(index,palette,geometry,!distant);group.rotation.set(-Math.PI/2+(seed%5-2)*.12,seed*.37,(seed%3-1)*.18,'YXZ');groups.push(group);return group;};
 make.quality=async(mode:'auto'|'low',width:number)=>{const next=emissionSize(width,mode),ticket=++request;if(size===next)return;await prepareEmissionGalaxies(next);if(disposed||ticket!==request)return;const old=palette;palette=emissionPalette(next);for(const g of groups)g.traverse(o=>{const material=(o as THREE.Mesh).material as THREE.MeshBasicMaterial|undefined;if(material?.map){const index=old.indexOf(material.map);if(index>=0)material.map=palette[index];}});old.forEach(t=>t.dispose());size=next;};
 make.dispose=()=>{disposed=true;request++;const used=new Set<THREE.Texture>();groups.forEach(g=>g.traverse(o=>{const map=((o as THREE.Mesh).material as THREE.MeshBasicMaterial)?.map;if(map)used.add(map);}));palette.forEach(t=>{if(!used.has(t))t.dispose();});};
 make.size=()=>size;make.presentation=(root:THREE.Group)=>{root.userData.textureQuality=size;return {quality:async(mode:'auto'|'low',width:number)=>{await make.quality(mode,width);root.userData.textureQuality=size;},dispose:make.dispose};};return make;
}
