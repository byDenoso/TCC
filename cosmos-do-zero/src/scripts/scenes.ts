/** Conceptual teaching scenes. Motion requires an explicit action and stops out of view. */
export function initScenes(): void {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  for (const root of document.querySelectorAll<HTMLElement>('[data-scene]')) {
    const status = root.querySelector<HTMLElement>('[data-scene-status]')!;
    let stopMotion = () => {};
    const stopIfHidden = () => { if (document.hidden) stopMotion(); };
    document.addEventListener('visibilitychange', stopIfHidden);
    reduced.addEventListener('change', () => { if (reduced.matches) stopMotion(); });
    if ('IntersectionObserver' in window) new IntersectionObserver(([entry]) => { if (!entry.isIntersecting) stopMotion(); }, { threshold: .05 }).observe(root);
    if (root.dataset.scene === 'scale') {
      const buttons = [...root.querySelectorAll<HTMLButtonElement>('[data-scale-step]')];
      const panels = [...root.querySelectorAll<HTMLElement>('[data-scale-panel]')];
      const visuals = [...root.querySelectorAll<HTMLImageElement>('[data-scale-visual]')];
      const select = (index: number) => {
        buttons.forEach((b, i) => b.setAttribute('aria-pressed', String(i === index)));
        panels.forEach((p, i) => p.hidden = i !== index);
        visuals.forEach((v,i) => v.dataset.hidden = String(i !== index));
        status.textContent = `Escala ${index + 1} de 5: ${buttons[index].textContent?.split('·')[1]?.trim()}. ${panels[index].querySelector('.scene-unit')?.textContent}. Quadros conceituais; não é um zoom em escala contínua.`;
      };
      buttons.forEach((b,i) => b.addEventListener('click', () => select(i)));
      select(0);
      const play = root.querySelector<HTMLButtonElement>('[data-light-play]')!;
      const pulse = root.querySelector<SVGCircleElement>('[data-light-pulse]')!;
      const lightStatus = root.querySelector<HTMLElement>('[data-light-status]')!;
      let frame = 0, position = 0, last = 0, playing = false;
      stopMotion = () => { if (playing && position < 1) lightStatus.textContent = 'Viagem pausada. Inicie novamente para acompanhar o restante do trajeto.'; playing = false; cancelAnimationFrame(frame); play.setAttribute('aria-pressed','false'); play.textContent = position >= 1 ? 'Repetir viagem da luz' : position > 0 ? 'Continuar viagem da luz' : 'Iniciar viagem da luz'; };
      const tick = (now: number) => {
        if (!playing) return;
        if (last) position = Math.min(1, position + Math.min(now-last, 80)/4200);
        last = now; pulse.setAttribute('cx', String(45 + position * 405));
        if (position >= 1) { stopMotion(); lightStatus.textContent = 'A luz chegou. Você recebe agora a informação emitida antes pela fonte.'; }
        else frame = requestAnimationFrame(tick);
      };
      play.addEventListener('click', () => {
        if (playing) { stopMotion(); lightStatus.textContent = 'Viagem pausada. A luz leva tempo para transportar informação.'; return; }
        if (reduced.matches) { position = position >= 1 ? 0 : 1; pulse.setAttribute('cx', String(45+405*position)); lightStatus.textContent = position ? 'Estado final: a luz chegou. Movimento reduzido: o trajeto muda sem animação.' : 'Estado inicial: pulso na fonte. Movimento reduzido: o trajeto muda sem animação.'; stopMotion(); return; }
        if (position >= 1) position = 0;
        playing = true; last = 0; play.textContent = 'Pausar viagem da luz'; play.setAttribute('aria-pressed','true'); lightStatus.textContent = 'A luz está em viagem. A imagem recebida será do passado da fonte.'; frame = requestAnimationFrame(tick);
      });
    }
    if (root.dataset.scene === 'expansion') {
      const range = root.querySelector<HTMLInputElement>('[data-expansion-scale]')!;
      const observer = root.querySelector<HTMLSelectElement>('[data-expansion-observer]')!;
      const output = root.querySelector<HTMLOutputElement>('[data-expansion-value]')!;
      const play = root.querySelector<HTMLButtonElement>('[data-expansion-play]')!;
      const wave = root.querySelector<SVGPathElement>('[data-expansion-wave]')!;
      let frame = 0, playing = false;
      const render = () => {
        const scale = Number(range.value);
        output.value = `${scale.toFixed(2).replace('.',',')} ×`;
        const chosen = root.querySelector<SVGGElement>(`[data-galaxy-id="${observer.value}"]`)!;
        const observerX = Number(chosen.dataset.x), observerY = Number(chosen.dataset.y);
        for (const galaxy of root.querySelectorAll<SVGGElement>('[data-expansion-galaxy]')) {
          galaxy.setAttribute('transform', `translate(${(Number(galaxy.dataset.x)-observerX)*scale} ${(Number(galaxy.dataset.y)-observerY)*scale})`);
          const selected = galaxy.dataset.galaxyId === observer.value;
          galaxy.dataset.observer = String(selected);
          const ring = galaxy.querySelector('[data-observer-ring]')!;
          ring.setAttribute('data-hidden',String(galaxy.dataset.galaxyId !== observer.value));
        }
        let path = 'M20 62';
        for(let x=20; x<=280; x+=2) path += `L${x} ${62-25*Math.sin((x-20)*Math.PI/(20*scale))}`;
        wave.setAttribute('d',path);
        status.textContent = `Fator de escala ${output.value}. Observador: ${observer.selectedOptions[0].textContent?.toLowerCase()}. Todas as separações crescem pelo mesmo fator; o sistema ligado mantém seu tamanho.`;
      };
      stopMotion = () => { playing = false; cancelAnimationFrame(frame); play.setAttribute('aria-pressed','false'); play.textContent = Number(range.value)>=1.6 ? 'Repetir expansão' : 'Animar a expansão'; };
      // Preserve sub-step precision: range inputs quantize .01, so accumulate time separately.
      let startScale = 1, startTime = 0;
      const animate = (now: number) => {
        if (!playing) return;
        if (!startTime) startTime = now;
        range.value = String(Math.min(1.6, startScale+(now-startTime)*.00012)); render();
        if(Number(range.value)>=1.6) stopMotion(); else frame=requestAnimationFrame(animate);
      };
      range.addEventListener('input', () => { stopMotion(); render(); }); observer.addEventListener('change', render);
      play.addEventListener('click', () => {
        if (playing) { stopMotion(); return; }
        if (reduced.matches) { range.value = Number(range.value)>=1.6 ? '1' : '1.6'; render(); stopMotion(); return; }
        if (Number(range.value)>=1.6) range.value='1';
        playing=true; startScale=Number(range.value); startTime=0; play.setAttribute('aria-pressed','true'); play.textContent='Pausar expansão'; frame=requestAnimationFrame(animate);
      }); render();
    }
    if (root.dataset.scene === 'evidence') {
      const buttons=[...root.querySelectorAll<HTMLButtonElement>('[data-evidence-select]')];
      const panels=[...root.querySelectorAll<HTMLElement>('[data-evidence-panel]')];
      const select=(index:number) => { buttons.forEach((b,i) => b.setAttribute('aria-pressed',String(i===index))); panels.forEach((p,i) => p.hidden=i!==index); status.textContent=`Evidência: ${panels[index].querySelector('h3')?.textContent}. Leia a observação, a explicação e a questão aberta.`; };
      buttons.forEach((b,i) => b.addEventListener('click',() => select(i))); select(0);
    }
  }
}
