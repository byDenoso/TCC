import { motionPreference } from './motion-preference';
import { terms } from '../data/client';
import { u } from '../lib/url';

/** Moldura compartilhada: informa o estado sem criar outro relógio de animação. */
export function initExperience(): void {
 const roots=document.querySelectorAll<HTMLElement>('[data-station],[data-sci-panel],[data-mx],[data-solar-studio]');
 for(const root of roots){
  const stage=root.querySelector<HTMLElement>('[data-e-volume],[data-sci-stage],.mx-stage,.obs-viz');
  if(!stage)continue;
  const toolbar=document.createElement('div');toolbar.className='experience-toolbar';
  const status=document.createElement('span');status.className='experience-status';status.textContent='Explore no seu ritmo';
  const expand=document.createElement('button');expand.type='button';expand.dataset.experienceExpand='';expand.textContent='Ampliar experiência ↗';
  toolbar.append(status,expand);
  const anchor=root.querySelector('.obs-grid,.sci-fig,.mx-lab,.solar-close-note')??stage;
  anchor.before(toolbar);
  let manual=false,visible=false;
  const update=()=>{
   const play=root.querySelector<HTMLElement>('[data-e-play],[data-sci-play],[data-mx-play],[data-solar-play],[data-3d-play]');
   const running=play?.getAttribute('aria-pressed')==='true';
   const range=root.querySelector<HTMLInputElement>('[data-e-range],[data-sci-range],[data-mx-range]');
   const complete=range&&Number(range.max)>Number(range.min)&&Number(range.value)>=Number(range.max);
   const text=play?.hasAttribute('disabled')?'Visualização estática disponível':motionPreference.matches?'Movimento reduzido · avance pelos controles':running&&visible?'Reproduzindo':complete?'Concluído · reveja ou compare':manual?'Pausado por você':visible?'Pronto para explorar':'Pausado fora da tela';
   if(status.textContent!==text)status.textContent=text;
   const state=running&&visible?'playing':complete?'complete':'paused';if(root.dataset.playback!==state)root.dataset.playback=state;
  };
  root.addEventListener('click',event=>{const target=(event.target as Element).closest('[data-e-play],[data-sci-play],[data-mx-play],[data-solar-play]');if(target){manual=true;queueMicrotask(update);}});
  root.addEventListener('click',event=>{
   const guess=(event.target as Element).closest<HTMLElement>('[data-opt],[data-mx-guess]');if(!guess)return;
   const result=root.querySelector<HTMLElement>('[data-guess-result],.mx-verdict');if(!result)return;
   queueMicrotask(()=>{let note=result.querySelector<HTMLElement>('[data-prediction]');if(!note){note=document.createElement('p');note.dataset.prediction='';note.className='prediction-recall';result.prepend(note);}note.textContent=`Seu palpite: ${guess.textContent?.trim().replace(/^[A-E](?=\S)/,'')}. Compare com a explicação e a figura.`;});
  });
  root.addEventListener('input',()=>{manual=true;update();});
  root.addEventListener('focusin',event=>{if((event.target as Element).closest('input,select,[data-e-target]'))stage.dataset.focusDiagram='true';});
  root.addEventListener('focusout',()=>{delete stage.dataset.focusDiagram;});
  new MutationObserver(update).observe(root,{subtree:true,attributes:true,attributeFilter:['aria-pressed','disabled']});
  new IntersectionObserver(([e])=>{visible=e.isIntersecting;update();},{threshold:.15}).observe(stage);
  document.addEventListener('cosmos:motionchange',update);
  expand.addEventListener('click',()=>{
   const position=window.scrollY,placeholder=document.createComment('posição da experiência');
   root.before(placeholder);
   const dialog=document.createElement('dialog');dialog.className='experience-dialog';dialog.setAttribute('aria-label',root.querySelector('h3,h2')?.textContent?.trim()||'Experiência ampliada');
   const close=document.createElement('button');close.type='button';close.className='experience-close';close.textContent='Fechar experiência ×';
   placeholder.parentElement!.append(dialog);dialog.append(close,root,panel);root.dataset.expanded='true';
   const finish=()=>{panel.hidePopover();document.body.append(panel);delete root.dataset.expanded;placeholder.replaceWith(root);dialog.remove();window.scrollTo({top:position,behavior:'instant'});expand.focus({preventScroll:true});window.dispatchEvent(new Event('resize'));};
   dialog.addEventListener('close',finish,{once:true});close.addEventListener('click',()=>dialog.close());
   dialog.showModal();close.focus();window.dispatchEvent(new Event('resize'));
  });
 }
 // Definições próximas à leitura: uma seleção deliberada, sem transformar todo o texto em links.
 const panel=document.createElement('div');panel.className='term-pop';panel.id='cosmos-term';panel.setAttribute('popover','auto');document.body.append(panel);
 for(const block of document.querySelectorAll<HTMLElement>('.lesson-section,.obs-station,.sci-panel')){
  const text=block.textContent?.toLocaleLowerCase('pt-BR')??'';
  const matches=terms.filter(term=>text.includes(term.term.toLocaleLowerCase('pt-BR').replace(' (cmb)',''))).slice(0,3);
  if(!matches.length)continue;
  const bar=document.createElement('div');bar.className='experience-terms';bar.append('Entenda os termos: ');
  for(const term of matches){const button=document.createElement('button');button.type='button';button.textContent=term.term;button.setAttribute('popovertarget',panel.id);
   button.addEventListener('click',()=>{panel.replaceChildren();const strong=document.createElement('strong');strong.textContent=term.term;const definition=document.createElement('p');definition.textContent=term.definition;const example=document.createElement('em');example.textContent=term.example;const link=document.createElement('a');link.textContent='Explorar o dicionário ↗';link.href=u('/glossario/');panel.append(strong,definition,example,link);});bar.append(button);}
  block.append(bar);
 }
 // O layout acompanha a altura real das barras, inclusive com zoom do navegador.
 const header=document.querySelector<HTMLElement>('.header-shell');if(header)new ResizeObserver(()=>document.documentElement.style.setProperty('--header-clearance',`${Math.ceil(header.getBoundingClientRect().height)+24}px`)).observe(header);
 const observer=new MutationObserver(()=>{const bar=document.querySelector<HTMLElement>('.lesson-stepper');if(!bar)return;observer.disconnect();new ResizeObserver(()=>document.documentElement.style.setProperty('--lesson-clearance',`${Math.ceil(bar.getBoundingClientRect().height)+32}px`)).observe(bar);});observer.observe(document.body,{childList:true,subtree:true});
}
