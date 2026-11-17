import type { openStoryVolume } from './story-volume-scene';
import { u } from '../lib/url';

type Volume = Awaited<ReturnType<typeof openStoryVolume>>;
export function initStoryVolumes() {
  for (const host of document.querySelectorAll<HTMLElement>('[data-story-volume]')) {
    const story = host.closest<HTMLElement>('[data-story]')!;
    const canvas = host.querySelector('canvas')!;
    const toggle = story.querySelector<HTMLButtonElement>('[data-volume-toggle]')!;
    const turn = host.querySelector<HTMLButtonElement>('[data-volume-turn]')!;
    const caption = host.querySelector<HTMLElement>('[data-volume-caption]')!;
    const status = host.querySelector<HTMLElement>('[data-volume-status]')!;
    const illustration = story.querySelector<HTMLButtonElement>('[data-story-mode="scene"]')!;
    illustration.addEventListener('click',()=>{if(active||toggle.disabled)close();});
    let scene: Volume | undefined;
    let active = false, serial = 0, yaw = 0, pitch = 0;
    function sync() {
      if (!scene || !active) return;
      caption.textContent = scene.frame(Number(story.dataset.storyProgress || 0), Number(story.dataset.storyPhase || 0), yaw, pitch);
    }
    function close() {
      serial++;
      active = false;
      scene?.dispose();
      scene = undefined;
      canvas.hidden = turn.hidden = caption.hidden = true;
      toggle.disabled = false;
      toggle.textContent = 'Explorar em 3D';
      toggle.setAttribute('aria-pressed','false');
      illustration.setAttribute('aria-pressed',String(story.dataset.storyModeActive==='scene'));
      status.textContent = '';
    }
    async function open() {
      if(story.dataset.storyModeActive==='film')illustration.click();
      const attempt = ++serial;
      toggle.disabled = true;
      toggle.textContent = 'Abrindo 3D…';
      status.textContent = '';
      try {
        const {openStoryVolume} = await import('./story-volume-scene');
        if (attempt !== serial) return;
        const renderer = await openStoryVolume(canvas,host.dataset.storyVolume!,u('/'));
        if (attempt !== serial) {renderer.dispose();return;}
        scene = renderer;
        active = true;
        canvas.hidden = turn.hidden = caption.hidden = false;
        scene.resize();
        sync();
        toggle.textContent = 'Fechar 3D';
        toggle.setAttribute('aria-pressed','true');
        illustration.setAttribute('aria-pressed','false');
      } catch {
        if (attempt !== serial) return;
        close();
        status.textContent = '3D indisponível neste aparelho. Os três momentos continuam na ilustração.';
      } finally { if (attempt === serial) toggle.disabled = false; }
    }
    toggle.addEventListener('click',()=>{if(active) close();else void open();});
    turn.addEventListener('click',()=>{yaw+=.42;sync();});
    const limitPitch=(value:number)=>Math.max(-.42,Math.min(.42,value));
    canvas.addEventListener('keydown',e=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(e.key))return;
      e.preventDefault();
      if(e.key==='Home'){yaw=0;pitch=0;}
      else if(e.key==='ArrowLeft'||e.key==='ArrowRight') yaw+=e.key==='ArrowRight'?.16:-.16;
      else pitch=limitPitch(pitch+(e.key==='ArrowUp'?.10:-.10));
      sync();
    });
    let pointer:{x:number,y:number,id:number}|null=null;
    canvas.addEventListener('pointerdown',e=>{pointer={x:e.clientX,y:e.clientY,id:e.pointerId};canvas.setPointerCapture(e.pointerId);});
    canvas.addEventListener('pointermove',e=>{
      if(pointer?.id!==e.pointerId)return;
      yaw+=(e.clientX-pointer.x)*.009;
      pitch=limitPitch(pitch+(pointer.y-e.clientY)*.003);
      pointer={x:e.clientX,y:e.clientY,id:e.pointerId};sync();
    });
    canvas.addEventListener('lostpointercapture',()=>{pointer=null;});
    canvas.addEventListener('webglcontextlost',e=>{
      if(!active)return;
      e.preventDefault();close();status.textContent='O aparelho liberou o 3D. Você pode continuar pela ilustração.';
    });
    const observer=new MutationObserver(()=>{
      if(story.dataset.storyModeActive==='film'){if(active||toggle.disabled)close();return;}
      sync();
    });
    observer.observe(story,{attributes:true,attributeFilter:['data-story-mode-active','data-story-progress','data-story-phase']});
    window.addEventListener('pagehide',e=>{close();if(!e.persisted)observer.disconnect();});
  }
}
