import * as THREE from 'three';
import { emissionGalaxy,emissionPalette } from './galaxy-emission';
import type { Exhibit } from './runtime';
import { expansionPositions } from '../../lib/expansion';

export function expansion(observer: () => number, arrows: () => boolean): Exhibit {
 const group=new THREE.Group();
 const palette=emissionPalette();
 const galaxies=expansionPositions.map((_,i)=>{
  const g=emissionGalaxy(i,palette);
  g.rotation.set([-.22,.38,-.46,.2][i%4],[-.22,.3,.7,-.65][i%4],i*1.73);
  g.scale.setScalar(i<3?1.2:[.52,.74,.62,.45][i%4]);group.add(g);return g;
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
 return {group,camera:[0,4.4,6.5],cameraForAspect:aspect=>aspect<1.2?[0,6.8,8.4]:[0,4.4,6.5],
 labels:galaxies.slice(0,3).map((object,i)=>({text:'ABC'[i],object,position:new THREE.Vector3(),pixelOffset:[i===1?-30:30,-14] as [number,number]})),update({value}){
  const scale=Math.max(1,value),origin=expansionPositions[observer()];
  galaxies.forEach((g,i)=>{
   const p=expansionPositions[i];g.position.set((p[0]-origin[0])*scale,(p[1]-origin[1])*scale,(p[2]-origin[2])*scale);
   const a=paths[i].geometry.getAttribute('position') as THREE.BufferAttribute;a.setXYZ(0,p[0]-origin[0],p[1]-origin[1],p[2]-origin[2]);a.setXYZ(1,g.position.x,g.position.y,g.position.z);a.needsUpdate=true;
   paths[i].visible=arrows()&&i!==observer()&&scale>1.01;
  });
 }};
}
