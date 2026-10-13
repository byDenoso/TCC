import * as THREE from 'three';
import { u } from '../../lib/url';
let grainLoading:Promise<void>|null=null,cloudLoading:Promise<void>|null=null,detailLoading:Promise<void>|null=null;
let grain:THREE.Texture,orion:THREE.Texture,density:THREE.Data3DTexture;
export async function prepareStellarMaterials(kind:'surface'|'cloud'|'nebula'='cloud'):Promise<void>{
 grainLoading??=new THREE.TextureLoader().loadAsync(u('/models/stellar/granulation.png')).then(map=>{grain=map;grain.colorSpace=THREE.NoColorSpace;});
 const jobs=[grainLoading];
 if(kind!=='surface'){cloudLoading??=fetch(u('/models/stellar/cloud-density-128.bin')).then(r=>{if(!r.ok)throw Error('cloud asset');return r.arrayBuffer();}).then(buffer=>{density=new THREE.Data3DTexture(new Uint8Array(buffer),128,128,128);density.format=THREE.RedFormat;density.type=THREE.UnsignedByteType;density.minFilter=density.magFilter=THREE.LinearFilter;density.unpackAlignment=1;density.needsUpdate=true;});jobs.push(cloudLoading);}
 if(kind==='nebula'){detailLoading??=new THREE.TextureLoader().loadAsync(u('/models/stellar/orion-detail.webp')).then(map=>{orion=map;orion.colorSpace=THREE.NoColorSpace;});jobs.push(detailLoading);}
 await Promise.all(jobs);
}
export function stellarFactory(){
 const map=grain.clone(),geometry=new THREE.SphereGeometry(1,64,32);
 const canvas=document.createElement('canvas');canvas.width=canvas.height=128;const ctx=canvas.getContext('2d')!,g=ctx.createRadialGradient(64,64,0,64,64,64);g.addColorStop(0,'#fff0');g.addColorStop(.70,'#fff0');g.addColorStop(.77,'#ffffff50');g.addColorStop(.85,'#ffffff15');g.addColorStop(1,'#fff0');ctx.fillStyle=g;ctx.fillRect(0,0,128,128);const haloMap=new THREE.CanvasTexture(canvas);
 return (color:THREE.ColorRepresentation=0xffffff)=>{const mesh=new THREE.Mesh(geometry,new THREE.ShaderMaterial({uniforms:{uGrain:{value:map},uColor:{value:new THREE.Color(color)},uIntensity:{value:1}},
 vertexShader:'varying vec2 vUv;varying vec3 n;varying vec3 p;void main(){vUv=uv;vec4 v=modelViewMatrix*vec4(position,1.);n=normalize(normalMatrix*normal);p=v.xyz;gl_Position=projectionMatrix*v;}',
 fragmentShader:'uniform sampler2D uGrain;uniform vec3 uColor;uniform float uIntensity;varying vec2 vUv;varying vec3 n;varying vec3 p;void main(){float mu=max(0.,dot(normalize(n),normalize(-p)));float grain=texture2D(uGrain,vUv).r;float light=(.15+.85*pow(mu,.58))*pow(grain,2.1);gl_FragColor=vec4(uColor*light*1.04*uIntensity,1.);\n#include <colorspace_fragment>\n}'
 }));const halo=new THREE.Sprite(new THREE.SpriteMaterial({map:haloMap,color,transparent:true,opacity:.12,depthWrite:false,blending:THREE.AdditiveBlending}));halo.scale.set(2.62,2.62,1);mesh.add(halo);return mesh;};
}
export function cloudFactory(observedDetail=false){const data=density.clone(),detail=observedDetail?orion.clone():null;return ()=>{
 const material=new THREE.ShaderMaterial({glslVersion:THREE.GLSL3,side:THREE.BackSide,transparent:true,depthWrite:false,uniforms:{uDensity:{value:data},uDetail:{value:detail},uObserved:{value:observedDetail?1:0},uMode:{value:0},uSteps:{value:36},uOpacity:{value:1},uShell:{value:0},uEdgeFade:{value:0}},
 vertexShader:'varying vec3 vOrigin;varying vec3 vDirection;void main(){vOrigin=(inverse(modelMatrix)*vec4(cameraPosition,1.)).xyz;vDirection=position-vOrigin;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
 fragmentShader:`precision highp sampler3D;uniform sampler3D uDensity;uniform sampler2D uDetail;uniform float uObserved;uniform float uMode;uniform float uSteps;uniform float uOpacity;uniform float uShell;uniform float uEdgeFade;varying vec3 vOrigin;varying vec3 vDirection;out vec4 outColor;
 vec2 hitBox(vec3 o,vec3 d){vec3 t0=(-vec3(1.)-o)/d;vec3 t1=(vec3(1.)-o)/d;vec3 lo=min(t0,t1),hi=max(t0,t1);return vec2(max(max(lo.x,lo.y),lo.z),min(min(hi.x,hi.y),hi.z));}
 float rho(vec3 p){float d=texture(uDensity,p*.5+.5).r;if(uEdgeFade>.01)d*=1.-smoothstep(1.-uEdgeFade,1.,max(max(abs(p.x),abs(p.y)),abs(p.z)));if(uShell>.01)d*=exp(-pow((length(p)-uShell)/.19,2.))*2.;return d;}
 void main(){vec3 ray=normalize(vDirection);vec2 bounds=hitBox(vOrigin,ray);if(bounds.x>bounds.y)discard;float t=max(bounds.x,0.),stepSize=(bounds.y-t)/uSteps;vec3 lightPoint=vec3(.12,.2,.45);vec4 sum=vec4(0.);
 for(int i=0;i<56;i++){if(float(i)>=uSteps||sum.a>.975)break;vec3 p=vOrigin+ray*(t+stepSize*(float(i)+.5));float d=rho(p);float illumination=exp(-length(p-lightPoint)*1.3);float shade=exp(-rho(p+normalize(lightPoint-p)*.10)*2.4);float a=(1.-exp(-d*stepSize*7.5))*uOpacity;
 vec3 gradient=vec3(rho(p+vec3(.015,0.,0.))-rho(p-vec3(.015,0.,0.)),rho(p+vec3(0.,.015,0.))-rho(p-vec3(0.,.015,0.)),rho(p+vec3(0.,0.,.015))-rho(p-vec3(0.,0.,.015)));float rim=.5+.5*max(0.,dot(normalize(gradient+vec3(.00001)),normalize(lightPoint-p)));vec3 color=mix(vec3(.32,.055,.10),vec3(1.9,1.25,1.03),illumination)*(.48+.52*shade)*rim*exp(-d*.8);
 vec3 projected=vOrigin+ray*((.20-vOrigin.z)/(abs(ray.z)<.001?.001:ray.z));vec2 detailUv=clamp((abs(ray.z)>.35?projected.xy:p.xy)*.46+.5,.002,.998);vec3 observed=pow(texture(uDetail,vec2(detailUv.x,1.-detailUv.y)).rgb,vec3(2.2));float brightness=dot(observed,vec3(.2126,.7152,.0722));
 if(uObserved>.5)color=(observed*3.1+vec3(.06,.025,.035))*(.55+.45*shade)*(1.-d*.28);
 if(uMode>.5&&uMode<1.5){float lamp=exp(-dot(p.xy-lightPoint.xy,p.xy-lightPoint.xy)*3.4);color=mix(vec3(.003,.009,.017),vec3(.35,.66,1.1),lamp)*(.28+.72*shade);if(uObserved>.5)color*=.18+sqrt(brightness)*3.;a*=.36+.64*lamp;}
 if(uMode>1.5){color=vec3(.00015,.0002,.0003);a=1.-exp(-d*stepSize*17.);}

 sum.rgb+=(1.-sum.a)*a*color;sum.a+=(1.-sum.a)*a;}
 if(sum.a<.005)discard;vec3 color=sum.rgb/max(sum.a,.001);outColor=vec4(pow(max(color,vec3(0.)),vec3(1./2.2)),sum.a);}`});
 const mesh=new THREE.Mesh(new THREE.BoxGeometry(2,2,2),material);mesh.scale.set(2.2,1.55,1.35);return mesh;
};}
export function lightStars(count=180):THREE.Points{
 const canvas=document.createElement('canvas');canvas.width=canvas.height=64;const ctx=canvas.getContext('2d')!,gradient=ctx.createRadialGradient(32,32,0,32,32,32);gradient.addColorStop(0,'#fff');gradient.addColorStop(.12,'#fff9');gradient.addColorStop(.4,'#ffffff30');gradient.addColorStop(1,'#fff0');ctx.fillStyle=gradient;ctx.fillRect(0,0,64,64);
 const positions=new Float32Array(count*3);for(let i=0;i<count;i++)positions.set([Math.sin(i*27.7)*4,Math.cos(i*11.3)*2.7,-2.8-Math.abs(Math.sin(i*4.2))],i*3);
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(positions,3));return new THREE.Points(geo,new THREE.PointsMaterial({map:new THREE.CanvasTexture(canvas),color:0xe5d7c5,size:.06,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,opacity:.85}));
}

/** Unresolved light source: a radial emission profile, not a visible plastic surface. */
export function distantStar(color:THREE.ColorRepresentation=0xffddab):THREE.Sprite{const canvas=document.createElement('canvas');canvas.width=canvas.height=128;const ctx=canvas.getContext('2d')!,g=ctx.createRadialGradient(64,64,0,64,64,64);g.addColorStop(0,'#fff');g.addColorStop(.065,'#ffffffe0');g.addColorStop(.17,'#ffffff90');g.addColorStop(.4,'#ffffff1e');g.addColorStop(1,'#fff0');ctx.fillStyle=g;ctx.fillRect(0,0,128,128);return new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas),color,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));}
