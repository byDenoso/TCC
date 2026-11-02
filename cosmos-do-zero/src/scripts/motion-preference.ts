/** A preferência do sistema sempre prevalece; a escolha local vale em todas as experiências. */
export type MotionLevel = 'full' | 'gentle' | 'reduced';
const system = matchMedia('(prefers-reduced-motion: reduce)');
let chosen: MotionLevel = 'full';
try { const saved=localStorage.getItem('cosmos-motion'); if(saved==='gentle'||saved==='reduced')chosen=saved; } catch { /* preferência desta sessão */ }
const events = new EventTarget();
export const motionPreference = {
 get matches(): boolean { return system.matches || chosen==='reduced'; },
 addEventListener(_type: 'change', listener: EventListenerOrEventListenerObject): void { events.addEventListener('change', listener); },
 removeEventListener(_type: 'change', listener: EventListenerOrEventListenerObject): void { events.removeEventListener('change', listener); }
};
export const motionFactor = (): number => chosen==='gentle' ? .55 : 1;
const sync=()=>{
 document.documentElement.dataset.motion=motionPreference.matches?'reduced':chosen;
 events.dispatchEvent(new Event('change'));
 document.dispatchEvent(new CustomEvent('cosmos:motionchange'));
};
system.addEventListener('change',sync);
export function initMotionPreference(): void {
 const select=document.querySelector<HTMLSelectElement>('[data-motion-select]');
 if(select){select.value=chosen;select.addEventListener('change',()=>{
  chosen=select.value as MotionLevel;
  try{localStorage.setItem('cosmos-motion',chosen);}catch{/* sessão */}
  sync();
 });}
 window.addEventListener('storage',event=>{if(event.key==='cosmos-motion'){chosen=event.newValue==='gentle'||event.newValue==='reduced'?event.newValue:'full';if(select)select.value=chosen;sync();}});
 sync();
}
