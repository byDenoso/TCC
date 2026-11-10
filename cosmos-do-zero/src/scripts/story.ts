import { STORIES, renderStory, sampleStory, storyProgress } from '../lib/story-scenes';
import { visibleMotion } from './visible-motion';
import { motionPreference } from './motion-preference';
import type { MountedScene } from './visual/runtime';

/** Uma cena usa um único relógio. Vídeo, controle manual e preferência têm prioridade. */
export function initStories():void {
 for(const root of document.querySelectorAll<HTMLElement>('[data-story]')){
  const id=root.dataset.story!,story=STORIES[id];if(!story)continue;
  const viewport=root.querySelector<HTMLElement>('[data-story-viewport]')!,stage=root.querySelector<HTMLElement>('[data-story-stage]')!;
  const world=stage.querySelector<HTMLElement>('[data-story-world]')!,graphic=stage.querySelector<HTMLElement>('[data-story-graphic]')!;
  const poster=world.querySelector<HTMLImageElement>('[data-story-poster]')!,posterUrl=poster.getAttribute('src')!;
  const film=root.querySelector<HTMLVideoElement>('[data-story-film]')!,play=root.querySelector<HTMLButtonElement>('[data-story-play]')!,label=root.querySelector<HTMLElement>('[data-story-play-label]')!;
  const range=root.querySelector<HTMLInputElement>('[data-story-time]')!,clock=root.querySelector<HTMLOutputElement>('[data-story-clock]')!,caption=root.querySelector<HTMLElement>('[data-story-caption]')!;
  const phases=[...root.querySelectorAll<HTMLButtonElement>('[data-story-phase]')],modes=[...root.querySelectorAll<HTMLButtonElement>('[data-story-mode]')];
  let seconds=motionPreference.matches?20:0,running=false,raf=0,last=0,lastPaint=0,lastProgress=-1,visible=false,mode='scene',sceneAutomatic=true,pendingFilmTime:number|null=null;
  let visual:MountedScene|null=null,preparing=false,alive=true;
  const showPoster=(phase:number)=>{
   if(id==='origem-do-universo')return;
   const src=phase===0?posterUrl:posterUrl.replace(/\.webp$/,`-${phase+1}.webp`);
   if(poster.getAttribute('src')!==src)poster.src=src;
  };
  const mountVisual=()=>{
   if(visual||preparing||!alive||!visible||mode!=='scene'||world.dataset.visualFallback==='true')return;
   preparing=true;
   void Promise.all([import('./visual/runtime'),import('./visual/story-exhibit')]).then(async ([{observeScene},{prepareStoryExhibit}])=>{
    const create=await prepareStoryExhibit(id);
    if(!alive)return;
    world.dataset.forceWebgl='true';
    visual=observeScene(world,create);
    const p=storyProgress(seconds);
    visual.state({value:p,phase:p,elapsed:seconds});
   }).catch(()=>{world.dataset.visualFallback='true';root.dataset.storyReference='true';}).finally(()=>{preparing=false;});
  };
  const referenceOnly=()=>{root.dataset.storyReference='true';};
  world.addEventListener('cosmos:contextlost',referenceOnly);
  world.addEventListener('cosmos:unavailable',referenceOnly);
  const paint=()=>{
   const t=mode==='film'?(pendingFilmTime??film.currentTime):seconds,p=storyProgress(t),state=sampleStory(id,p);
   if(mode==='scene'&&p!==lastProgress){
    graphic.innerHTML=renderStory(id,p,`story-${id}`,true);
    showPoster(state.phase);
    visual?.state({value:p,phase:p,elapsed:t});
    lastProgress=p;
   }
   const value=t.toFixed(2);if(range.value!==value)range.value=value;
   range.setAttribute('aria-valuetext',`${t.toFixed(1).replace('.',',')} segundos; ${story.phases[state.phase].label}`);
   const display=`0:${String(Math.floor(t)).padStart(2,'0')} / 0:20`;if(clock.textContent!==display)clock.textContent=display;
   const text=story.phases[state.phase].say;if(caption.textContent!==text)caption.textContent=text;
   phases.forEach((button,i)=>button.setAttribute('aria-current',i===state.phase?'step':'false'));
   const on=mode==='film'?!film.paused:running;play.setAttribute('aria-pressed',String(on));
   label.textContent=on?'Pausar':motionPreference.matches&&mode==='scene'?'Avançar':'Reproduzir';
   const notReady=mode==='film'&&!Number.isFinite(film.duration);range.disabled=notReady;phases.forEach(b=>b.disabled=notReady);
  };
  const stop=()=>{running=false;cancelAnimationFrame(raf);paint();};
  const tick=(now:number)=>{
   if(!running)return;
   if(last)seconds=(seconds+Math.min(now-last,1000)/1000)%20;last=now;
   if(now-lastPaint>=33){lastPaint=now;paint();}raf=requestAnimationFrame(tick);
  };
  const start=()=>{if(mode!=='scene'||!visible||motionPreference.matches)return;if(seconds>=20)seconds=0;running=true;last=0;lastPaint=0;paint();raf=requestAnimationFrame(tick);};
  const automatic=visibleMotion(viewport,{start,stop,running:()=>running,ready:()=>mode==='scene',visibility:on=>{visible=on;if(on)mountVisual();else film.pause();}});
  // Metadados podem chegar depois de outra escolha. Só a posição mais recente é aplicada.
  const alignFilm=()=>{if(mode==='film'&&pendingFilmTime!==null&&Number.isFinite(film.duration)){film.currentTime=Math.min(pendingFilmTime,film.duration);pendingFilmTime=null;}paint();};
  const seek=(value:number)=>{sceneAutomatic=false;automatic.manual();stop();seconds=value;if(mode==='film'){film.pause();pendingFilmTime=value;alignFilm();}else paint();};
  play.addEventListener('click',()=>{
   if(mode==='film'){if(film.paused)void film.play().catch(()=>{caption.textContent='Use o botão de reprodução do vídeo para começar.';});else film.pause();return;}
   if(running){sceneAutomatic=false;automatic.manual();stop();return;}
   if(motionPreference.matches){const phase=sampleStory(id,storyProgress(seconds)).phase,next=(phase+1)%3;seek(next===0?0:3+story.phases[next].at*12);return;}
   sceneAutomatic=true;automatic.automatic();
  });
  range.addEventListener('input',()=>seek(Number(range.value)));
  phases.forEach((button,i)=>button.addEventListener('click',()=>seek(i===0?0:3+story.phases[i].at*12)));
  root.querySelector('[data-story-reset]')!.addEventListener('click',()=>seek(0));
  modes.forEach(button=>button.addEventListener('click',()=>{
   const next=button.dataset.storyMode!;if(mode===next)return;
   const position=mode==='film'?(pendingFilmTime??film.currentTime):seconds;
   sceneAutomatic=false;automatic.manual();stop();film.pause();seconds=position;mode=next;
   root.dataset.storyModeActive=mode;stage.hidden=mode!=='scene';film.hidden=mode!=='film';
   if(mode==='scene'){lastProgress=-1;mountVisual();}
   modes.forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
   pendingFilmTime=mode==='film'?seconds:null;
   if(mode==='film'&&film.readyState===0){film.preload='metadata';film.load();}
   alignFilm();
  }));
  film.addEventListener('loadedmetadata',alignFilm);
  for(const event of ['play','pause','ended','timeupdate'])film.addEventListener(event,paint);
  const preference=()=>{if(motionPreference.matches){stop();seconds=20;film.pause();}paint();};
  motionPreference.addEventListener('change',preference);
  const hidden=()=>{if(document.hidden)film.pause();};document.addEventListener('visibilitychange',hidden);
  const restore=(event:PageTransitionEvent)=>{if(event.persisted){if(mode==='scene'&&sceneAutomatic)automatic.automatic();else paint();}};
  window.addEventListener('pageshow',restore);
  window.addEventListener('pagehide',event=>{stop();film.pause();if(event.persisted)return;alive=false;visual?.dispose();automatic.dispose();motionPreference.removeEventListener('change',preference);document.removeEventListener('visibilitychange',hidden);window.removeEventListener('pageshow',restore);});
  paint();root.dataset.storyReady='true';
 }
}
