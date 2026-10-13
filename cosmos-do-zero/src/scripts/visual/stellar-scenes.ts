import * as THREE from 'three';
import type { Exhibit } from './runtime';
import { stellarFactory,cloudFactory,lightStars } from './stellar-materials';
import { stellarPath,orbColor,mainSequenceRadius } from '../../lib/stars';
const color=(mesh:THREE.Mesh,value:THREE.ColorRepresentation)=>{((mesh.material as THREE.ShaderMaterial).uniforms.uColor.value as THREE.Color).set(value);mesh.children.forEach(o=>{if(o instanceof THREE.Sprite)o.material.color.set(value);});};
const quality=(meshes:THREE.Mesh[])=> (mode:'auto'|'low',width:number)=>{meshes.forEach(m=>(m.material as THREE.ShaderMaterial).uniforms.uSteps.value=mode==='low'?18:width<600?26:38);};
export function nebulaScene():Exhibit{
 const group=new THREE.Group(),cloud=cloudFactory(true)(),stars=lightStars(360),hot=lightStars(4);stars.renderOrder=0;cloud.renderOrder=1;cloud.scale.y=1.85;hot.renderOrder=2;(stars.material as THREE.PointsMaterial).size=.14;(stars.material as THREE.PointsMaterial).toneMapped=false;const pos=hot.geometry.getAttribute('position') as THREE.BufferAttribute;for(let i=0;i<4;i++)pos.setXYZ(i,.12+Math.sin(i*4)*.17,.2+Math.cos(i*6)*.12,.75);pos.needsUpdate=true;(hot.material as THREE.PointsMaterial).size=.22;const sky=new THREE.Mesh(new THREE.PlaneGeometry(9,6),new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{uOpacity:{value:.18}},vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',fragmentShader:'uniform float uOpacity;varying vec2 vUv;void main(){float light=exp(-dot(vUv-.5,vUv-.5)*9.);gl_FragColor=vec4(.20,.23,.30,light*uOpacity);}'}));sky.position.z=-3.8;sky.renderOrder=-1;group.add(sky,stars,cloud,hot);
 return {group,camera:[0,.25,6.4],cameraForAspect:a=>a<1?[0,.3,6.8]:[0,.25,6.4],quality:quality([cloud]),update({value}){(cloud.material as THREE.ShaderMaterial).uniforms.uMode.value=value;(sky.material as THREE.ShaderMaterial).uniforms.uOpacity.value=.4;}};
}
export function collapseScene():Exhibit{
 const group=new THREE.Group(),cloud=cloudFactory()(),star=stellarFactory()(0xffebd4);group.add(cloud,star);
 return {group,camera:[0,1.3,6.8],cameraForAspect:a=>a<1?[0,1.6,8]:[0,1.3,6.8],quality:quality([cloud]),update({value,phase}){
  const step=Math.round(value),s=[1,.75,.65,.55][step];cloud.scale.set(2.2*s,step>=2?.13:1.55*s,1.35*s);(cloud.material as THREE.ShaderMaterial).uniforms.uOpacity.value=step===0?1:step===1?.8:.65;
  star.visible=step>0;star.scale.setScalar(step===1?.17+phase*.04:step===2?.25:.38);color(star,step===1?0xcc6f44:step===2?0xf3b577:0xfff4e7);
 }};
}
export function sunLayersScene():Exhibit{
 const group=new THREE.Group(),make=stellarFactory(),surface=make(),cut=make();cut.geometry=new THREE.SphereGeometry(1,64,32,Math.PI/2,Math.PI*1.5);group.add(surface,cut);
 const radii=[0,.25,.71,1],colors=[0xfff2c3,0xe1b87f,0xc88d55],faces=new THREE.Group();group.add(faces);
 for(let i=0;i<3;i++)for(const phi of[Math.PI/2,Math.PI*2]){
 const material=new THREE.ShaderMaterial({side:THREE.DoubleSide,uniforms:{uColor:{value:new THREE.Color(colors[i])},uZone:{value:i},uSelected:{value:1},uGrain:{value:(surface.material as THREE.ShaderMaterial).uniforms.uGrain.value}},
 vertexShader:'varying vec2 vUv;varying vec3 vNormal;void main(){vUv=uv;vNormal=normalize(normalMatrix*normal);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
 fragmentShader:`uniform vec3 uColor;uniform float uZone;uniform float uSelected;uniform sampler2D uGrain;varying vec2 vUv;varying vec3 vNormal;void main(){vec2 p=vUv*2.-1.;float r=length(p),a=atan(p.y,p.x);float fine=texture2D(uGrain,vec2(fract(a/6.283+ r*.25),fract(r*.55))).r;float flow=(texture2D(uGrain,vec2(fract(vUv.x*1.7),fract(vUv.y*1.3))).r-.8)*.10;float depth=.68+.32*abs(dot(normalize(vNormal),normalize(vec3(-.8,.5,1.))));vec3 c=uColor*(.68+.32*pow(fine,3.)+flow)*(.94+.06*(1.-r))*depth*uSelected;gl_FragColor=vec4(c,1.);
#include <colorspace_fragment>
}`});
 const face=new THREE.Mesh(new THREE.RingGeometry(radii[i],radii[i+1],96,4,-Math.PI/2,Math.PI),material);face.rotation.y=phi+Math.PI;faces.add(face);}
 const core=new THREE.Mesh(new THREE.SphereGeometry(.25,48,24),new THREE.MeshBasicMaterial({color:0xffedc3}));group.add(core);
 const points=Array.from({length:100},(_,i)=>{const r=.26+i/99*.44,a=i*2.39;return new THREE.Vector3(-r*.7+Math.sin(a)*.055,Math.sin(i*1.53)*.11,r*.7+Math.cos(a)*.055);});
 const track=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0xfff0bc,transparent:true,opacity:.65}));group.add(track);
 const energy=new THREE.Mesh(new THREE.SphereGeometry(.025,12,8),new THREE.MeshBasicMaterial({color:0xffffff}));group.add(energy);
 const flows=new THREE.Group();group.add(flows);for(let i=0;i<4;i++){const x=-.42-i*.10;const curve=new THREE.EllipseCurve(0,0,.055,.11,0,Math.PI*2,false,0).getPoints(50);const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.map(p=>new THREE.Vector3(x+p.x,.30+p.y,.60+i*.03))),new THREE.LineBasicMaterial({color:i%2?0x83b3d5:0xffe4a1}));flows.add(line);}
 return {group,lighting:{ambient:.25,key:2,fill:.28,exposure:1.05,neutral:true},camera:[-1.7,1.4,4.1],cameraForAspect:a=>a<1?[-1.35,1.1,3.7]:[-1.7,1.4,4.1],update({value,phase}){const v=Math.round(value);surface.visible=v===3;cut.visible=faces.visible=core.visible=v<3;track.visible=energy.visible=v===1;flows.visible=v===2;track.geometry.setDrawRange(0,Math.max(2,Math.floor(phase*100)));energy.position.copy(points[Math.min(99,Math.floor(phase*99))]);faces.children.forEach((f,i)=>(f as THREE.Mesh<THREE.BufferGeometry,THREE.ShaderMaterial>).material.uniforms.uSelected.value=Math.floor(i/2)===v?1.16:.80);}};
}
export function stellarPairScene():Exhibit{
 const group=new THREE.Group(),make=stellarFactory(),sun=make(),red=make(0xdb7050),shell=cloudFactory()();sun.position.x=-1.15;red.position.x=1.15;shell.position.x=-1.15;group.add(sun,red,shell);
 const left={text:'estrela como o Sol',position:new THREE.Vector3(-1.15,-.6,0)},right={text:'anã vermelha',position:new THREE.Vector3(1.15,-.55,0)};
 return {group,labels:[left,right],camera:[0,.9,6.7],cameraForAspect:a=>a<1?[0,.9,8.3]:[0,.9,6.7],quality:quality([shell]),update({value,phase}){const v=Math.round(value);sun.scale.setScalar([.42,.50,.95,.20,.15][v]);red.scale.setScalar(v===4?.15:.23);color(sun,v===2?0xea9272:v>=3?0xd9e7ff:0xffffff);color(red,v===4?0xcbd6e4:0xdb7050);shell.visible=v===3;shell.scale.setScalar(.85+phase*.65);(shell.material as THREE.ShaderMaterial).uniforms.uShell.value=.55+phase*.3;(shell.material as THREE.ShaderMaterial).uniforms.uMode.value=1;left.position.y=-sun.scale.x-.13;right.position.y=-red.scale.x-.13;(sun.material as THREE.ShaderMaterial).uniforms.uIntensity.value=v===4?.14:v===3?1.38:1;sun.children.forEach(o=>{if(o instanceof THREE.Sprite)o.material.opacity=v===4?.01:v===3?.22:.12;});left.text=v===4?'anã branca fria · prevista':v===3?'anã branca · ampliada':v===2?'gigante / perda de gás':'estrela como o Sol';right.text=v===4?'anã branca · prevista':'anã vermelha';}};
}
export function massiveScene(remnant:()=>Exhibit):Exhibit{
 const group=new THREE.Group(),star=stellarFactory()(0xbfcfff),end=remnant(),ejecta=cloudFactory()();group.add(star,end.group,ejecta);
 return {group,labels:end.labels,camera:[0,2,5.1],cameraForAspect:a=>a<1.4?[0,2.6,6.4]:[0,2,5.1],quality:quality([ejecta]),update(state){const v=Math.round(state.value);star.visible=v<3;star.scale.setScalar(v===1?1.3:v===2?1.3-state.phase*.95:.75);color(star,v===1?0xec9d7b:0xbfcfff);end.group.visible=v===3;end.update(state);ejecta.visible=v===3;ejecta.position.x=-1.55;ejecta.scale.setScalar(.55+state.phase*.35);(ejecta.material as THREE.ShaderMaterial).uniforms.uMode.value=1;(ejecta.material as THREE.ShaderMaterial).uniforms.uShell.value=.65;(ejecta.material as THREE.ShaderMaterial).uniforms.uOpacity.value=.22;}};
}
export function stellarMassScene(mass:()=>number,remnant:()=>Exhibit):Exhibit{
 const group=new THREE.Group(),makeCloud=cloudFactory(),cloud=makeCloud(),star=stellarFactory()(),shell=makeCloud(),end=remnant();group.add(cloud,star,shell,end.group);
 const label={text:'',position:new THREE.Vector3(0,-1.4,0)};
 return {group,labels:[label,...(end.labels??[])],camera:[0,1.6,7.2],quality:quality([cloud,shell]),update({value,phase}){const m=mass(),step=Math.round(value),path=stellarPath(m),c=orbColor(m);color(star,new THREE.Color().setRGB(c[0]/255,c[1]/255,c[2]/255,THREE.SRGBColorSpace));cloud.visible=step<2;cloud.scale.set(step===0?2.2:.9,step===0?1.55:.13,step===0?1.35:.7);star.visible=step>0&&!(step===4&&m>=8);star.scale.setScalar(step===1?.25:.35+Math.log1p(mainSequenceRadius(m))*.3);if(step===3&&m>=.6&&m<8){star.scale.setScalar(.75+phase*.7);color(star,0xea9474);}if(step===3&&m>=8)star.scale.setScalar(1.3-phase);if(step===4&&m<8){star.scale.setScalar(.24);color(star,0xd8e6ff);}shell.visible=step===4&&m>=.6&&m<8;shell.scale.setScalar(1+phase*.5);(shell.material as THREE.ShaderMaterial).uniforms.uShell.value=.55+phase*.25;(shell.material as THREE.ShaderMaterial).uniforms.uMode.value=1;end.group.visible=step===4&&m>=8;end.update({value:3,phase,elapsed:0});label.text=path.steps[step]+(m<.6&&step>=3?' · prevista':'');}};
}
