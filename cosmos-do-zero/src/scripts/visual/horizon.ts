import * as THREE from 'three';
import type { Exhibit } from './runtime';
import { createGalaxyFactory } from './galaxy';
export function horizon(initialSize:import('./galaxy-emission').EmissionSize=1536):Exhibit{
 const galaxy=createGalaxyFactory(initialSize);
 const group=new THREE.Group(),positions=[new THREE.Vector3(0,0,0),new THREE.Vector3(1.8,0,0),new THREE.Vector3(0,1.1,0)];
 for(let i=0;i<24;i++){const g=galaxy(i*137,i%3===0?'elliptical':i%5===0?'irregular':'spiral',true);g.scale.setScalar(.22);g.position.set(Math.sin(i*4.3)*3.5,Math.cos(i*7)*1.3,Math.cos(i*8.9)*2.3);group.add(g);}
 positions.forEach((position,i)=>{const g=galaxy(30+i);g.position.copy(position);g.scale.setScalar(.5);group.add(g);});
 const observer=new THREE.Mesh(new THREE.SphereGeometry(.075,16,10),new THREE.MeshBasicMaterial({color:0xffac71}));group.add(observer);
 const circle=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(Array.from({length:96},(_,i)=>new THREE.Vector3(Math.cos(i/96*Math.PI*2)*1.7,0,Math.sin(i/96*Math.PI*2)*1.7))),new THREE.LineDashedMaterial({color:0xc4a485,dashSize:.08,gapSize:.04,transparent:true,opacity:.8}));circle.computeLineDistances();group.add(circle);
 const label={text:'observador: nós',position:observer.position};
 return {group,...galaxy.presentation(group),labels:[label],camera:[0,4,9],update({value}){const i=Math.min(2,Math.round(value));observer.position.copy(positions[i]);circle.position.copy(positions[i]);label.text=['observador: nós','observador: galáxia à direita','observador: galáxia acima'][i];}};
}
