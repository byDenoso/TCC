import { cmbSphere } from './cmb-sphere';
import { cmbTemperature, inCmbMap } from '../lib/cmb-map';

export function initCmb(): void {
  const root = document.querySelector<HTMLElement>('[data-cmb]');
  const frame = root?.querySelector<HTMLElement>('[data-cmb-frame]');
  const canvas = root?.querySelector<HTMLCanvasElement>('[data-cmb-canvas]');
  const poster = root?.querySelector<HTMLImageElement>('[data-cmb-poster]');
  const probe = root?.querySelector<HTMLElement>('[data-cmb-probe]');
  const read = root?.querySelector<HTMLElement>('[data-cmb-read]');
  if (!frame || !canvas || !poster || !probe || !read) return;

  // The poster and temperature probe use the same deterministic field.
  void poster.decode().then(() => {
    const context = canvas.getContext('2d');
    if (!context) return;
    context.drawImage(poster, 0, 0, canvas.width, canvas.height);
    canvas.hidden = false;
    poster.hidden = true;
  }).catch(() => { /* Keep the HTML map and its controls available. */ });

  const pointGlobe = cmbSphere(root!.querySelector('[data-cmb-sphere]'), poster);
  let xPosition = 0.5;
  let yPosition = 0.5;
  const format = new Intl.NumberFormat('pt-BR');
  const show = (x: number, y: number) => {
    if (!inCmbMap(x, y) || (!probe.hidden && x === xPosition && y === yPosition)) return;
    pointGlobe(x,y);
    xPosition = x;
    yPosition = y;
    probe.hidden = false;
    probe.style.left = `${x * 100}%`;
    probe.style.top = `${y * 100}%`;
    const temperature = cmbTemperature(x, y);
    const difference = Math.abs(temperature);
    read.textContent = difference < 8
      ? 'No mapa simulado, a temperatura deste ponto está quase na média.'
      : `No mapa simulado, este ponto está ${format.format(difference)} milionésimos de kelvin ${temperature > 0 ? 'acima' : 'abaixo'} da média.`;
  };
  const selectFromPointer = (event: PointerEvent) => {
    const bounds = frame.getBoundingClientRect();
    show((event.clientX - bounds.left) / bounds.width, (event.clientY - bounds.top) / bounds.height);
  };
  frame.addEventListener('pointermove', event => {
    if (event.pointerType !== 'touch') selectFromPointer(event);
  });
  frame.addEventListener('pointerdown', selectFromPointer);

  const offsets: Record<string, [number, number]> = {
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
    ArrowUp: [0, -2],
    ArrowDown: [0, 2]
  };
  frame.addEventListener('keydown', event => {
    const offset = offsets[event.key];
    if (!offset) return;
    event.preventDefault();
    const step = event.shiftKey ? 0.08 : 0.025;
    // Shorten the last step to keep navigation inside the oval.
    for (let length = step; length >= 0.001; length /= 2) {
      const x = xPosition + offset[0] * length;
      const y = yPosition + offset[1] * length;
      if (!inCmbMap(x, y)) continue;
      show(x, y);
      break;
    }
  });
  frame.addEventListener('focus', () => show(xPosition, yPosition));
}
