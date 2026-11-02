import * as THREE from 'three';
import { createWorldFactory,prepareWorlds } from './assets';
import { observeScene,whenNear,type Exhibit,type MountedScene } from './runtime';
import { planets } from '../../data/client';

export function styleEarth(world:THREE.Group,cut=false):void{
 const earth=world.getObjectByName('terra') as THREE.Mesh;
 const earthMaterial=earth.material as THREE.MeshStandardMaterial;
 if(!earthMaterial.userData.cosmosOcean){
  // The land-oriented MODIS base map has near-black water; tint only its dark blue pixels.
  earthMaterial.onBeforeCompile=(shader)=>{
   shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
float water=smoothstep(.002,.007,diffuseColor.b-diffuseColor.r)*(1.-smoothstep(.018,.06,max(diffuseColor.r,max(diffuseColor.g,diffuseColor.b))));
diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.012,.065,.16),water*.9);`);
  };
  earthMaterial.customProgramCacheKey=()=> 'earth-ocean-tint-v1';
  earthMaterial.userData.cosmosOcean=true;earthMaterial.needsUpdate=true;
 }
 const clouds=world.getObjectByName('terra_nuvens') as THREE.Mesh | undefined;
 if(clouds){
  const material=clouds.material as THREE.MeshStandardMaterial;
  if(!material.userData.cosmosClouds){
   // A spherical procedural field avoids the old oversized, pole-pinched cloud map.
   material.map?.dispose(); material.map=null; material.side=THREE.FrontSide;
   material.transparent=true;material.depthWrite=false;material.opacity=.62;material.color.set(0xf5f9ff);
   material.onBeforeCompile=(shader)=>{
    shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vCloudP;').replace('#include <begin_vertex>','#include <begin_vertex>\nvCloudP = position;');
    shader.fragmentShader=shader.fragmentShader.replace('#include <common>',`#include <common>
varying vec3 vCloudP;
float cloudHash(vec3 p){p=fract(p*.1031);p+=dot(p,p.yzx+33.33);return fract((p.x+p.y)*p.z);}
float cloudNoise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(mix(cloudHash(i),cloudHash(i+vec3(1,0,0)),f.x),mix(cloudHash(i+vec3(0,1,0)),cloudHash(i+vec3(1,1,0)),f.x),f.y),mix(mix(cloudHash(i+vec3(0,0,1)),cloudHash(i+vec3(1,0,1)),f.x),mix(cloudHash(i+vec3(0,1,1)),cloudHash(i+vec3(1,1,1)),f.x),f.y),f.z);}
float cloudFbm(vec3 p){return .52*cloudNoise(p)+.27*cloudNoise(p*2.03)+.14*cloudNoise(p*4.11)+.07*cloudNoise(p*8.19);}`)
     .replace('#include <color_fragment>',`#include <color_fragment>
vec3 globe=normalize(vCloudP);float warp=cloudFbm(globe*3.4+vec3(7.1,2.4,5.7));
float cloud=cloudFbm(globe*8.0+vec3(warp*2.2,warp*1.0,-warp*1.7));
cloud+=.12*(cloudNoise(globe*25.0+9.0)-.5);
diffuseColor.a*=smoothstep(.50,.67,cloud);`);
   };
   material.customProgramCacheKey=()=> 'earth-clouds-spherical-v1';
   material.userData.cosmosClouds=true;material.needsUpdate=true;
  }
 }
 // A reflected sky changes the material response, not MODIS pixels. Reuse it for duplicate Earths.
 if(!earthMaterial.envMap){
 const sky=new THREE.CubeTexture(Array.from({length:6},(_,i)=>{const c=document.createElement('canvas');c.width=c.height=32;const ctx=c.getContext('2d')!;ctx.fillStyle=i===3?'#101c27':i===2?'#476d8d':'#294f70';ctx.fillRect(0,0,32,32);return c;}));sky.colorSpace=THREE.SRGBColorSpace;sky.needsUpdate=true;
 earthMaterial.envMap=sky;earthMaterial.envMapIntensity=.75;
 }
 const atmosphere=new THREE.Mesh(cut?new THREE.SphereGeometry(1.014,64,32,Math.PI/2,Math.PI*1.5):new THREE.SphereGeometry(1.014,64,32),new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.FrontSide,
  vertexShader:'varying vec3 n;varying vec3 wn;varying vec3 p;void main(){wn=normalize(mat3(modelMatrix)*normal);vec4 v=modelViewMatrix*vec4(position,1.);n=normalize(normalMatrix*normal);p=v.xyz;gl_Position=projectionMatrix*v;}',
  fragmentShader:'varying vec3 n;varying vec3 wn;varying vec3 p;void main(){float edge=pow(1.-max(0.,dot(normalize(n),normalize(-p))),2.7);float day=.38+.62*smoothstep(-.3,.6,dot(normalize(wn),normalize(vec3(-5.,4.,6.))));gl_FragColor=vec4(.15,.56,1.,day*(edge*.52+.006));}'
 }));world.add(atmosphere);
 if(!cut){
  const halo=new THREE.Mesh(new THREE.SphereGeometry(1.06,64,32),new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.BackSide,
   vertexShader:'varying vec3 n;varying vec3 p;void main(){vec4 v=modelViewMatrix*vec4(position,1.);n=normalize(normalMatrix*normal);p=v.xyz;gl_Position=projectionMatrix*v;}',
   fragmentShader:'varying vec3 n;varying vec3 p;void main(){float mu=abs(dot(normalize(n),normalize(-p)));float glow=smoothstep(.0,.26,mu);gl_FragColor=vec4(.12,.54,1.,glow*.55);}'
  }));world.add(halo);
 }
}
export function worldExhibit(names:()=>string[],radii:()=>number[] =()=>[1]):Exhibit {
 const group=new THREE.Group(),make=createWorldFactory(),worlds=new Map<string,THREE.Group>();
 const labels=[0,1].map(i=>({text:'',position:new THREE.Vector3(i===0?-1.3:1.3,-1.08,0),visible:()=>names().length>1}));
 const framing=()=>names().length>1?[0,.5,4.3] as [number,number,number]:names()[0]==='saturno'?[0,1.8,6.1] as [number,number,number]:[0,.48,3.65] as [number,number,number];
 return {group,highDefinition:true,inspect(){return {originals:make.inspectSources()};},labels,orthographicHeight:names().length>1?(aspect)=>aspect<1.4?4.8:3.2:undefined,camera:framing(),cameraForAspect:(aspect)=>{const c=framing();return [c[0],c[1],c[2]*(names().length>1&&aspect<1.4?1.55:names()[0]==='saturno'&&aspect<1?1.2:1)];},lighting:{ambient:.24,key:3.4,fill:.06,exposure:1.18,shadows:true,neutral:true},quality(mode,width){const size=mode==='low'?512:width<600?1024:2048;make.quality(size);group.userData.textureQuality=size;},
 update(state){worlds.forEach(w=>w.visible=false);const selected=names(),sizes=radii(),max=Math.max(...sizes);
 selected.forEach((name,i)=>{const key=i===1&&selected[0]===name?name+'-second':name;if(!worlds.has(key)){const clone=make(name);if(name==='terra')styleEarth(clone);group.add(clone);worlds.set(key,clone);}const w=worlds.get(key);if(!w)return;w.name='world-'+name+'-'+i;w.visible=true;w.position.set(selected.length>1?(i===0?-1.3:1.3):0,0,0);w.scale.setScalar(selected.length>1?sizes[i]/max:1);const spin=(planets.find(p=>p.id===name)?.rotation??1)<0?-state.phase:state.phase;w.rotation.set(name==='saturno'?.36:0,name==='terra'?-1.8+spin:spin,name==='saturno'?-.25:0);
 if(selected.length>1){const ring=w.getObjectByName('saturno_aneis');if(ring)ring.visible=false;labels[i].position.set(w.position.x,-sizes[i]/max-.13,0);labels[i].text=planets.find(p=>p.id===name)?.name??name;}});
 }};
}
export async function attachWorldView(stage:HTMLElement,names:()=>string[],radii?:()=>number[],valid:()=>boolean=()=>true):Promise<MountedScene|null>{
 try{if(!await whenNear(stage,valid))return null;await prepareWorlds();return valid()?observeScene(stage,()=>worldExhibit(names,radii)):null;}catch{if(valid()){stage.dataset.visualFallback='true';stage.dispatchEvent(new CustomEvent('cosmos:unavailable'));}return null;}
}
export async function initCatalogWorld(root:HTMLElement,stage:HTMLElement,names:()=>string[],radii?:()=>number[]):Promise<void>{
 let alive=true;window.addEventListener('pagehide',e=>{if(!e.persisted)alive=false;});
 try{if(!await whenNear(stage,()=>alive))return;await prepareWorlds();if(!alive)return;let view:MountedScene|null=null;
 const refresh=()=>{view?.dispose();view=observeScene(stage,()=>worldExhibit(names,radii));view.state({phase:0});};
 root.addEventListener('cosmos:worldselection',refresh);refresh();
 window.addEventListener('pagehide',e=>{if(!e.persisted){root.removeEventListener('cosmos:worldselection',refresh);view?.dispose();}});
 }catch{stage.dataset.visualFallback='true';}
}
