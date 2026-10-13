import {structuresScene} from './origin-scenes';
import {diskScene,giantScene,cometScene} from './solar-processes';
import {distantStar} from './stellar-materials';
import {styleEarth} from './world-view';
import {emissionReady,emissionSize,prepareStarsOnly,starsOnlyMap,starsOnlyReady} from './galaxy-emission';
import {earthLayersScene,atmosphereScene,magnetosphereScene} from './earth-scenes';
import {remnantScene} from './remnants';
import { nebulaScene,collapseScene,sunLayersScene,stellarPairScene,massiveScene,stellarMassScene } from './stellar-scenes';
import * as THREE from 'three';
import type { Exhibit,VisualState } from './runtime';
import { createGalaxyFactory } from './galaxy';
import { cosmicWeb } from './web';
import { horizon } from './horizon';
import { createWorldFactory } from './assets';
import { expansion } from './expansion';
import { trajectory,trajectoryAt } from '../micro/sistema';

const colors=[0xf6bb78,0x88b1e8,0xc97079,0x96cbbc];
const sphere=(r:number,col:number,emissive=false)=>new THREE.Mesh(new THREE.SphereGeometry(r,32,20),new THREE.MeshStandardMaterial({color:col,roughness:.85,emissive:emissive?col:0,emissiveIntensity:emissive?.4:0}));
const web=cosmicWeb;
export function address(initialSize:import('./galaxy-emission').EmissionSize=1536):Exhibit{
 const galaxy=createGalaxyFactory(initialSize);
  const makeWorld=createWorldFactory();
  const group=new THREE.Group(),steps=Array.from({length:5},()=>new THREE.Group());steps.forEach(s=>group.add(s));
  const homeEarth=makeWorld('terra');styleEarth(homeEarth);homeEarth.scale.setScalar(1.3);steps[0].add(homeEarth);
  const sun=distantStar(0xffd6a1);sun.scale.setScalar(.38);steps[1].add(sun);
  ['mercurio','venus','terra','marte','jupiter','saturno','urano','netuno'].forEach((name,i)=>{const w=makeWorld(name);const a=i*1.7,r=.8+i*.26;w.scale.setScalar(i<4?.08:.15);w.position.set(Math.cos(a)*r,0,Math.sin(a)*r);steps[1].add(w);});
  const milkyWay=galaxy(55),solarAddress=new THREE.Object3D();solarAddress.position.set(.36,.20,.06);milkyWay.add(solarAddress);const marker=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(Array.from({length:32},(_,i)=>new THREE.Vector3(.36+.045*Math.cos(i/32*Math.PI*2),.20+.045*Math.sin(i/32*Math.PI*2),.06))),new THREE.LineBasicMaterial({color:0xe6ba73}));milkyWay.add(marker);steps[2].add(milkyWay);steps[2].scale.setScalar(3.5);
  const localPositions=[[-1.1,.18,.2],[1.15,-.12,.0],[-1.9,.85,-1.8],[.2,.9,-2.4],[1.8,.6,-1.5],[-.2,-.6,-1.3]],localGalaxies=localPositions.map((p,i)=>{const g=galaxy(i===0?55:27+i,i>1&&i%3===0?'elliptical':'spiral');g.scale.setScalar(i<2?1.05:.3);g.position.set(p[0],p[1],p[2]);steps[3].add(g);return g;});
  const network=web(initialSize,galaxy);steps[4].add(network.group);steps[4].scale.setScalar(.6);network.update({value:1,phase:1,elapsed:0});
  return {group,labels:[...localGalaxies.slice(0,2).map((g,i)=>({text:i===0?'Via Láctea':'Andrômeda',position:g.position,visible:()=>steps[3].visible})),{text:'Sistema Solar',object:solarAddress,position:solarAddress.position,visible:()=>steps[2].visible,pixelOffset:[65,-18]}],lighting:{neutral:true,ambient:1.4,key:3,fill:.3,exposure:1},quality:async(mode,width)=>{await galaxy.quality(mode,width);makeWorld.quality(mode==='low'?512:width<600?1024:2048);group.userData.textureQuality=galaxy.size();},dispose:galaxy.dispose,camera:[0,.6,4.5],cameraForValue:(value,aspect)=>{const views:[number,number,number][]=[[0,.6,4.5],[0,4.7,5.8],[0,4.2,5.2],[0,3.2,5.7],[0,2.2,4.5]];const c=views[Math.max(0,Math.min(4,Math.round(value)))];return [c[0],c[1],c[2]*(aspect<1.2?1.12:1)];},update({value}){steps.forEach((s,i)=>s.visible=i===Math.round(value));}};
}
function galaxyLayers(initialSize:import('./galaxy-emission').EmissionSize=1536):Exhibit{
 const galaxy=createGalaxyFactory(initialSize),group=new THREE.Group(),spiral=galaxy(24),elliptical=galaxy(3,'elliptical');spiral.rotation.set(-Math.PI/2,.1,0,'YXZ');elliptical.rotation.set(-Math.PI/2+.38,-.2,.25,'YXZ');
 let bareMap=starsOnlyMap(initialSize),bareSize=initialSize,request=0,alive=true;const stars=spiral.clone(true);stars.traverse(o=>{const mesh=o as THREE.Mesh;if(mesh.material instanceof THREE.MeshBasicMaterial&&mesh.material.map){mesh.material=mesh.material.clone();(mesh.material as THREE.MeshBasicMaterial).map=bareMap;}});
 const halo=new THREE.Mesh(new THREE.SphereGeometry(1.3,32,16),new THREE.MeshBasicMaterial({color:0x526b96,transparent:true,opacity:.045,depthWrite:false}));group.add(stars,spiral,elliptical,halo);stars.scale.setScalar(1.45);spiral.scale.setScalar(1.45);elliptical.scale.setScalar(1.45);group.userData.textureQuality=initialSize;
 return {group,labels:[{text:'halo inferido · não emite esta luz',position:new THREE.Vector3(0,-1.4,0),visible:()=>halo.visible}],camera:[0,2.7,4.8],async quality(mode,width){const ticket=++request;await galaxy.quality(mode,width);const size=galaxy.size();await prepareStarsOnly(size);if(!alive||ticket!==request||bareSize===size)return;const next=starsOnlyMap(size);stars.traverse(o=>{const m=(o as THREE.Mesh).material as THREE.MeshBasicMaterial;if(m?.map===bareMap)m.map=next;});bareMap.dispose();bareMap=next;bareSize=size;group.userData.textureQuality=size;},dispose(){alive=false;request++;galaxy.dispose();},update({value}){stars.visible=value<1;spiral.visible=value>=1&&value<3;elliptical.visible=value>=3;halo.visible=value>=2&&value<3;}};
}
function nebula():Exhibit{return nebulaScene();}

function lightJourney():Exhibit{
 const group=new THREE.Group(),make=createWorldFactory(),earth=make('terra'),star=distantStar,photon=sphere(.055,0x90badd,true);styleEarth(earth);earth.position.x=1.65;earth.scale.setScalar(.5);group.add(earth,photon);
 const sources=[make('lua'),star(0xfff3df),star(0xff8268)];sources.forEach(s=>{s.position.x=-1.65;group.add(s);});sources[0].scale.setScalar(.34);sources[1].scale.setScalar(1.45);sources[2].scale.setScalar(1.05);
 const label={text:'Lua · 1,3 segundo',position:sources[0].position};return {group,lighting:{neutral:true,ambient:.35,key:3.3,fill:.15,exposure:1.1},labels:[label,{text:'Terra',position:earth.position}],camera:[0,1.1,5.6],quality(mode,width){make.quality(mode==='low'?512:width<600?1024:2048);},update({value,phase}){const v=Math.min(2,Math.round(value));sources.forEach((s,i)=>s.visible=i===v);label.text=['Lua · 1,3 segundo','Sol · 8 min 20 s','Proxima Centauri · 4,2 anos'][v];photon.position.x=-1.25+phase*2.5;}};
}
function atoms():Exhibit{
  const group=new THREE.Group(),parts=Array.from({length:28},(_,i)=>{const p=sphere(i<4?.09:.07,i<4?0x8f99ad:0xc5684f);group.add(p);return p;});
  const electronGeo=new THREE.SphereGeometry(.035,12,8),electronMaterial=new THREE.MeshBasicMaterial({color:0x70b6ed,toneMapped:false}),electrons=Array.from({length:24},()=>new THREE.Mesh(electronGeo,electronMaterial));electrons.forEach(e=>group.add(e));
  const clouds=Array.from({length:24},()=>new THREE.Mesh(new THREE.SphereGeometry(.19,16,10),new THREE.MeshBasicMaterial({color:0x74a8cf,transparent:true,opacity:.1,depthWrite:false})));clouds.forEach(c=>group.add(c));
  return {group,camera:[0,2,6],update({value,phase}){parts.forEach((p,i)=>{const bound=value>=1&&i<8,k=value===1?phase:1;
    const original=new THREE.Vector3(Math.sin(i*6.7)*2,Math.cos(i*3.9)*1.2,Math.cos(i*1.7));const cluster=i<4?Math.floor(i/2):Math.floor((i-4)/2);const target=new THREE.Vector3(cluster===0?-.6:.8,(i%2-.5)*.14,i<4?-.07:.07);p.position.copy(bound?original.lerp(target,k):original);
  });electrons.forEach((e,i)=>{if(value<3)e.position.set(Math.sin(i*4.9+.6)*2.1,Math.cos(i*7.3+.2)*1.3,Math.sin(i*6.1)*1.1);else{e.position.copy(parts[i+4].position);e.position.x+=(i%2?1:-1)*.25;e.position.y+=.14;e.position.z+=.18;}});clouds.forEach((c,i)=>{c.visible=value>=3;c.position.copy(parts[i+4].position);});}};
}
function firstStructures():Exhibit{return structuresScene();}
function collapse():Exhibit{return collapseScene();}

function sunLayers():Exhibit{return sunLayersScene();}

function stellarPair():Exhibit{return stellarPairScene();}

export function blackHole():Exhibit{return remnantScene();}
function massive():Exhibit{return massiveScene(blackHole);}

export function stellarMass(mass:()=>number):Exhibit{return stellarMassScene(mass,blackHole);}

function solarDisk():Exhibit{return diskScene();}
function giant():Exhibit{return giantScene();}
function comet():Exhibit{return cometScene();}
function orbit():Exhibit{
  const make=createWorldFactory();make.quality(512);const group=new THREE.Group(),sun=distantStar(0xffd6a1),body=make('terra');sun.scale.setScalar(.6);body.scale.setScalar(.06);group.add(sun,body);
  let geo=new THREE.BufferGeometry();const line=new THREE.Line(geo,new THREE.LineBasicMaterial({color:0x709dc9}));group.add(line);
  const velocity=new THREE.ArrowHelper(new THREE.Vector3(0,0,1),new THREE.Vector3(),.4,0x86bddb,.09,.05),gravity=new THREE.ArrowHelper(new THREE.Vector3(-1,0,0),new THREE.Vector3(),.4,0xe3b96f,.09,.05);group.add(velocity,gravity);
  const markerCanvas=document.createElement('canvas');markerCanvas.width=markerCanvas.height=64;const markerContext=markerCanvas.getContext('2d')!,markerGradient=markerContext.createRadialGradient(32,32,0,32,32,32);markerGradient.addColorStop(0,'#fff');markerGradient.addColorStop(.38,'#fff');markerGradient.addColorStop(.7,'#ffffff50');markerGradient.addColorStop(1,'#fff0');markerContext.fillStyle=markerGradient;markerContext.fillRect(0,0,64,64);const positionMarker=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(markerCanvas),color:0xf4e9d2,transparent:true,depthTest:false,depthWrite:false,sizeAttenuation:false,toneMapped:false}));positionMarker.scale.set(.045,.045,1);positionMarker.renderOrder=10;group.add(positionMarker);
  let cached=-1,path=trajectory(1);const selectPath=(value:number)=>{if(value===cached)return;cached=value;path=trajectory(value);geo.dispose();geo=new THREE.BufferGeometry().setFromPoints(path.pts.map(([x,y])=>new THREE.Vector3(x,0,y)));line.geometry=geo;};
  const limit=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(Array.from({length:48},(_,i)=>new THREE.Vector3(.14*Math.cos(i/48*Math.PI*2),0,.14*Math.sin(i/48*Math.PI*2)))),new THREE.LineBasicMaterial({color:0xaa8c5c,transparent:true,opacity:.6}));group.add(limit);
  return {group,inspect(){return {speed:cached,lineVertices:line.geometry.getAttribute('position')?.count,body:body.position.toArray(),velocityDirection:new THREE.Vector3(0,1,0).applyQuaternion(velocity.quaternion).toArray(),gravityDirection:new THREE.Vector3(0,1,0).applyQuaternion(gravity.quaternion).toArray(),classification:path.kind};},camera:[0,3.1,5.1],cameraForValue:(value,aspect)=>{selectPath(value);const radius=Math.max(...path.pts.map(p=>Math.hypot(...p))),d=(radius+.65)/Math.sin(Math.PI*21/180)/Math.min(1,aspect);return [0,d*.82,d*.57];},update({value,phase}){selectPath(value);const sample=trajectoryAt(path,phase),p=sample.position;body.position.set(p[0],0,p[1]);positionMarker.position.copy(body.position);const a=path.pts[sample.index],b=path.pts[Math.min(path.pts.length-1,sample.index+1)],dir=new THREE.Vector3(b[0]-a[0],0,b[1]-a[1]);velocity.visible=dir.lengthSq()>1e-12&&!(value===0&&phase===0);velocity.position.copy(body.position);velocity.setDirection(dir.normalize());gravity.position.copy(body.position);gravity.setDirection(body.position.clone().negate().normalize());}};
}
function earthLayers():Exhibit{return earthLayersScene();}
function atmosphere():Exhibit{return atmosphereScene();}
function magnetosphere():Exhibit{return magnetosphereScene();}

const galaxyStageSize=(stage:HTMLElement)=>{const desired=emissionSize(stage.clientWidth,stage.dataset.cosmosQuality==='low'?'low':'auto');return emissionReady(desired)?desired:(Number(stage.dataset.galaxySeedSize)||1536) as import('./galaxy-emission').EmissionSize;};
export const visualCatalog:Record<string,{make:(stage:HTMLElement)=>Exhibit;assets?:boolean;galaxies?:boolean;galaxyStars?:boolean;stellar?:'surface'|'cloud'|'nebula';preserveSvg?:boolean;legend?:string}>={
 'galaxias-e-nebulosas-via-lactea':{make:stage=>address(galaxyStageSize(stage)),assets:true,galaxies:true},
 'galaxias-e-nebulosas-tipos':{make:stage=>{const size=galaxyStageSize(stage);return galaxyLayers(starsOnlyReady(size)?size:Number(stage.dataset.galaxySeedSize) as import('./galaxy-emission').EmissionSize);},galaxies:true,galaxyStars:true},
 'galaxias-e-nebulosas-teia-cosmica':{make:stage=>web(galaxyStageSize(stage)),galaxies:true},
 'galaxias-e-nebulosas-nebulosas':{make:nebula,stellar:'nebula'},
 'galaxias-e-nebulosas-gas-e-estrelas':{make:lightJourney,assets:true},
 'galaxias-e-nebulosas-centros-galacticos':{make:stage=>horizon(galaxyStageSize(stage)),galaxies:true,preserveSvg:true},
 'origem-do-universo-o-universo':{make:stage=>expansion(()=>0,()=>false,galaxyStageSize(stage)),galaxies:true,preserveSvg:true},
 'origem-do-universo-fase-quente':{make:atoms,preserveSvg:true,legend:'Laranja: prótons. Cinza: nêutrons. Azul: elétrons, livres nas primeiras etapas e ligados simbolicamente no final. Quantidades e tamanhos esquemáticos; sem órbitas planetárias de elétrons.'},
 'origem-do-universo-primeiras-estruturas':{make:firstStructures,preserveSvg:true,stellar:'cloud'},
 'vida-das-estrelas-colapso':{make:collapse,stellar:'cloud'},
 'vida-das-estrelas-sol':{make:sunLayers,stellar:'surface'},
 'vida-das-estrelas-pequenas-e-medias':{make:stellarPair,stellar:'cloud'},
 'vida-das-estrelas-massivas':{make:massive,stellar:'cloud',legend:'Estrela de nêutrons OU buraco negro: destinos possíveis de caminhos distintos, não um sistema duplo. O gás ilustrado pertence ao caminho da estrela de nêutrons.'},
 'sistema-solar-disco':{make:solarDisk,assets:true,stellar:'cloud'},
 'sistema-solar-gigantes':{make:giant,assets:true,preserveSvg:true},
 'sistema-solar-pequenos-corpos':{make:comet,legend:'Azul: cauda de gás ionizado. Âmbar: cauda de poeira, mais curva. Comprimentos e larguras ampliados para leitura; ambas são empurradas para longe do Sol.'},
 'sistema-solar-orbitas':{make:orbit,assets:true,legend:'Seta azul: direção do movimento. Âmbar: direção da gravidade. Os comprimentos são ilustrativos; não comparam intensidade. O marcador claro mostra a posição do corpo, ampliada para leitura. O círculo central marca o limite ilustrativo de queda; a câmera enquadra a trajetória.'},
 'terra-e-atmosfera-formacao-da-terra':{make:earthLayers,assets:true},
 'terra-e-atmosfera-camadas':{make:atmosphere,assets:true,preserveSvg:true},
 'terra-e-atmosfera-campo-magnetico':{make:magnetosphere,assets:true}
};
export function updateExhibit(scene:Exhibit,state:VisualState){scene.update(state);}
void colors;




