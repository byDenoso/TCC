import * as THREE from 'three';
import type {Exhibit} from './runtime';
import {stellarFactory} from './stellar-materials';
/** Artistic accretion disc; no ray tracing, photon ring or relativistic shadow. */
export function remnantScene():Exhibit{
 const group=new THREE.Group(),hole=new THREE.Group();hole.position.x=.9;group.add(hole);
 const horizon=new THREE.Mesh(new THREE.CircleGeometry(.16,64),new THREE.MeshBasicMaterial({color:0x000002,side:THREE.DoubleSide}));horizon.rotation.x=Math.PI/2;hole.add(horizon);
 const disk=new THREE.Mesh(new THREE.RingGeometry(.55,1.45,128,16),new THREE.ShaderMaterial({side:THREE.DoubleSide,transparent:true,depthWrite:false,toneMapped:false,uniforms:{uTime:{value:0}},
 vertexShader:'varying vec2 vP;void main(){vP=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
 fragmentShader:`uniform float uTime;varying vec2 vP;float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);}void main(){float r=length(vP),angle=atan(vP.y,vP.x);vec2 p=vec2(cos(angle-uTime*.35),sin(angle-uTime*.35))*r;float clumps=noise(p*6.)*.6+noise(p*18.+2.)*.3+noise(p*47.)*.1;float profile=exp(-(r-.60)*1.9)*smoothstep(.55,.63,r);float fine=.64+.52*clumps;vec3 color=mix(vec3(.88,.27,.095),vec3(1.,.83,.53),pow(profile,.65));float a=(1.-smoothstep(1.25,1.45,r))*(.45+.55*profile);gl_FragColor=vec4(color*fine*(.36+.65*profile),a);}`
 }));disk.rotation.x=Math.PI/2;hole.add(disk);
 const neutron=stellarFactory()(0xe1eeff);neutron.position.x=-1.55;neutron.scale.setScalar(.19);(neutron.material as THREE.ShaderMaterial).uniforms.uIntensity.value=1.45;group.add(neutron);
 const nsLabel={text:'estrela de nêutrons · ampliada',position:new THREE.Vector3(-1.55,-.22,0),visible:()=>group.visible&&neutron.visible},bhLabel={text:'corte do horizonte · marcador',position:new THREE.Vector3(.9,-.38,0),visible:()=>group.visible&&horizon.visible};
 return {group,labels:[nsLabel,bhLabel],camera:[0,2.3,6.6],cameraForAspect:a=>a<1?[0,3.6,8.8]:[0,2.3,6.6],update({value,phase}){horizon.visible=disk.visible=neutron.visible=value>=3;(disk.material as THREE.ShaderMaterial).uniforms.uTime.value=phase*3.;}};
}
