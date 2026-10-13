import * as THREE from 'three';
import type { Exhibit,VisualState } from './runtime';
import { galaxy } from './galaxy';
import { cosmicWeb } from './web';
import { horizon } from './horizon';
import { world } from './assets';
import { expansion } from './expansion';
import { cometPosition, trajectory,trajectoryAt } from '../micro/sistema';
import { orbColor,stellarPath,mainSequenceRadius } from '../../lib/stars';

const colors=[0xf6bb78,0x88b1e8,0xc97079,0x96cbbc];
const sphere=(r:number,col:number,emissive=false)=>new THREE.Mesh(new THREE.SphereGeometry(r,32,20),new THREE.MeshStandardMaterial({color:col,roughness:.85,emissive:emissive?col:0,emissiveIntensity:emissive?.4:0}));
function glowCloud(seed:number,color:number,radius=2,n=1200,spread=60,opacity=.18):THREE.Points{
  let s=seed;const random=()=>((s=(Math.imul(s,1664525)+1013904223)>>>0)/4294967296);
  const positions=new Float32Array(n*3);for(let i=0;i<n;i++){const a=random()*Math.PI*2,b=Math.acos(2*random()-1),r=radius*Math.cbrt(random());positions.set([Math.sin(b)*Math.cos(a)*r,Math.cos(b)*r,Math.sin(b)*Math.sin(a)*r],i*3);}
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(positions,3));
  return new THREE.Points(g,new THREE.ShaderMaterial({uniforms:{uColor:{value:new THREE.Color(color)},uSpread:{value:spread},uOpacity:{value:opacity}},transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    vertexShader:'uniform float uSpread;void main(){vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=clamp(uSpread/-p.z,2.,32.);}',
    fragmentShader:'uniform vec3 uColor;uniform float uOpacity;void main(){vec2 p=gl_PointCoord-.5;float r=dot(p,p);if(r>.25)discard;gl_FragColor=vec4(uColor,exp(-r*16.)*uOpacity);\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}'
  }));
}
const web=cosmicWeb;
function address():Exhibit{
  const group=new THREE.Group(),steps=Array.from({length:5},()=>new THREE.Group());steps.forEach(s=>group.add(s));
  steps[0].add(world('terra'));
  const sun=sphere(.38,0xe6ba69,true);steps[1].add(sun);
  ['mercurio','venus','terra','marte','jupiter','saturno','urano','netuno'].forEach((name,i)=>{const w=world(name);const a=i*1.7,r=.8+i*.26;w.scale.setScalar(i<4?.08:.15);w.position.set(Math.cos(a)*r,0,Math.sin(a)*r);steps[1].add(w);});
  steps[2].add(galaxy(55));steps[2].scale.setScalar(2.2);
  for(let i=0;i<6;i++){const g=galaxy(27+i,i%3===0?'elliptical':'spiral');g.scale.setScalar(i<2?.7:.22);g.position.set(Math.sin(i*3)*2,Math.cos(i*4)*.4,Math.cos(i*5)*1.5);steps[3].add(g);}
  const network=web();steps[4].add(network.group);steps[4].scale.setScalar(.6);network.update({value:1,phase:1,elapsed:0});
  return {group,camera:[0,2.7,7.4],update({value}){steps.forEach((s,i)=>s.visible=i===Math.round(value));}};
}
function galaxyLayers():Exhibit{
  const group=new THREE.Group(),spiral=galaxy(24),elliptical=galaxy(3,'elliptical'),gas=glowCloud(77,0x8e6d9e,.75,1200);
  const halo=new THREE.Mesh(new THREE.SphereGeometry(1.3,32,16),new THREE.MeshBasicMaterial({color:0x526b96,transparent:true,opacity:.06,depthWrite:false}));
  group.add(spiral,elliptical,gas,halo);group.rotation.x=.35;
  return {group,camera:[0,1.6,3.5],update({value}){spiral.visible=value<3;elliptical.visible=value>=3;gas.visible=value>=1&&value<3;halo.visible=value>=2&&value<3;}};
}
function nebula():Exhibit{
  const group=new THREE.Group(),cloud=glowCloud(7,0xc66589,1.9,900,125,.07),stars=new THREE.Group();group.add(cloud,stars);
  const positions=cloud.geometry.getAttribute('position') as THREE.BufferAttribute;
  for(let i=0;i<positions.count;i++){const lobe=i%3;const x=positions.getX(i)*.65+[-.6,.55,.1][lobe];const y=positions.getY(i)*.32+[.1,-.12,.45][lobe]+Math.sin(x*2)*.13;positions.setXYZ(i,x,y,positions.getZ(i)*.5+[0,-.35,.3][lobe]);}positions.needsUpdate=true;
  for(let i=0;i<12;i++){const star=new THREE.Mesh(new THREE.SphereGeometry(i===0?.025:.014,12,8),new THREE.MeshBasicMaterial({color:i===0?0xe7d2ad:0xd4bea1}));star.position.set(Math.sin(i*7)*1.8,Math.cos(i*8)*.6,Math.cos(i*3)*1.1);stars.add(star);if(i===0){const corona=glowCloud(7,0xc5bbab,.16,600);corona.position.copy(star.position);stars.add(corona);}}
  return {group,camera:[0,1.1,5.8],update({value,phase}){const m=cloud.material as THREE.ShaderMaterial;m.uniforms.uColor.value.set(value===0?0xa95072:value===1?0x5c85b9:0x1c1420);m.blending=value===2?THREE.NormalBlending:THREE.AdditiveBlending;cloud.scale.setScalar(.9+phase*.1);}};
}
function lightJourney():Exhibit{
 const group=new THREE.Group(),earth=world('terra'),photon=sphere(.055,0x90badd,true);
 earth.position.x=2;earth.scale.setScalar(.35);group.add(earth,photon);
 const sources=[world('lua'),sphere(.38,0xe0bb7b,true),sphere(.19,0xab4c35,true)];sources.forEach(s=>{s.position.x=-2;group.add(s);});sources[0].scale.setScalar(.25);
 const label={text:'Lua · 1,3 segundo',position:sources[0].position};
 return {group,labels:[label,{text:'Terra',position:earth.position}],camera:[0,1.3,6.5],update({value,phase}){
  const v=Math.min(2,Math.round(value));sources.forEach((s,i)=>s.visible=i===v);label.text=['Lua · 1,3 segundo','Sol · 8 min 20 s','Proxima Centauri · 4,2 anos'][v];photon.position.x=-1.6+phase*3.2;
 }};
}
function atoms():Exhibit{
  const group=new THREE.Group(),parts=Array.from({length:28},(_,i)=>{const p=sphere(i<4?.09:.07,i<4?0x8f99ad:0xc5684f);group.add(p);return p;});
  const clouds=Array.from({length:24},()=>new THREE.Mesh(new THREE.SphereGeometry(.19,16,10),new THREE.MeshBasicMaterial({color:0x74a8cf,transparent:true,opacity:.1,depthWrite:false})));clouds.forEach(c=>group.add(c));
  return {group,camera:[0,2,6],update({value,phase}){parts.forEach((p,i)=>{const bound=value>=1&&i<8,k=value===1?phase:1;
    const original=new THREE.Vector3(Math.sin(i*6.7)*2,Math.cos(i*3.9)*1.2,Math.cos(i*1.7));const cluster=i<4?Math.floor(i/2):Math.floor((i-4)/2);const target=new THREE.Vector3(cluster===0?-.6:.8,(i%2-.5)*.14,i<4?-.07:.07);p.position.copy(bound?original.lerp(target,k):original);
  });clouds.forEach((c,i)=>{c.visible=value>=3&&i!==1&&i!==3;c.position.copy(parts[i+4].position);});}};
}
function firstStructures():Exhibit{
 const group=new THREE.Group(),gas=new THREE.Group(),stars=new THREE.Group(),bubbles=new THREE.Group();group.add(gas,stars,bubbles);
 const clusters=Array.from({length:9},(_,i)=>new THREE.Vector3(Math.sin(i*7.1)*2.4,Math.cos(i*3.4)*.7,Math.cos(i*9.2)*1.6));
 clusters.forEach((p,i)=>{const g=glowCloud(i*33+7,0x7c86a3,.65,500);g.position.copy(p);gas.add(g);const s=sphere(.045,0xd6be8f,true);s.position.copy(p);stars.add(s);const b=new THREE.Mesh(new THREE.SphereGeometry(.7,24,16),new THREE.MeshBasicMaterial({color:0x6488b4,transparent:true,opacity:.055,depthWrite:false}));b.position.copy(p);bubbles.add(b);});
 return {group,camera:[0,2.7,8],update({value}){gas.children.forEach(g=>g.scale.setScalar(1-Math.min(.7,value)));stars.visible=value>.45;bubbles.visible=value>.55;bubbles.children.forEach(b=>b.scale.setScalar(Math.max(.02,(value-.55)*3)));}};
}
function collapse():Exhibit{
  const group=new THREE.Group(),cloud=glowCloud(99,0x85849f,2.5,2600),star=sphere(.5,0xcd864a,true);group.add(cloud,star);
  return {group,camera:[0,2.5,7],update({value,phase}){const shrink=[1,.7,.3,.18][Math.round(value)]??.18;cloud.scale.set(shrink, value>=2?shrink*.3:shrink,shrink);star.visible=value>=1;star.scale.setScalar(value>=2?.6:phase*.3);}};
}
function sunLayers():Exhibit{
  const group=new THREE.Group();const shells=[1,.72,.5,.25].map((r,i)=>{
    const m=new THREE.Mesh(new THREE.SphereGeometry(r,40,24,Math.PI,Math.PI*1.5),new THREE.MeshStandardMaterial({color:[0xdba64b,0xd07b35,0xb75131,0xeecf89][i],roughness:.9,side:THREE.DoubleSide,emissive:0x8d431d,emissiveIntensity:.15}));group.add(m);return m;
  });
  const energy=new THREE.Mesh(new THREE.SphereGeometry(.035,12,8),new THREE.MeshBasicMaterial({color:0xffecd0}));group.add(energy);
  return {group,camera:[1,1.7,4.4],update({value,phase}){shells.forEach((m,i)=>{const material=m.material as THREE.MeshStandardMaterial;material.emissiveIntensity=i===3-Math.round(value)?.65:.08;});const target=[.12,.52,.83,1.15][Math.round(value)];const r=target*(.7+.3*phase);energy.position.set(r*.72,Math.sin(phase*30)*.03,r*.72);}};
}
function stellarPair():Exhibit{
  const group=new THREE.Group(),sun=sphere(.42,0xe6b26c,true),red=sphere(.23,0xb34b30,true),shell=glowCloud(22,0x70a59d,.9,1700);
  const redLabel={text:'anã vermelha',position:red.position};
  sun.position.x=-1.4;red.position.x=1.4;shell.position.x=-1.4;group.add(sun,red,shell);
  return {group,labels:[{text:'estrela como o Sol',position:sun.position},redLabel],camera:[0,1.3,6.5],update({value,phase}){
    const v=Math.round(value),r=[1,1.2,2.8,.18,.18][v];sun.scale.setScalar(r);(sun.material as THREE.MeshStandardMaterial).color.set(v===2?0xb85435:v>=3?0x9aaebd:0xe6b26c);shell.visible=v===3;shell.scale.setScalar(phase);red.visible=true;red.scale.setScalar(v===4?.35:1);redLabel.text=v===4?'anã branca (prevista)':'anã vermelha';(red.material as THREE.MeshStandardMaterial).color.set(v===4?0x9caec5:0xb34b30);
  }};
}
export function blackHole():Exhibit{
  const group=new THREE.Group(),horizon=sphere(.44,0x030305),disk=new THREE.Mesh(new THREE.RingGeometry(.7,1.8,96,8),new THREE.MeshStandardMaterial({color:0xc88a46,emissive:0x704219,emissiveIntensity:.45,side:THREE.DoubleSide,roughness:.8}));
  disk.rotation.x=Math.PI/2;group.add(horizon,disk);
  const diskMat=disk.material as THREE.MeshStandardMaterial;
  diskMat.onBeforeCompile=(shader)=>{
    shader.vertexShader='varying vec2 vDisk;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvDisk=position.xy;');
    shader.fragmentShader='varying vec2 vDisk;\n'+shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\nfloat radius=length(vDisk);float noise=sin(vDisk.x*19.+sin(vDisk.y*9.))*sin(vDisk.y*31.+cos(vDisk.x*8.));diffuseColor.rgb*=mix(.4,1.2,clamp((1.8-radius)/1.1,0.,1.))*(.87+.13*noise);');
  };
  const node=sphere(.14,0x9eacc5,true);node.position.x=-2.6;group.add(node);group.position.x=.8;
  return {group,labels:[{text:'horizonte',position:new THREE.Vector3(.8,.1,0),visible:()=>group.visible&&horizon.visible},{text:'estrela de nêutrons',position:new THREE.Vector3(-1.8,0,0),visible:()=>group.visible&&node.visible}],camera:[0,4.5,6.5],update({value}){disk.visible=value>=3;horizon.visible=value>=3;node.visible=value>=3;}};
}
function massive():Exhibit{
  const group=new THREE.Group(),star=sphere(.75,0x8daacd,true),remnants=blackHole();group.add(star,remnants.group);
  return {group,camera:[0,4.5,6.5],labels:remnants.labels,update(state){star.visible=state.value<3;remnants.group.visible=state.value>=3;star.scale.setScalar(state.value===1?1.7:state.value===2?Math.max(.2,1.7-state.phase*1.5):1);(star.material as THREE.MeshStandardMaterial).color.set(state.value===1?0xcc744c:0x8daacd);remnants.update(state);}};
}
export function stellarMass(mass:()=>number):Exhibit{
 const group=new THREE.Group(),cloud=glowCloud(91,0x8b789a,2,2000),star=sphere(.7,0xd4ad6d,true),shell=glowCloud(42,0x739dad,1.5,1900),remnants=blackHole();group.add(cloud,star,shell,remnants.group);
 const label={text:'Sequência principal',position:new THREE.Vector3(0,-1.3,0)};
 return {group,labels:[label,...(remnants.labels??[])],camera:[0,3.3,7],update({value,phase}){
  const m=mass(),step=Math.round(value),path=stellarPath(m),c=orbColor(m),material=star.material as THREE.MeshStandardMaterial;
  material.color.setRGB(c[0]/255,c[1]/255,c[2]/255,THREE.SRGBColorSpace);material.emissive.copy(material.color);material.emissiveIntensity=.25;
  cloud.visible=step<=1;cloud.scale.set(step===0?1:.4,step===0?1:.15,step===0?1:.4);
  star.visible=step>0&&!(m>=8&&step===4);star.scale.setScalar(.45+Math.log1p(mainSequenceRadius(m))*.4);
  if(step===3&&m>=.6&&m<8){star.scale.setScalar(1+phase*.8);material.color.set(0xb55435);}
  if(step===3&&m>=8)star.scale.setScalar(Math.max(.25,1.5-phase));
  if(step===4&&m<8){star.scale.setScalar(.16);material.color.set(0x9eadbf);}
  shell.visible=step===4&&m>=.6&&m<8;shell.scale.setScalar(.6+phase*.4);
  remnants.group.visible=step===4&&m>=8;remnants.update({value:3,phase,elapsed:0});
  label.text=path.steps[step]+(m<.6&&step>=3?' · prevista':'');label.position.y=step===3?-1.7:-1.3;
 }};
}
function solarDisk():Exhibit{
  const group=new THREE.Group(),sun=sphere(.28,0xd7a253,true),cloud=glowCloud(82,0xa48570,2.5,2500),planets=new THREE.Group();group.add(sun,cloud,planets);
  ['mercurio','venus','terra','marte','jupiter','saturno','urano','netuno'].forEach((name,i)=>{const p=world(name);p.scale.setScalar(i<4?.1:.18);p.position.set(Math.cos(i*2)*(.7+i*.23),0,Math.sin(i*2)*(.7+i*.23));planets.add(p);});
  return {group,camera:[0,3,7],update({value}){cloud.visible=value<3;cloud.scale.y=value===0?.7:.09;planets.visible=value>=3;}};
}
function giant():Exhibit{
 const group=new THREE.Group(),body=world('jupiter');body.position.x=-1.3;body.scale.setScalar(.65);group.add(body);
 const cut=new THREE.Group();cut.position.x=1.1;group.add(cut);
 [.95,.75,.5,.24].forEach((r,i)=>cut.add(new THREE.Mesh(new THREE.SphereGeometry(r,32,20,Math.PI,Math.PI*1.5),new THREE.MeshStandardMaterial({color:[0xc6a06c,0xa4784b,0x686157,0x413c36][i],roughness:1,side:THREE.DoubleSide}))));
 const probe=sphere(.065,0xe8c48b,true);cut.add(probe);
 return {group,labels:[{text:'Júpiter: gás cada vez mais denso',position:body.position},{text:'sonda: profundidade ilustrativa',position:probe.position,object:probe}],camera:[0,1.5,6],update({value}){probe.position.set(0,.95-value*.8,.12);}};
}
function comet():Exhibit{
 const group=new THREE.Group(),sun=sphere(.18,0xe6b675,true),ice=sphere(.065,0x727b82);
 sun.position.x=-1.6;group.add(sun,ice);
 const gasGeo=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]),dustGeo=new THREE.BufferGeometry().setFromPoints(Array.from({length:24},()=>new THREE.Vector3()));
 const gas=new THREE.Line(gasGeo,new THREE.LineBasicMaterial({color:0x79addc})),dust=new THREE.Line(dustGeo,new THREE.LineBasicMaterial({color:0xbda16e}));group.add(gas,dust);
 const path=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(Array.from({length:160},(_,i)=>{const [x,y]=cometPosition(i/160);return new THREE.Vector3((x-260)/95,0,(y-135)/95);})),new THREE.LineBasicMaterial({color:0x455366,transparent:true,opacity:.55}));group.add(path);
 return {group,labels:[{text:'Sol',position:sun.position},{text:'gelo e poeira',position:ice.position}],camera:[0,3,7],update({value}){
  const [x,y,vx,vy]=cometPosition(value);ice.position.set((x-260)/95,0,(y-135)/95);
  const dir=ice.position.clone().sub(sun.position),dist=dir.length();dir.normalize();
  const length=Math.min(1.6,1/Math.max(.15,dist*dist));gas.visible=dust.visible=length>.09;
  const p=gasGeo.getAttribute('position') as THREE.BufferAttribute,end=ice.position.clone().addScaledVector(dir,length);p.setXYZ(0,ice.position.x,0,ice.position.z);p.setXYZ(1,end.x,0,end.z);p.needsUpdate=true;
  const tangent=new THREE.Vector3(-vx,0,-vy).normalize(),d=dustGeo.getAttribute('position') as THREE.BufferAttribute;
  for(let i=0;i<24;i++){const t=i/23;const point=ice.position.clone().addScaledVector(dir,length*t*.8).addScaledVector(tangent,length*t*t*.38);d.setXYZ(i,point.x,point.y,point.z);}d.needsUpdate=true;
 }};
}
function orbit():Exhibit{
  const group=new THREE.Group(),sun=sphere(.14,0xe6b675,true),body=world('terra');body.scale.setScalar(.06);group.add(sun,body);
  let geo=new THREE.BufferGeometry();const line=new THREE.Line(geo,new THREE.LineBasicMaterial({color:0x709dc9}));group.add(line);
  let cached=-1,path=trajectory(1);
  return {group,camera:[0,3.1,5.1],update({value,phase}){if(value!==cached){cached=value;path=trajectory(value);geo.dispose();geo=new THREE.BufferGeometry().setFromPoints(path.pts.map(([x,y])=>new THREE.Vector3(x,0,y)));line.geometry=geo;}const p=trajectoryAt(path,phase).position;body.position.set(p[0],0,p[1]);}};
}
function earthLayers():Exhibit{
 const group=new THREE.Group(),earth=world('terra');group.add(earth);
 const layers=[.98,.83,.53,.28].map((r,i)=>new THREE.Mesh(new THREE.SphereGeometry(r,32,20,Math.PI,Math.PI*1.5),new THREE.MeshStandardMaterial({color:[0x706247,0x965c3a,0xc6873e,0xd6b873][i],side:THREE.DoubleSide,roughness:1})));layers.forEach(l=>group.add(l));
 const mixture=new THREE.Group();group.add(mixture);const drops=Array.from({length:48},(_,i)=>{const iron=i<18,p=sphere(iron?.07:.09,iron?0x8a3d28:0xb3926a);mixture.add(p);return p;});
 return {group,camera:[1,1.3,4.2],update({value,phase}){
  const v=Math.round(value);earth.visible=v===3;layers.forEach(l=>l.visible=v===2);mixture.visible=v<2;
  drops.forEach((p,i)=>{const original=new THREE.Vector3(Math.sin(i*4.3)*.7,Math.cos(i*7.4)*.6,Math.sin(i*3.1)*.7);const target=original.clone().multiplyScalar(i<18?.23:1.2);p.position.copy(v===1?original.lerp(target,phase):original);});
 }};
}
function atmosphere():Exhibit{
  const group=new THREE.Group(),earth=world('terra');group.add(earth);const shells=[1.018,1.075,1.1275,1.18].map((r,i)=>new THREE.Mesh(new THREE.SphereGeometry(r,32,20),new THREE.MeshBasicMaterial({color:[0x719aba,0x927aaa,0x956d8b,0xb08b69][i],transparent:true,opacity:.1,depthWrite:false,side:THREE.BackSide})));shells.forEach(s=>group.add(s));
  const marker=sphere(.045,0xffbf87,true);group.add(marker);
  return {group,camera:[0,.9,4],labels:[{text:'espessura ampliada para ver as camadas',position:new THREE.Vector3(0,-1.3,0)}],update({value}){const r=1+value/120*.18;marker.position.set(r*.8,r*.6,0);shells.forEach((s,i)=>(s.material as THREE.MeshBasicMaterial).opacity=i===(value<12?0:value<50?1:value<85?2:3)?.23:.06);}};
}
function magnetosphere():Exhibit{
  const group=new THREE.Group(),earth=world('terra');earth.scale.setScalar(.55);group.add(earth);
  const field=new THREE.Group();group.add(field);
  for(let i=0;i<8;i++){const a=i/8*Math.PI*2,points:THREE.Vector3[]=[];for(let j=0;j<=80;j++){const t=j/80*Math.PI*2;points.push(new THREE.Vector3(Math.cos(t)*1.6+Math.cos(a)*.4,Math.sin(t)*.9*Math.cos(a),Math.sin(t)*.9*Math.sin(a)));}field.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0x457ca9,transparent:true,opacity:.6})));}
  const wind=Array.from({length:26},(_,i)=>{const p=sphere(.02,0xcdab65,true);p.position.y=Math.sin(i*3)*1.3;p.position.z=Math.cos(i*5)*.5;group.add(p);return p;});
  return {group,camera:[0,2.5,7],update({value,phase}){field.visible=value===0;wind.forEach((p,i)=>{const x=-3+((phase+i/26)%1)*6;p.position.x=x;p.position.y=Math.sin(i*3)*1.3+(value===0&&Math.abs(x)<1.4?(i%2?1:-1)*(.9-Math.abs(x)*.5):0);});}};
}

export const visualCatalog:Record<string,{make:()=>Exhibit;assets?:boolean;preserveSvg?:boolean}>={
 'galaxias-e-nebulosas-via-lactea':{make:address,assets:true},
 'galaxias-e-nebulosas-tipos':{make:galaxyLayers},
 'galaxias-e-nebulosas-teia-cosmica':{make:web},
 'galaxias-e-nebulosas-nebulosas':{make:nebula},
 'galaxias-e-nebulosas-gas-e-estrelas':{make:lightJourney,assets:true},
 'galaxias-e-nebulosas-centros-galacticos':{make:horizon,preserveSvg:true},
 'origem-do-universo-o-universo':{make:()=>expansion(()=>0,()=>false)},
 'origem-do-universo-fase-quente':{make:atoms},
 'origem-do-universo-primeiras-estruturas':{make:firstStructures,preserveSvg:true},
 'vida-das-estrelas-colapso':{make:collapse},
 'vida-das-estrelas-sol':{make:sunLayers},
 'vida-das-estrelas-pequenas-e-medias':{make:stellarPair},
 'vida-das-estrelas-massivas':{make:massive},
 'sistema-solar-disco':{make:solarDisk,assets:true},
 'sistema-solar-gigantes':{make:giant,assets:true},
 'sistema-solar-pequenos-corpos':{make:comet},
 'sistema-solar-orbitas':{make:orbit,assets:true},
 'terra-e-atmosfera-formacao-da-terra':{make:earthLayers,assets:true},
 'terra-e-atmosfera-camadas':{make:atmosphere,assets:true,preserveSvg:true},
 'terra-e-atmosfera-campo-magnetico':{make:magnetosphere,assets:true}
};
export function updateExhibit(scene:Exhibit,state:VisualState){scene.update(state);}
void colors;




