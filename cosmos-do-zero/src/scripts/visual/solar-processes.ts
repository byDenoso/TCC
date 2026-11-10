import * as THREE from 'three';
import type {Exhibit} from './runtime';
import {createWorldFactory} from './assets';
import {distantStar,cloudFactory,stellarFactory} from './stellar-materials';
import {cometPosition} from '../micro/sistema';
const neutral={neutral:true,ambient:.45,key:3.2,fill:.12,exposure:1.1};

const dustNoise = `
float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3. - 2. * f);
  return mix(mix(hash(i), hash(i + vec2(1., 0.)), f.x),
             mix(hash(i + vec2(0., 1.)), hash(i + 1.), f.x), f.y);
}
`;

const textureVertex = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.);
}
`;

function dustDisk(): THREE.Mesh<THREE.PlaneGeometry, THREE.ShaderMaterial> {
 const mesh = new THREE.Mesh(new THREE.PlaneGeometry(5.4, 5.4), new THREE.ShaderMaterial({
  transparent: true, side: THREE.DoubleSide, depthWrite: false,
  blending: THREE.AdditiveBlending, toneMapped: false, uniforms: {uOpacity:{value:0}},
  vertexShader: textureVertex,
  fragmentShader: `
   varying vec2 vUv;
   uniform float uOpacity;
   ${dustNoise}
   void main() {
    vec2 p = (vUv - .5) * 2.;
    float r = length(p);
    float falloff = smoothstep(.055, .15, r) * (1. - smoothstep(.66, 1., r));
    if (falloff <= .001) discard;
    float theta = r < .01 ? 0. : atan(p.y, p.x);
    float spiral = theta - 2.5 * log(r + .05);
    vec2 streaks = vec2(cos(spiral), sin(spiral));
    float density = .5 * noise(streaks * 7. + r * 23.) + .3 * noise(p * 64.) + .2 * noise(p * 140.);
    vec3 color = mix(vec3(.78, .43, .19), vec3(.18, .16, .19), smoothstep(.14, .92, r));
    gl_FragColor = vec4(color, falloff * density * uOpacity * (1.2 - r));
    #include <colorspace_fragment>
   }`
 }));
 mesh.rotation.x = -Math.PI / 2;
 return mesh;
}

/** Formation is a sequence of illustrations, not a hydrodynamic integration. */
export function diskScene():Exhibit{
 const group=new THREE.Group(),make=createWorldFactory(),sun=stellarFactory()(0xffd5a1),cloud=cloudFactory()(),planets=new THREE.Group(),disk=dustDisk();
 const grainCount=180;
 const grains=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(.018,1),new THREE.MeshStandardMaterial({roughness:1}),grainCount);
 const grainPose=new THREE.Object3D();
 const accretions=Array.from({length:grainCount},(_,i)=>{
  const radius=.32+Math.sqrt((i+.5)/grainCount)*2.1,angle=i*2.399;
  const color=new THREE.Color(radius<1.3?0xb98964:0x9eb4c5).multiplyScalar(.48+(i%9)*.068);
  grains.setColorAt(i,color);
  return {position:new THREE.Vector3(Math.cos(angle)*radius,Math.sin(i*5)*.045,Math.sin(angle)*radius),size:.44+(i%7)*.15};
 });
 grains.frustumCulled=false;
 group.add(cloud,disk,sun,grains,planets);
 const worlds=['mercurio','venus','terra','marte','jupiter','saturno','urano','netuno'].map((name,i)=>{const p=make(name),r=.65+i*.25,a=i*2;p.scale.setScalar(i<4?.08:.16);p.position.set(Math.cos(a)*r,0,Math.sin(a)*r);planets.add(p);return p;});
 const iceLine=new THREE.Line(new THREE.BufferGeometry().setFromPoints(Array.from({length:129},(_,i)=>new THREE.Vector3(1.3*Math.cos((i%128)/128*Math.PI*2),.06,1.3*Math.sin((i%128)/128*Math.PI*2)))),new THREE.LineDashedMaterial({color:0x8cbbd6,dashSize:.08,gapSize:.05,transparent:true,opacity:.7}));iceLine.computeLineDistances();group.add(iceLine);
 const cloudUniforms=(cloud.material as THREE.ShaderMaterial).uniforms;
 cloudUniforms.uEdgeFade.value=.28;
 return {
  group,lighting:neutral,camera:[0,3.5,6.6],cameraForAspect:a=>a<1.5?[0,4,7.4]:[0,3.5,6.6],
  labels:[{text:'linha do gelo · posição ilustrativa',position:new THREE.Vector3(1.3,.07,0),visible:()=>iceLine.visible}],
  quality(mode,width){make.quality(mode==='low'?512:width<600?1024:2048);cloudUniforms.uSteps.value=mode==='low'?18:width<600?26:38;},
  update({value,phase}){
   const step=Math.round(value),collapse=step===1?phase:1;
   cloud.visible=step<3;
   cloud.scale.set(2.5,step===0?1.5:1.5*(1-collapse)+.16*collapse,2.5);
   cloud.rotation.y=phase*(step===0?.18:.4);
   cloudUniforms.uOpacity.value=step<2?.72:.27;
   disk.visible=step>0;
   disk.material.uniforms.uOpacity.value=step===1?.66*collapse:step===2?.66:.19;
   disk.rotation.z=phase*.22;
   sun.visible=step>0;
   sun.scale.setScalar(step===1?.14+phase*.08:.22);
   grains.visible=step===2;
   if(grains.visible){
    grains.rotation.y=phase*.22;
    accretions.forEach(({position,size},i)=>{
     grainPose.position.copy(position);
     grainPose.scale.setScalar(size*(.68+phase*.55));
     grainPose.updateMatrix();
     grains.setMatrixAt(i,grainPose.matrix);
    });
    grains.instanceMatrix.needsUpdate=true;
   }
   iceLine.visible=step>=2;
   planets.visible=step===3;
   worlds.forEach(world=>world.rotation.y=phase*.3);
  }
 };
}
/** A continuous pressure/composition schematic; no physical depth solution or solid surface. */
export function giantScene():Exhibit{
 const group=new THREE.Group(),make=createWorldFactory(),body=make('jupiter'),cut=make('jupiter');body.scale.setScalar(.7);body.position.x=-1.2;cut.position.x=1.05;group.add(body,cut);
 cut.traverse(o=>{const mesh=o as THREE.Mesh;if(!mesh.isMesh)return;const geometry=mesh.geometry.clone(),p=geometry.getAttribute('position'),index=geometry.index,kept:number[]=[];for(let i=0;i<(index?.count??p.count);i+=3){const ids=[0,1,2].map(k=>index?index.getX(i+k):i+k),x=ids.reduce((s,j)=>s+p.getX(j),0),z=ids.reduce((s,j)=>s+p.getZ(j),0);if(!(x<0&&z>0))kept.push(...ids);}geometry.setIndex(kept);mesh.geometry=geometry;});
 const faceMaterial=new THREE.ShaderMaterial({
  side:THREE.DoubleSide,uniforms:{uDepth:{value:0}},vertexShader:textureVertex,
  fragmentShader:`
   uniform float uDepth;
   varying vec2 vUv;
   ${dustNoise}
   void main() {
    vec2 p = (vUv - .5) * 2.;
    float r = length(p);
    float angle = r < .01 ? 0. : atan(p.y, p.x);
    float structure = noise(vec2(angle * 9., r * 48.));
    float variation = .88 + .14 * structure + .08 * noise(p * 130.);
    vec3 interior = mix(vec3(.21, .135, .13), vec3(.46, .26, .15), smoothstep(.05, .58, r));
    vec3 atmosphere = mix(vec3(.65, .36, .16), vec3(.9, .72, .49), smoothstep(.79, 1., r));
    vec3 color = mix(interior, atmosphere, smoothstep(.48, .98, r + (structure - .5) * .045));
    float selected = exp(-pow((1. - r - uDepth) / .045, 2.));
    gl_FragColor = vec4(color * variation * (.69 + .28 * selected), 1.);
    #include <colorspace_fragment>
   }`
 });
 for(const angle of[Math.PI/2,Math.PI*2]){const face=new THREE.Mesh(new THREE.CircleGeometry(.985,96,-Math.PI/2,Math.PI),faceMaterial);face.rotation.y=angle+Math.PI;cut.add(face);}
 const probe=new THREE.Mesh(new THREE.IcosahedronGeometry(.045,1),new THREE.MeshBasicMaterial({color:0xf3c77e}));cut.add(probe);const positionLabel={text:'nuvens · sem chão',object:probe,position:probe.position};
 return {group,lighting:neutral,camera:[-1,1.3,5.8],labels:[{text:'Júpiter',position:new THREE.Vector3(-1.2,-.83,0)},positionLabel],quality(mode,width){make.quality(mode==='low'?512:width<600?1024:2048);},update({value}){probe.position.set(-.03,.97*(1-value),.07);faceMaterial.uniforms.uDepth.value=value;positionLabel.text=value<.12?'nuvens · sem chão':value<.15?'nível de 1 bar':value<.75?'hidrogênio comprimido':value<.93?'hidrogênio condutor':'núcleo difuso? · inferido';}};
}
function rockyNoise(x:number,y:number,z:number):number {
 const hash=(a:number,b:number,c:number)=>{
  const seed=(Math.imul(a,374761393)+Math.imul(b,668265263)+Math.imul(c,1442695041))|0;
  const scrambled=Math.imul(seed^(seed>>>13),1274126177);
  return ((scrambled^(scrambled>>>16))>>>0)/4294967296;
 };
 const ix=Math.floor(x),iy=Math.floor(y),iz=Math.floor(z);
 const smooth=(t:number)=>t*t*(3-2*t);
 const [fx,fy,fz]=[smooth(x-ix),smooth(y-iy),smooth(z-iz)];
 const lerp=THREE.MathUtils.lerp;
 const slab=(k:number)=>lerp(lerp(hash(ix,iy,k),hash(ix+1,iy,k),fx),lerp(hash(ix,iy+1,k),hash(ix+1,iy+1,k),fx),fy);
 return lerp(slab(iz),slab(iz+1),fz);
}

function cometNucleus(): THREE.Mesh {
 const geometry=new THREE.SphereGeometry(1,72,48);
 const position=geometry.getAttribute('position');
 const colors=new Float32Array(position.count*3);
 const normal=new THREE.Vector3();
 const lobeRadius=(center:number,sx:number,sy:number,sz:number)=>{
  const a=(normal.x/sx)**2+(normal.y/sy)**2+(normal.z/sz)**2;
  const b=-2*normal.x*center/sx**2;
  const c=(center/sx)**2-1;
  return (-b+Math.sqrt(b*b-4*a*c))/(2*a);
 };
 for(let i=0;i<position.count;i++){
  normal.fromBufferAttribute(position,i).normalize();
  const {x,y,z}=normal;
  const body=lobeRadius(-.36,.7,.56,.49),head=lobeRadius(.4,.48,.49,.4);
  const seam=Math.max(0,.17-Math.abs(body-head));
  const lumps=.21*(rockyNoise(x*4,y*4,z*4)-.5)+.08*(rockyNoise(x*12,y*12,z*12)-.5);
  const radius=.108*(Math.max(body,head)+seam*seam/.68+lumps);
  position.setXYZ(i,x*radius,y*radius,z*radius);
  const shade=.47+.32*rockyNoise(x*13,y*13,z*13)+.18*rockyNoise(x*31,y*31,z*31);
  colors.set([shade,shade,shade],i*3);
 }
 geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));
 geometry.computeVertexNormals();
 return new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x938c82,vertexColors:true,roughness:1}));
}

function cometComa():THREE.Sprite {
 const canvas=document.createElement('canvas');
 canvas.width=canvas.height=64;
 const context=canvas.getContext('2d')!;
 const glow=context.createRadialGradient(32,32,0,32,32,32);
 glow.addColorStop(0,'#f5e5c1bd');
 glow.addColorStop(.17,'#deecdb8c');
 glow.addColorStop(.42,'#8cb9ac32');
 glow.addColorStop(1,'#8cb9ac00');
 context.fillStyle=glow;
 context.fillRect(0,0,64,64);
 const map=new THREE.CanvasTexture(canvas);
 map.colorSpace=THREE.SRGBColorSpace;
 return new THREE.Sprite(new THREE.SpriteMaterial({map,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
}

const tailSamples=43,tailSheets=3;
function cometTail(color:THREE.ColorRepresentation,filament:boolean):THREE.Mesh<THREE.BufferGeometry,THREE.ShaderMaterial> {
 const geometry=new THREE.BufferGeometry();
 const positions=new Float32Array(tailSheets*tailSamples*2*3);
 const uvs:number[]=[],indices:number[]=[];
 for(let sheet=0;sheet<tailSheets;sheet++)for(let i=0;i<tailSamples;i++){
  uvs.push(i/(tailSamples-1),0,i/(tailSamples-1),1);
  if(i<tailSamples-1){
   const k=(sheet*tailSamples+i)*2;
   indices.push(k,k+1,k+2,k+1,k+3,k+2);
  }
 }
 geometry.setAttribute('position',new THREE.BufferAttribute(positions,3).setUsage(THREE.DynamicDrawUsage));
 geometry.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));
 geometry.setIndex(indices);
 const material=new THREE.ShaderMaterial({
  side:THREE.DoubleSide,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false,
  uniforms:{uColor:{value:new THREE.Color(color)},uActivity:{value:0},uIon:{value:filament?1:0}},
  vertexShader:textureVertex,
  fragmentShader:`
   uniform vec3 uColor;
   uniform float uActivity, uIon;
   varying vec2 vUv;
   ${dustNoise}
   void main() {
    float along = vUv.x, width = (vUv.y - .5) * 2.;
    float broad = noise(vec2(along * 13., width * 6.));
    float fine = noise(vec2(along * 18., width * 40. + broad * 1.2));
    float spine = exp(-width * width * mix(4., 11., uIon));
    float rays = mix(.64 + .36 * broad, .4 + .6 * fine, uIon);
    float a = (1. - smoothstep(.2, 1., along)) * (1. - smoothstep(.72, 1., abs(width))) * spine * rays;
    gl_FragColor = vec4(uColor, a * uActivity * .31);
    #include <colorspace_fragment>
   }`
 });
 const tail=new THREE.Mesh(geometry,material);
 tail.frustumCulled=false;
 return tail;
}

export function cometScene():Exhibit{
 const group=new THREE.Group(),sun=distantStar(0xffd6a1);
 const [periX,centerY,,semiminor]=cometPosition(0);
 const [aphelionX]=cometPosition(.5);
 const semimajor=(aphelionX-periX)/2,centerX=periX+semimajor,scale=95;
 const position=(value:number)=>{
  const [x,y,vx,vy]=cometPosition(value);
  return [(x-centerX)/scale,(y-centerY)/scale,vx,vy] as const;
 };
 sun.scale.setScalar(1.2);
 sun.position.x=-Math.sqrt(semimajor**2-semiminor**2)/scale;
 const sunlight=new THREE.PointLight(0xffe1b6,.62);
 sunlight.position.copy(sun.position);
 const nucleus=cometNucleus(),coma=cometComa();
 const closeup=nucleus.clone();
 closeup.position.set(2.45,1.1,-.3);
 closeup.scale.setScalar(4);
 const gas=cometTail(0x4e84d0,true),dust=cometTail(0xd5a971,false);
 const orbit=new THREE.Line(new THREE.BufferGeometry().setFromPoints(Array.from({length:181},(_,i)=>{
  const [x,y]=position(i/180);
  return new THREE.Vector3(x,0,y);
 })),new THREE.LineBasicMaterial({color:0x65768a,transparent:true,opacity:.46}));
 const tailAnchor=new THREE.Object3D();
 group.add(sun,sunlight,nucleus,closeup,coma,gas,dust,orbit,tailAnchor);
 group.position.x=.5;
 const away=new THREE.Vector3(),behind=new THREE.Vector3(),perp=new THREE.Vector3(),center=new THREE.Vector3();
 const tailLabel={text:'cauda iônica · para longe do Sol',object:tailAnchor,position:tailAnchor.position,visible:()=>gas.visible};
 return {
  group,lighting:{...neutral,ambient:.46,key:.45,fill:0},camera:[0,3.6,6.5],
  cameraForAspect:aspect=>[0,3.6,6.5*Math.max(1,1.5/aspect)],
  labels:[
   {text:'Sol',object:sun,position:sun.position},tailLabel,
   {text:'Núcleo ampliado',object:closeup,position:closeup.position,pixelOffset:[0,27]}
  ],
  update({value}){
   const [x,y,vx,vy]=position(value);
   nucleus.position.set(x,0,y);
   nucleus.rotation.set(.19,value*6,-.3);
   closeup.rotation.copy(nucleus.rotation);
   away.copy(nucleus.position).sub(sun.position);
   const distance=away.length(),length=Math.min(1.9,1/Math.max(.12,distance**2));
   const activity=THREE.MathUtils.smoothstep(length,.075,.65);
   away.normalize();
   behind.set(-vx,0,-vy).normalize();
   perp.set(-away.z,0,away.x);
   gas.visible=dust.visible=coma.visible=activity>.005;
   coma.position.copy(nucleus.position);
   coma.scale.setScalar(.2+.39*activity);
   coma.material.opacity=.64*activity;
   if(gas.visible)for(const [mesh,curvature,width] of [[gas,0,.12],[dust,.35,.23]] as const){
    const positions=mesh.geometry.getAttribute('position');
    mesh.material.uniforms.uActivity.value=activity;
    for(let i=0;i<tailSamples;i++){
     const t=i/(tailSamples-1);
     center.copy(nucleus.position).addScaledVector(away,length*t).addScaledVector(behind,length*t*t*curvature);
     const extent=width*(.19+t)*Math.sqrt(length);
     for(let sheet=0;sheet<tailSheets;sheet++){
      const angle=sheet*Math.PI/tailSheets;
      for(let j=0;j<2;j++){
       const spread=(j?1:-1)*extent,across=spread*Math.cos(angle);
       positions.setXYZ((sheet*tailSamples+i)*2+j,center.x+perp.x*across,.025+spread*Math.sin(angle),center.z+perp.z*across);
      }
     }
    }
    positions.needsUpdate=true;
   }
   tailAnchor.position.copy(nucleus.position).addScaledVector(away,length*.75);
  }
 };
}
