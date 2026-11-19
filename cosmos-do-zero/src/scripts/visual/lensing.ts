import { plate, disc, galaxy, loadPlateImage } from '../lab/plate';
import { lensSource,pointImages } from '../../lib/physics';
import { svg } from '../lab/common';
export function initLensing():void {
 for(const root of document.querySelectorAll<HTMLElement>('[data-lens]')){
  const canvas=root.querySelector<HTMLCanvasElement>('[data-lens-image]')!,ctx=canvas.getContext('2d');
  const source=root.querySelector<HTMLInputElement>('[data-lens-source]')!,lens=root.querySelector<HTMLInputElement>('[data-lens-lens]')!,caption=root.querySelector<HTMLElement>('[data-lens-caption]')!;
  const massRatio=root.querySelector<HTMLInputElement>('[data-lens-mass]')!;
  const ratio=()=>massRatio.valueAsNumber;
  const background = [7,12,24], coreColor = [126,105,76];
  const brightness = root.querySelector<HTMLSelectElement>('[data-lens-brightness]')!;
  let sourcePixels: ImageData | undefined;
  const alternate=root.querySelector<SVGSVGElement>('[data-lens-image-fallback]')!;
  const ring=alternate.querySelector<SVGCircleElement>('[data-lens-ring]')!;
  const imagePoints=[...alternate.querySelectorAll<SVGCircleElement>('[data-lens-image-point]')];
  canvas.hidden=!ctx;alternate.toggleAttribute('hidden',Boolean(ctx));
  const fallback=root.querySelector<SVGSVGElement>('[data-lens-fallback]')!;
  root.querySelector<HTMLDetailsElement>('[data-lens-geometry]')!.open=innerWidth>600;
  const diagram = svg('g', {}, fallback);
  const surface = plate(fallback, ['spiral','elliptical','earth'], (ctx, img) => {
    galaxy(ctx,img('spiral'),120 + source.valueAsNumber*90,70,23,-.4);
    galaxy(ctx,img('elliptical'),240 + lens.valueAsNumber*45,140,23*Math.cbrt(ratio()),.25,.82);
    disc(ctx,img('earth'),360,210,10,.84);
  });
  const drawFallback=()=>{diagram.replaceChildren();const sx=Number(source.value)*45,lx=Number(lens.value)*45;
   svg('ellipse',{'data-lab-body':'',cx:120+sx*2,cy:70,rx:10,ry:6,fill:'#b3b7cf'},diagram);svg('circle',{'data-lab-body':'',cx:240+lx,cy:140,r:15,fill:'#d6aa7f'},diagram);svg('circle',{'data-lab-body':'',cx:360,cy:210,r:7,fill:'#85aabd'},diagram);
   svg('text',{x:120+sx*2,y:40,'text-anchor':'middle',fill:'var(--ink-2)'},diagram,'fonte');svg('text',{x:240+lx,y:180,'text-anchor':'middle',fill:'var(--ink-2)'},diagram,'lente');svg('text',{x:370,y:245,fill:'var(--ink-2)'},diagram,'observador');
   for(const theta of pointImages(Number(source.value)-Number(lens.value),ratio()))svg('polyline',{points:`${120+sx*2},70 ${240+lx+theta*45},140 360,210`,fill:'none',stroke:'#ac936f','stroke-width':1.5},diagram);
  };
  const render=()=>{
   const beta=Number(source.value)-Number(lens.value),mu=ratio(),aligned=Math.abs(beta)<.04;
   if(ctx){
    const image=ctx.createImageData(240,240);
    const photo = brightness.value === 'photo' ? sourcePixels : undefined;
   for(let y=0;y<240;y++)for(let x=0;x<240;x++){
    const tx=(x-120)/48,ty=(y-120)/48,[bx,by]=lensSource(tx,ty,mu);
    const intensity=Math.exp(-((bx-beta)**2+by**2)/(.12**2*2));const r2=tx*tx+ty*ty,lensGlow=Math.exp(-r2/.035)*.55;
    const i=(y*240+x)*4;image.data[i]=7+intensity*176+lensGlow*126;image.data[i+1]=12+intensity*153+lensGlow*105;image.data[i+2]=24+intensity*114+lensGlow*76;image.data[i+3]=255;
    if (photo) {
      // The source spans 0.72 Einstein radii of the reference mass in each dimension.
      const ix = Math.floor(((bx-beta)/.72 + .5)*photo.width);
      const iy = Math.floor((by/.72 + .5)*photo.height);
      const inside = ix >= 0 && iy >= 0 && ix < photo.width && iy < photo.height;
      const j = (iy*photo.width+ix)*4;
      const alpha = inside ? photo.data[j+3]/255 : 0;
      for (let k=0; k<3; k++) image.data[i+k] = background[k] + lensGlow*coreColor[k] + (inside ? photo.data[j+k]*alpha : 0);
    }
    }
    ctx.putImageData(image,0,0);
   }else{
    ring.setAttribute('r',String(48*Math.sqrt(mu)));
    ring.setAttribute('visibility',aligned?'visible':'hidden');
    pointImages(beta,mu).forEach((theta,i)=>{
     imagePoints[i].setAttribute('cx',String(120+theta*48));
     imagePoints[i].setAttribute('visibility',aligned?'hidden':'visible');
    });
   }
   root.querySelector<HTMLElement>('[data-lens-source-out]')!.textContent=Number(source.value).toLocaleString('pt-BR',{minimumFractionDigits:2});root.querySelector<HTMLElement>('[data-lens-lens-out]')!.textContent=Number(lens.value).toLocaleString('pt-BR',{minimumFractionDigits:2});
   root.querySelector<HTMLElement>('[data-lens-mass-out]')!.textContent=ratio().toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})+' × M₀';
   const radius=Math.sqrt(ratio()).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
   caption.textContent='Imagem centrada na lente. '+(aligned?`Fonte e lente alinhadas: o anel tem raio ${radius} na escala angular de referência.`:ctx?'Fora do alinhamento: aparecem arcos de brilho diferente.':'Fora do alinhamento: o esquema indica as duas posições para uma fonte pontual.');
   drawFallback(); surface.refresh();
  };
  if (ctx) {
   const observer = new IntersectionObserver(([entry]) => {
    if (!entry.isIntersecting) return;
    observer.disconnect();
    loadPlateImage('spiral').then(image => {
      const sample = document.createElement('canvas');
      sample.width = 192; sample.height = 192;
      const sourceCtx = sample.getContext('2d');
      if (!sourceCtx) return;
      sourceCtx.drawImage(image,0,0,192,192);
      sourcePixels = sourceCtx.getImageData(0,0,192,192);
      brightness.disabled = false;
      brightness.value = 'photo';
      render();
    }).catch(() => { /* O perfil gaussiano continua disponível. */ });
   });
   observer.observe(canvas);
  }
  brightness.addEventListener('change', render);
  source.addEventListener('input',render);lens.addEventListener('input',render);massRatio.addEventListener('input',render);
  root.querySelector('[data-lens-example]')!.addEventListener('click',()=>{source.value='0.7';lens.value='0';massRatio.value='1';render();});
  root.querySelector('[data-lens-reset]')!.addEventListener('click',()=>{source.value='0';lens.value='0';massRatio.value='1';render();});render();
  root.dataset.lensReady='true';
 }
}
