import * as THREE from 'three';
import type { Exhibit } from './runtime';
import { createGalaxyFactory } from './galaxy';

/** Interpolação artística volumétrica. Não é integração gravitacional N-body. */
export function cosmicWeb(initialSize:import('./galaxy-emission').EmissionSize=1536,sharedFactory?:ReturnType<typeof createGalaxyFactory>):Exhibit {
 const galaxy=sharedFactory??createGalaxyFactory(initialSize);
 const group=new THREE.Group();let seed=41;const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
 const normal=()=>Math.sqrt(-2*Math.log(Math.max(1e-6,random())))*Math.cos(2*Math.PI*random());
 const nodes=Array.from({length:14},()=>new THREE.Vector3((random()-.5)*6,(random()-.5)*2.6,(random()-.5)*5));
 const n=7200,start=new Float32Array(n*3),end=new Float32Array(n*3),weights=new Float32Array(n);
 for(let i=0;i<n;i++){
  const a=nodes[Math.floor(random()*nodes.length)];
  const nearest=nodes.filter(b=>b!==a).sort((b,c)=>a.distanceToSquared(b)-a.distanceToSquared(c));
  const cluster=random()<.28;weights[i]=cluster?1:.35+random()*.35;const target=cluster?a.clone():a.clone().lerp(nearest[Math.floor(random()*3)],random());
  target.add(new THREE.Vector3(normal()*.075,normal()*.075,normal()*.075));
  end.set(target.toArray(),i*3);start.set([(random()-.5)*6,(random()-.5)*2.6,(random()-.5)*5],i*3);
 }
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(end,3));geo.setAttribute('aStart',new THREE.BufferAttribute(start,3));geo.setAttribute('aWeight',new THREE.BufferAttribute(weights,1));
 const uniforms={uK:{value:0}};
 const mat=new THREE.ShaderMaterial({uniforms,toneMapped:false,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
 vertexShader:'attribute vec3 aStart;attribute float aWeight;varying float vW;uniform float uK;void main(){vW=mix(.45,aWeight,uK);vec3 p=mix(aStart,position,uK);vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;gl_PointSize=clamp((24.+vW*10.)/-mv.z,1.4,5.);}',
 fragmentShader:'varying float vW;void main(){vec2 p=gl_PointCoord-.5;float r=dot(p,p);if(r>.25)discard;gl_FragColor=vec4(mix(vec3(.35,.55,.82),vec3(.9,.72,.46),vW),exp(-r*25.)*(.12+.18*vW));}'
 });group.add(new THREE.Points(geo,mat));
 const galaxies=nodes.map((p,i)=>{const g=galaxy(77+i,i%4===0?'elliptical':i%5===0?'irregular':'spiral',true);g.position.copy(p);g.scale.setScalar(.16);g.rotation.set(i*.2,i*.7,i*.4);group.add(g);return g;});
 return {group,...(!sharedFactory?galaxy.presentation(group):{}),camera:[0,2.8,6.5],cameraForAspect:a=>a<1.6?[0,4.5,9]:[0,2.8,6.5],update({value}){uniforms.uK.value=Math.min(1,Math.max(0,value));galaxies.forEach(g=>g.visible=value>.8);}};
}
