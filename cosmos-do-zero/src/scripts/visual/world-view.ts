import { u } from '../../lib/url';

export function frameUrl(body: string, frame = 0): string {
  return u(`/models/solar-turntable/${body}/${String(frame).padStart(2, '0')}.webp`);
}

export function frameSources(body: string, frame = 0): string {
  const name = String(frame).padStart(2, '0');
  const compact = body === 'terra' || body.startsWith('terra-')
    ? `${u(`/models/worlds-hd/compact/${body}/${name}.webp`)} 448w`
    : `${frameUrl(body, frame)} 320w`;
  return `${compact}, ${u(`/models/worlds-hd/${body}/${name}.webp`)} 1024w`;
}

/** The two discs in a comparison always share angle and magnification. */
export function mountWorldView(root: HTMLElement, stage: HTMLElement, names: () => string[]) {
  const images = [...stage.querySelectorAll<HTMLImageElement>('img')];
  const angle = root.querySelector<HTMLInputElement>('[data-world-angle]')!;
  const zoom = root.querySelector<HTMLInputElement>('[data-world-zoom]')!;
  const angleLabel = root.querySelector<HTMLOutputElement>('[data-world-degrees]')!;
  const zoomLabel = root.querySelector<HTMLOutputElement>('[data-world-percent]')!;
  const signal = new AbortController();
  const opts = { signal: signal.signal };
  const failed = new Set<string>();
  let frame = 0;
  const refresh = () => {
    const bodies = names();
    images.forEach((image, i) => {
      const src = frameUrl(bodies[i], frame);
      const magnification = Number(zoom.value) / 100;
      const parentWidth = image.parentElement?.clientWidth ?? 0;
      const width = image.style.width.endsWith('%')
        ? parentWidth * parseFloat(image.style.width) / 100
        : Math.min(image.clientWidth, image.clientHeight || image.clientWidth);
      if (width > 0) image.sizes = `${Math.ceil(width * magnification)}px`;
      if (failed.has(src)) image.removeAttribute('srcset');
      else {
        const candidates = frameSources(bodies[i], frame);
        if (image.getAttribute('srcset') !== candidates) image.srcset = candidates;
      }
      if (image.getAttribute('src') !== src) image.src = src;
      image.style.scale = String(magnification);
    });
    angle.value = String(frame);
    angleLabel.value = `${frame * 10}°`;
    angle.setAttribute('aria-valuetext', angleLabel.value);
    zoomLabel.value = `${zoom.value}%`;
  };
  const setFrame = (n: number) => {
    frame = ((Math.round(n) % 36) + 36) % 36;
    refresh();
  };
  images.forEach((image, i) => image.addEventListener('error', () => {
    if (!image.getAttribute('src')?.includes('/solar-turntable/')) return;
    if (image.currentSrc.includes('/worlds-hd/') && image.hasAttribute('srcset')) {
      failed.add(frameUrl(names()[i], frame));
      image.removeAttribute('srcset');
      return;
    }
    stage.dispatchEvent(new Event('worldmanual'));
    if (frame !== 0) {
      setFrame(0);
      return;
    }
    const body = names()[i];
    const portrait = body.startsWith('terra-') ? 'terra' : body;
    image.removeAttribute('srcset');
    image.src = u(`/models/portraits/${portrait}.webp`);
  }, opts));
  const manual = () => stage.dispatchEvent(new Event('worldmanual'));
  angle.addEventListener('input', () => { manual(); setFrame(+angle.value); }, opts);
  zoom.addEventListener('input', refresh, opts);
  let drag: { id: number; x: number; frame: number } | undefined;
  stage.style.touchAction = 'pan-y pinch-zoom';
  stage.addEventListener('dragstart', e => e.preventDefault(), opts);
  stage.addEventListener('pointerdown', e => {
    if (!e.isPrimary || e.button !== 0) return;
    drag = { id: e.pointerId, x: e.clientX, frame };
    stage.setPointerCapture(e.pointerId);
  }, opts);
  stage.addEventListener('pointermove', e => {
    if (!drag || drag.id !== e.pointerId) return;
    const steps = Math.round((e.clientX - drag.x) / 10);
    if (steps || frame !== drag.frame) { manual(); setFrame(drag.frame + steps); }
  }, opts);
  stage.addEventListener('lostpointercapture', () => { drag = undefined; }, opts);
  const resize = new ResizeObserver(refresh);
  resize.observe(stage);
  window.addEventListener('pagehide', e => {
    if (!e.persisted) { resize.disconnect(); signal.abort(); }
  }, opts);
  refresh();
  return { refresh, setFrame, advance: (delta = 1) => setFrame(frame + delta) };
}
