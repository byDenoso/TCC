import * as THREE from 'three';
import { observeScene,whenNear,type MountedScene,type Exhibit } from '../visual/runtime';
import { createGalaxyFactory } from '../visual/galaxy';
import {prepareEmissionGalaxies,emissionSize,emissionReady} from '../visual/galaxy-emission';
import { PLANCK } from '../../lib/cosmology';
import { photonTable,photonAt } from '../../lib/photon';
import { animator,svg } from './common';
export interface Tempo3D { set(z:number,lamNm:number):void; dispose():void }

/** Caminho FLRW calculado por evento; distâncias projetadas comprimidas, corpos ligados constantes. */
export async function mountTempo3D(host:HTMLElement,reduced:()=>boolean):Promise<Tempo3D|null>{
 let z=0,phase=0,playing=false,table=photonTable(0,PLANCK),view:MountedScene|null=null;
 host.querySelectorAll<HTMLElement>('.obs3d-label,.obs3d-tag').forEach(e=>e.hidden=true);
 const fallback=svg('svg',{viewBox:'0 0 640 400',role:'img','aria-label':'A luz percorre o espaço enquanto as distâncias crescem. Trajetória calculada no modelo FLRW, distâncias comprimidas na imagem.'},host);
 const source=svg('ellipse',{rx:15,ry:7,fill:'#b4a184'},fallback),us=svg('ellipse',{cx:490,cy:210,rx:15,ry:7,fill:'#779bc5'},fallback),light=svg('circle',{r:5,fill:'#f8bc75'},fallback);
 void us;
 const make=():Exhibit=>{
  const size=host.dataset.cosmosQuality==='low'&&emissionReady(512)?512:initialSize,galaxy=createGalaxyFactory(size);
  const group=new THREE.Group(),usGalaxy=galaxy(29),srcGalaxy=galaxy(19),photon=new THREE.Mesh(new THREE.SphereGeometry(.045,12,8),new THREE.MeshBasicMaterial({color:0xf4c99b}));
  usGalaxy.scale.setScalar(.85);srcGalaxy.scale.setScalar(.85);usGalaxy.position.x=1.85;
  const field=Array.from({length:9},(_,i)=>{const g=galaxy(22+i,i%3===0?'elliptical':i%5===0?'irregular':'spiral',true);g.scale.setScalar(.32);group.add(g);return g;});
  const gas=new THREE.Mesh(new THREE.SphereGeometry(.5,32,16),new THREE.ShaderMaterial({transparent:true,depthWrite:false,toneMapped:false,vertexShader:'varying vec3 n;varying vec3 p;void main(){vec4 v=modelViewMatrix*vec4(position,1.);n=normalize(normalMatrix*normal);p=v.xyz;gl_Position=projectionMatrix*v;}',fragmentShader:'varying vec3 n;varying vec3 p;void main(){float mu=max(0.,dot(normalize(n),normalize(-p)));float a=pow(mu,2.)*.28;gl_FragColor=vec4(.75,.42,.24,a);}'}));
  group.add(usGalaxy,srcGalaxy,photon,gas);
  const srcLabel={text:'galáxia: emissão',position:srcGalaxy.position,visible:()=>z>.005};
  return {group,...galaxy.presentation(group),camera:[0,4.8,7.4],labels:[{text:'nós · hoje',position:usGalaxy.position},srcLabel],update(){
   const state=photonAt(table,phase),scale=state.a**.18;
   srcGalaxy.position.set(1.85-3.7*scale,0,0);photon.position.set(1.85-3.7*state.chi*scale,0,0);gas.position.copy(srcGalaxy.position);
   srcGalaxy.visible=z>.005&&z<20;gas.visible=z>=20;srcLabel.text=z<20?'galáxia: emissão':'região de gás: emissão';
   field.forEach((g,i)=>{g.position.set((Math.sin(i*5)*3.4-1.85)*scale+1.85,Math.cos(i*3)*.7,Math.cos(i*7)*2*scale);g.visible=1/state.a-1<20;});
   photon.visible=z>.005;
  }};
 };
 const paint=()=>{const state=photonAt(table,phase),s=state.a**.18;source.style.display=z<.005?'none':'';light.style.display=z<.005?'none':'';source.setAttribute('cx',String(490-390*s));source.setAttribute('cy','210');light.setAttribute('cx',String(490-390*s*state.chi));light.setAttribute('cy','210');view?.state({value:z,phase});};
 const button=host.querySelector<HTMLButtonElement>('[data-3d-play]');
 const sync=()=>{button?.setAttribute('aria-pressed',String(playing));if(button){button.hidden=z<.005;button.querySelector('[data-3d-play-label]')!.textContent=playing?'Pausar':'Continuar';button.firstElementChild!.textContent=playing?'❚❚':'▶';}};
 const anim=animator(host,dt=>{phase+=dt/5200;if(phase>1.25)phase=0;paint();return playing;});
 const autoPause=()=>{playing=false;sync();};host.addEventListener('cosmos:autopause',autoPause);
 const click=()=>{if(playing){anim.stop();playing=false;}else{anim.start();playing=anim.running();}sync();};button?.addEventListener('click',click);
 const initialSize=emissionSize(host.closest<HTMLElement>('.obs-viz')?.clientWidth??host.clientWidth,host.dataset.cosmosQuality==='low'?'low':'auto');
 if(!await whenNear(host.closest<HTMLElement>('.obs-viz')??host)){fallback.remove();anim.dispose();button?.removeEventListener('click',click);host.removeEventListener('cosmos:autopause',autoPause);return null;}
 try{await prepareEmissionGalaxies(initialSize);}catch{fallback.remove();anim.dispose();button?.removeEventListener('click',click);host.removeEventListener('cosmos:autopause',autoPause);return null;}
 view=host.dataset.visualFallback==='true'?null:observeScene(host,make);
 const fail=()=>{anim.stop();playing=false;sync();host.dispatchEvent(new CustomEvent('obs3d:lost',{bubbles:true}));};
 host.addEventListener('cosmos:contextlost',fail);host.addEventListener('cosmos:unavailable',fail);
 const dispose=()=>{anim.dispose();view?.dispose();button?.removeEventListener('click',click);host.removeEventListener('cosmos:autopause',autoPause);host.removeEventListener('cosmos:contextlost',fail);host.removeEventListener('cosmos:unavailable',fail);fallback.remove();};
 window.addEventListener('pagehide',(event)=>{if(event.persisted){anim.stop();playing=false;sync();}else dispose();});
 return {set(next){if(next===z){paint();return;}z=next;table=photonTable(z,PLANCK);phase=reduced()?1:0;playing=!reduced()&&z>=.005;anim.stop();if(playing){anim.start();playing=anim.running();}paint();sync();},dispose};
}
