import * as THREE from 'three';
import { observeScene,type Exhibit } from './runtime';
import {emissionGalaxy,emissionPalette,emissionSize,prepareEmissionGalaxies,type EmissionSize} from './galaxy-emission';
import type {MountedScene} from './runtime';
import { lensSource,pointImages } from '../../lib/physics';
import { svg } from '../lab/common';
export function initLensing():void {
 for(const root of document.querySelectorAll<HTMLElement>('[data-lens]')){
  const stage=root.querySelector<HTMLElement>('[data-lens-stage]')!,canvas=root.querySelector<HTMLCanvasElement>('[data-lens-image]')!,ctx=canvas.getContext('2d')!;
  const source=root.querySelector<HTMLInputElement>('[data-lens-source]')!,lens=root.querySelector<HTMLInputElement>('[data-lens-lens]')!,caption=root.querySelector<HTMLElement>('[data-lens-caption]')!;
  const fallback=root.querySelector<SVGSVGElement>('[data-lens-fallback]')!;
  root.querySelector<HTMLDetailsElement>('[data-lens-geometry]')!.open=innerWidth>600;
  const drawFallback=()=>{fallback.replaceChildren();const sx=Number(source.value)*45,lx=Number(lens.value)*45;
   svg('ellipse',{cx:120+sx*2,cy:70,rx:10,ry:6,fill:'#b3b7cf'},fallback);svg('circle',{cx:240+lx,cy:140,r:15,fill:'#d6aa7f'},fallback);svg('circle',{cx:360,cy:210,r:7,fill:'#85aabd'},fallback);
   svg('text',{x:25,y:45,fill:'var(--ink-2)'},fallback,'fonte');svg('text',{x:225,y:175,fill:'var(--ink-2)'},fallback,'lente');svg('text',{x:370,y:245,fill:'var(--ink-2)'},fallback,'observador');
   for(const theta of pointImages(Number(source.value)-Number(lens.value)))svg('polyline',{points:`${120+sx*2},70 ${240+lx+theta*45},140 360,210`,fill:'none',stroke:'#ac936f','stroke-width':1.5},fallback);
  };
  const make=():Exhibit=>{
   let size:EmissionSize=(Number(stage.dataset.textureQuality)||emissionSize(stage.clientWidth)) as EmissionSize,palette=emissionPalette(size),request=0,disposed=false;const group=new THREE.Group(),geo=new THREE.PlaneGeometry(2,2),src=emissionGalaxy(0,palette,geo),mass=emissionGalaxy(4,palette,geo),observer=new THREE.Mesh(new THREE.SphereGeometry(.1,16,10),new THREE.MeshStandardMaterial({color:0x80a4c2}));
   group.userData.textureQuality=size;palette.forEach((t,i)=>{if(i!==0&&i!==4)t.dispose();});src.scale.setScalar(.6);src.rotation.y=.30;mass.scale.setScalar(.75);mass.rotation.y=-.20;src.position.z=-2.7;observer.position.z=2.7;group.add(src,mass,observer);
   const lines=[0,1].map(()=>{const l=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3(),new THREE.Vector3()]),new THREE.LineBasicMaterial({color:0xb0936d,transparent:true,opacity:.6}));group.add(l);return l;});
   return {group,async quality(mode,width){const next=emissionSize(width,mode),ticket=++request;if(next===size)return;await prepareEmissionGalaxies(next);if(disposed||ticket!==request)return;const old=palette;palette=emissionPalette(next);group.traverse(o=>{const mesh=o as THREE.Mesh;for(const m of mesh.material?(Array.isArray(mesh.material)?mesh.material:[mesh.material]):[]){const material=m as THREE.MeshBasicMaterial;const index=material.map?old.indexOf(material.map):-1;if(index>=0)material.map=palette[index];}});old.forEach(t=>t.dispose());palette.forEach((t,i)=>{if(i!==0&&i!==4)t.dispose();});size=next;group.userData.textureQuality=size;},dispose(){disposed=true;request++;},labels:[{text:'fonte',position:src.position},{text:'massa que faz a lente',position:mass.position},{text:'observador',position:observer.position}],camera:[4.2,3.2,6.5],update(){
    src.position.x=2*Number(source.value)*.48;mass.position.x=Number(lens.value)*.48;
    pointImages(Number(source.value)-Number(lens.value)).forEach((theta,i)=>{const a=lines[i].geometry.getAttribute('position') as THREE.BufferAttribute;a.setXYZ(0,src.position.x,0,-2.7);a.setXYZ(1,mass.position.x+theta*.48,0,0);a.setXYZ(2,0,0,2.7);a.needsUpdate=true;});
   }};
  };
  let view:MountedScene|null=null,alive=true,loading=false;const loader=new IntersectionObserver(async entries=>{if(!entries.some(e=>e.isIntersecting)||loading||view||!alive)return;loading=true;try{await prepareEmissionGalaxies(emissionSize(stage.clientWidth,stage.dataset.cosmosQuality==='low'?'low':'auto'));if(!alive)return;view=observeScene(stage,make);render();loader.disconnect();}catch{stage.dataset.visualFallback='true';}finally{loading=false;}},{rootMargin:'150px'});loader.observe(stage);
  const render=()=>{
   const beta=Number(source.value)-Number(lens.value),image=ctx.createImageData(240,240);
   for(let y=0;y<240;y++)for(let x=0;x<240;x++){
    const tx=(x-120)/48,ty=(y-120)/48,[bx,by]=lensSource(tx,ty);
    const intensity=Math.exp(-((bx-beta)**2+by**2)/(.12**2*2));const r2=tx*tx+ty*ty,lensGlow=Math.exp(-r2/.035)*.55;
    const i=(y*240+x)*4;image.data[i]=7+intensity*176+lensGlow*126;image.data[i+1]=12+intensity*153+lensGlow*105;image.data[i+2]=24+intensity*114+lensGlow*76;image.data[i+3]=255;
   }ctx.putImageData(image,0,0);
   root.querySelector<HTMLElement>('[data-lens-source-out]')!.textContent=Number(source.value).toLocaleString('pt-BR',{minimumFractionDigits:2});root.querySelector<HTMLElement>('[data-lens-lens-out]')!.textContent=Number(lens.value).toLocaleString('pt-BR',{minimumFractionDigits:2});
   caption.textContent='Imagem centrada na lente. '+(Math.abs(beta)<.04?'Fonte e lente alinhadas: a imagem calculada forma um anel.':'Fora do alinhamento: o anel se quebra em arcos de brilho diferente.');
   drawFallback();view?.state({value:beta});
  };
  source.addEventListener('input',render);lens.addEventListener('input',render);root.querySelector('[data-lens-reset]')!.addEventListener('click',()=>{source.value='0';lens.value='0';render();});render();
  root.dataset.lensReady='true';
  window.addEventListener('pagehide',(event)=>{if(!event.persisted){alive=false;loader.disconnect();view?.dispose();}});
 }
}
