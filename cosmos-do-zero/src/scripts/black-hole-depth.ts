import { baked, depthCanvas } from './lesson-depth';
import { visibleMotion } from './visible-motion';
import { motionPreference } from './motion-preference';

export function initBlackHoleDepth() {
  for (const plate of document.querySelectorAll<HTMLElement>(
    '[data-bh-stage]',
  )) {
    const kind = plate.dataset.bhStage;
    const range = plate.querySelector<HTMLInputElement>('input');
    const canvas = plate.querySelector<HTMLCanvasElement>('canvas');
    const play = plate.querySelector<HTMLButtonElement>('[data-bh-play]');
    const output = plate.querySelector('output');
    if (!range || !canvas || !play || !output) continue;
    let value = Number(range.value),
      frame = 0,
      last = 0,
      playing = false;
    const maximum = Number(range.max);
    const paint = depthCanvas(canvas, (ctx, image) => {
      if (kind === 'orbitas') {
        const mean = (value / maximum) * Math.PI * 2;
        const e = Math.sqrt(1 - (105 / 178) ** 2);
        let eccentric = mean;
        for (let i = 0; i < 10; i++)
          eccentric -=
            (eccentric - e * Math.sin(eccentric) - mean) /
            (1 - e * Math.cos(eccentric));
        const x = 265 + 178 * Math.cos(eccentric),
          y = 154 + 105 * Math.sin(eccentric);
        const star = image(baked('star'));
        if (!star) return;
        ctx.drawImage(star, x - 10, y - 10, 20, 20);
        ctx.fillStyle = '#ffc16a';
        ctx.font = 'bold 16px sans-serif';
        ctx.fillText('S2', x - 12, y - 21);
      } else if (kind === 'acrecao') {
        const disk = image(baked('disk'));
        if (!disk) return;
        ctx.drawImage(disk, 100, -2, 334, 334);
        const angle = (value / maximum) * Math.PI * 2;
        const x = 267 + 125 * Math.cos(angle),
          y = 165 + 36 * Math.sin(angle);
        if (Math.sin(angle) > 0 || Math.abs(x - 267) > 43) {
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, 2 * Math.PI);
          ctx.fillStyle = '#fff6c9';
          ctx.fill();
        }
      } else {
        const field = image(baked('stars-far'));
        if (!field) return;
        // Clip the background field outside the causal boundary.
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, 560, 310);
        ctx.arc(270, 163, 74, 0, 2 * Math.PI, true);
        ctx.clip('evenodd');
        ctx.globalAlpha = 0.55;
        ctx.drawImage(field, 0, 0, 560, 310);
        ctx.restore();
        // Only the particles are animated here. The dashed circle defines the horizon in the diagram.
        const t = value / maximum;
        for (const x of [80 + 190 * t, 372 + 115 * t]) {
          ctx.beginPath();
          ctx.arc(x, x < 300 ? 170 : 156, 5, 0, 2 * Math.PI);
          ctx.fillStyle = '#ffbd64';
          ctx.fill();
        }
      }
      plate.dataset.bhReady = 'true';
    });
    function update() {
      range!.value = String(value);
      const unit =
        kind === 'orbitas' ? ' anos' : kind === 'acrecao' ? '°' : '%';
      output!.textContent = Number(range!.value).toLocaleString('pt-BR') + unit;
      range!.setAttribute('aria-valuetext', output!.textContent);
      paint();
    }
    function stop() {
      cancelAnimationFrame(frame);
      playing = false;
      last = 0;
      play!.textContent = motionPreference.matches ? 'Avançar' : 'Reproduzir';
      play!.setAttribute('aria-pressed', 'false');
    }
    function tick(now: number) {
      if (!playing) return;
      if (last)
        value =
          (value + (Math.min(64, now - last) / 12000) * maximum) % maximum;
      last = now;
      update();
      frame = requestAnimationFrame(tick);
    }
    const motion = visibleMotion(canvas, {
      start() {
        playing = true;
        play.textContent = 'Pausar';
        play.setAttribute('aria-pressed', 'true');
        frame = requestAnimationFrame(tick);
      },
      stop,
      running: () => playing,
    });
    motion.manual();
    range.addEventListener('input', () => {
      motion.manual();
      stop();
      value = range.valueAsNumber;
      update();
    });
    play.addEventListener('click', () => {
      if (playing) {
        motion.manual();
        stop();
      } else if (motionPreference.matches) {
        value = value >= maximum ? 0 : Math.min(maximum, value + maximum / 8);
        update();
      } else motion.automatic();
    });
    motionPreference.addEventListener('change', stop);
    window.addEventListener('pagehide', (e) => {
      stop();
      if (!e.persisted) {
        motion.dispose();
        motionPreference.removeEventListener('change', stop);
      }
    });
    stop();
    update();
  }
}
