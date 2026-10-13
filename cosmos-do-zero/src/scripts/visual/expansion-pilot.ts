import * as THREE from 'three';
import { emissionGalaxy,emissionPalette,emissionSize,prepareEmissionGalaxies,type EmissionSize } from './galaxy-emission';
import type { Exhibit } from './runtime';
import { expansionPositions } from '../../lib/expansion';

export function expansion(observer: () => number, arrows: () => boolean,initialSize:EmissionSize=1536): Exhibit {
 const group=new THREE.Group();
 let size=initialSize,palette=emissionPalette(size),request=0,disposed=false;
 group.userData.textureQuality=size;
 const discGeometry=new THREE.PlaneGeometry(2,2);
 const galaxies=expansionPositions.map((_,i)=>{
  const g=emissionGalaxy(i,palette,discGeometry);g.name=`galaxy-${i}`;
  g.rotation.set([-.25,.32,-.62,.4][i%4],[-.3,.65,.9,-.65][i%4],i*1.73);
  g.scale.setScalar(i===0?1.15:i===1?1.2:i===2?1.04:[.46,.58,.48,.36][i%4]);group.add(g);return g;
 });
 // Faint distant starlight, radial Gaussian fragments instead of square points.
 const positions=new Float32Array(900*3);let seed=8712;
 const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
 for(let i=0;i<900;i++)positions.set([(random()-.5)*30,(random()-.5)*18,-8-random()*14],i*3);
 const stars=new THREE.BufferGeometry();stars.setAttribute('position',new THREE.BufferAttribute(positions,3));
 group.add(new THREE.Points(stars,new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false,
 vertexShader:'void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_PointSize=2.2;}',
 fragmentShader:'void main(){vec2 p=gl_PointCoord-.5;float a=exp(-dot(p,p)*32.)*.18;gl_FragColor=vec4(.64,.74,.92,a);}' })));
 const paths=expansionPositions.map(()=>{const geo=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]);const line=new THREE.Line(geo,new THREE.LineBasicMaterial({color:0x8ca4ba,transparent:true,opacity:.24}));group.add(line);return line;});
 return {group,inspect(){return {galaxies:galaxies.map(g=>({name:g.name,scale:g.scale.toArray(),position:g.position.toArray()}))};},camera:[1.1,3.4,7.8],cameraForAspect:aspect=>aspect<1.2?[.8,5.7,10.6]:[1.1,3.4,7.8],
 async quality(mode,width){const next=emissionSize(width,mode),ticket=++request;if(next===size)return;await prepareEmissionGalaxies(next);if(disposed||ticket!==request)return;const old=palette;palette=emissionPalette(next);group.traverse(o=>{const mesh=o as THREE.Mesh;for(const m of mesh.material?(Array.isArray(mesh.material)?mesh.material:[mesh.material]):[]){const material=m as THREE.MeshBasicMaterial;const index=material.map?old.indexOf(material.map):-1;if(index>=0)material.map=palette[index];}});old.forEach(t=>t.dispose());size=next;group.userData.textureQuality=size;},
 dispose(){disposed=true;request++;},
 labels:galaxies.slice(0,3).map((object,i)=>({text:'ABC'[i],object,position:new THREE.Vector3(),pixelOffset:[i===1?-30:30,-14] as [number,number]})),update({value}){
  const scale=Math.max(1,value),origin=expansionPositions[observer()];
  galaxies.forEach((g,i)=>{
   const p=expansionPositions[i];g.position.set((p[0]-origin[0])*scale,(p[1]-origin[1])*scale,(p[2]-origin[2])*scale);
   const a=paths[i].geometry.getAttribute('position') as THREE.BufferAttribute;a.setXYZ(0,p[0]-origin[0],p[1]-origin[1],p[2]-origin[2]);a.setXYZ(1,g.position.x,g.position.y,g.position.z);a.needsUpdate=true;
   paths[i].visible=arrows()&&i!==observer()&&scale>1.01;
  });
 }};
}
