import * as THREE from 'three';
import type {Exhibit} from './runtime';
import {stellarFactory} from './stellar-materials';
/** Artistic accretion disc; no ray tracing, photon ring or relativistic shadow. */
export function remnantScene():Exhibit{
 const group=new THREE.Group(),hole=new THREE.Group();hole.position.x=.9;group.add(hole);
 const horizon=new THREE.Mesh(new THREE.CircleGeometry(.16,64),new THREE.MeshBasicMaterial({color:0x000002,side:THREE.DoubleSide}));horizon.rotation.x=Math.PI/2;hole.add(horizon);
 const disk=new THREE.Mesh(new THREE.RingGeometry(.55,1.45,128,16),new THREE.ShaderMaterial({side:THREE.DoubleSide,transparent:true,depthWrite:false,toneMapped:false,uniforms:{uTime:{value:0}},
 vertexShader:'varying vec2 vP;void main(){vP=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
 fragmentShader:`uniform float uTime;varying vec2 vP;float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);}void main(){
   float r=length(vP),angle=atan(vP.y,vP.x);
   // Sheared orbital filaments, evaluated in Cartesian angular coordinates across the seam.
   float winding = angle + 9.*log(r) - uTime*.23/pow(r,1.5);
   vec2 sheared = vec2(cos(winding),sin(winding));
   float stream = noise(sheared*vec2(3.,4.) + vec2(r*24.,r*39.));
   float fine = noise(sheared*8. + vec2(r*51.,r*63.));
   float crest = .5 + .5*sin(r*117. + stream*3.8 + fine*1.3);
   float accretion = .42+.43*stream+.14*fine+.15*crest;
   float inner = smoothstep(.55,.59,r);
   float heat = inner*exp(-(r-.59)*2.8);
   float edge = 1.-smoothstep(1.17,1.45,r);
   vec3 color = mix(vec3(.64,.23,.095),vec3(1.,.89,.68),pow(heat,.8));
   gl_FragColor=vec4(color*accretion*(.48+.60*heat)*(.91+.09*cos(angle)),inner*edge);
 }`
 }));disk.rotation.x=Math.PI/2;hole.add(disk);
 const neutron=stellarFactory()(0xe1eeff);neutron.position.x=-1.55;neutron.scale.setScalar(.19);(neutron.material as THREE.ShaderMaterial).uniforms.uIntensity.value=1.15;(neutron.material as THREE.ShaderMaterial).uniforms.uPhotosphere.value=0;group.add(neutron);
 const nsLabel={text:'estrela de nêutrons · ampliada',position:new THREE.Vector3(-1.55,-.22,0),visible:()=>group.visible&&neutron.visible},bhLabel={text:'corte do horizonte · marcador',position:new THREE.Vector3(.9,-.38,0),visible:()=>group.visible&&horizon.visible};
 return {group,labels:[nsLabel,bhLabel],camera:[0,2.3,6.6],cameraForAspect:a=>a<1?[0,3.6,8.8]:[0,2.3,6.6],update({value,phase}){horizon.visible=disk.visible=neutron.visible=value>=3;(disk.material as THREE.ShaderMaterial).uniforms.uTime.value=phase*3.;}};
}
