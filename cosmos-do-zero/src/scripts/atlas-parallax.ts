type Scene = Awaited<ReturnType<typeof import('./atlas-parallax-scene').openInstrument>>;
const fmt = (number: number) => number.toLocaleString('pt-BR', { maximumFractionDigits: 2 });

export function bindParallax(root: HTMLElement) {
  const get = <T extends HTMLElement>(query: string) => root.querySelector<T>(query)!;
  const slider = get<HTMLInputElement>('input[type=range]');
  const button = get<HTMLButtonElement>('[data-open]');
  const top = get<HTMLButtonElement>('[data-top]');
  const canvas = get<HTMLCanvasElement>('canvas');
  const status = get('[data-status]');
  let scene: Scene | undefined;
  let dead = false;
  function update() {
    const distance = Number(slider.value);
    const angle = 1 / distance;
    const seconds = (n: number) => n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 3 }) + '″';
    const guess = root.querySelector<HTMLInputElement>('input[type=radio]:checked')?.value;
    get('[data-distance]').textContent = fmt(distance) + ' pc';
    slider.setAttribute('aria-valuetext', fmt(distance) + (distance === 1 ? ' parsec' : ' parsecs'));
    get('[data-p]').textContent = seconds(angle);
    get('[data-total]').textContent = seconds(2 * angle);
    root.querySelector('[data-trace-a]')!.setAttribute('transform', `translate(${295+230*angle} 0)`);
    root.querySelector('[data-trace-b]')!.setAttribute('transform', `translate(${295-230*angle} 0)`);
    const feedback = get('[data-feedback]');
    if (distance === 8) {
      const verdict = guess == null ? '' : guess === '0' ? 'Seu palpite confere. ' : 'Compare com a previsão. ';
      feedback.textContent = verdict + 'De 4 para 8 pc, a separação cai de 0,50″ para 0,25″. Dobrar a distância reduz a paralaxe à metade.';
    } else {
      feedback.textContent = `A ${fmt(distance)} pc, a separação A–B é ${seconds(2*angle)}. ` +
        (guess == null ? 'Faça uma previsão e teste 8 pc.' : 'Leve a régua até 8 pc para conferir sua previsão.');
    }
    scene?.setDistance(distance);
  }
  root.addEventListener('input', update);
  button.addEventListener('click', async () => {
    if (scene) {
      scene.dispose(); scene = undefined;
      canvas.hidden = top.hidden = true;
      top.setAttribute('aria-pressed', 'false');
      button.setAttribute('aria-pressed','false');
      button.textContent = 'Explorar a maquete em 3D';
      status.textContent = '';
      return;
    }
    button.disabled = true;
    status.textContent = 'Carregando a maquete…';
    try {
      const { openInstrument } = await import('./atlas-parallax-scene');
      if (dead) return;
      canvas.hidden = false;
      scene = await openInstrument(canvas, root.dataset.model!);
      if (dead) { scene.dispose(); scene = undefined; return; }
      scene.setDistance(Number(slider.value));
      top.hidden = false;
      button.textContent = 'Fechar 3D';
      button.setAttribute('aria-pressed', 'true');
      status.textContent = 'Maquete pronta. Mova a régua para comparar as visadas.';
    } catch {
      canvas.hidden = true;
      status.textContent = 'O 3D está indisponível neste dispositivo. A régua angular continua ativa.';
    } finally { button.disabled = false; }
  });
  top.addEventListener('click', () => {
    const active = top.getAttribute('aria-pressed') !== 'true';
    top.setAttribute('aria-pressed', String(active));
    scene?.view(active);
  });
  window.addEventListener('pagehide', (event) => {
    if (event.persisted) return;
    dead = true;
    scene?.dispose();
  }, { once: true });
  update();
}
