import settings from '../../public/models/saturn/scene.json';
import { u } from '../lib/url';
import { mountWithGpu } from './visual/gpu-lease';
import type { SaturnView } from './visual/saturn-view';

export function initSaturn(): void {
  const element = document.querySelector<HTMLElement>('[data-saturn]');
  if (!element || element.dataset.controlsReady) return;
  const root: HTMLElement = element;

  const stage = root.querySelector<HTMLElement>('[data-saturn-stage]')!;
  const slider = root.querySelector<HTMLInputElement>('[data-saturn-slider]')!;
  const output = root.querySelector<HTMLOutputElement>('[data-saturn-angle]')!;
  const presets = root.querySelectorAll<HTMLButtonElement>('[data-saturn-preset]');
  const rings = root.querySelectorAll<SVGGElement>('[data-saturn-rings]');
  const globe = root.querySelectorAll<SVGEllipseElement>('[data-saturn-globe]');
  const edge = root.querySelector<SVGPathElement>('[data-saturn-edge]')!;
  const unit = 960 / settings.camera.frameWidth;
  const modelUrl = u(`/models/saturn/${settings.model}`);
  let view: SaturnView | null = null;
  let pending: AbortController | null = null;
  let bytes: ArrayBuffer | undefined;
  let visible = false;
  let failed = false;
  let revoked = false;

  function setAngle(degrees: number) {
    slider.value = String(degrees);
    slider.setAttribute('aria-valuetext', `${degrees} graus${degrees === settings.camera.edgeAngle ? ', de perfil' : ''}`);
    output.value = `${degrees}°`;
    const radians = degrees * Math.PI / 180;
    const opening = Math.sin(radians);
    const height = unit * Math.hypot(settings.geometry.polarRadius * Math.cos(radians), opening);
    for (const ring of rings) ring.setAttribute('transform', `scale(1 ${opening})`);
    for (const ellipse of globe) ellipse.setAttribute('ry', String(height));
    edge.setAttribute('visibility', degrees === settings.camera.edgeAngle ? 'visible' : 'hidden');
    for (const button of presets) button.setAttribute('aria-pressed', String(degrees === Number(button.dataset.saturnPreset)));
    view?.setAngle(degrees);
  }

  function stop(): void {
    const request = pending;
    pending = null;
    request?.abort();
    view?.dispose();
    view = null;
  }

  async function readModel(signal: AbortSignal) {
    const response = await fetch(modelUrl, { signal });
    if (!response.ok) throw new Error(`Saturn GLB: HTTP ${response.status}`);
    return response.arrayBuffer();
  }

  function start(): void {
    if (!visible || document.hidden || pending || view || failed || revoked) return;
    const request = new AbortController();
    pending = request;
    const valid = () => pending === request && !request.signal.aborted && visible && !document.hidden && root.isConnected && !root.closest('[hidden]');
    void (async () => {
      const timeout = window.setTimeout(() => { if (valid()) { failed = true; request.abort(); } }, 10000);
      try {
        // Give the diagram and the native controls a paint before either download.
        await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
        if (!valid()) return;
        const [{ createSaturnView }, model] = await Promise.all([import('./visual/saturn-view'), bytes ?? readModel(request.signal)]);
        if (!valid()) return;
        bytes = model;
        const mounted = await mountWithGpu(valid, () => createSaturnView(stage, modelUrl, model, {
          angle: () => Number(slider.value),
          signal: request.signal,
          valid,
          released(reason) {
            view = null;
            if (reason === 'revoked') revoked = true;
            if (reason === 'failed') failed = true;
          }
        }));
        if (valid() && mounted) view = mounted;
        else mounted?.dispose();
      } catch {
        if (valid()) failed = true;
      } finally {
        clearTimeout(timeout);
        if (pending === request) pending = null;
      }
    })();
  }

  const onControl = () => {
    revoked = false;
    start();
  };
  slider.disabled = false;
  slider.addEventListener('input', () => { setAngle(Number(slider.value)); onControl(); });
  for (const button of presets) {
    button.disabled = false;
    button.addEventListener('click', () => { setAngle(Number(button.dataset.saturnPreset)); onControl(); });
  }
  setAngle(Number(slider.value));
  root.dataset.controlsReady = 'true';
  performance.mark('saturn:controls-ready');

  if (typeof IntersectionObserver === 'undefined') return;
  const observer = new IntersectionObserver(([entry]) => {
    visible = !!entry?.isIntersecting;
    if (!visible) stop();
    else start();
  }, { threshold: .12 });
  observer.observe(stage);
  window.addEventListener('pagehide', event => {
    stop();
    if (!event.persisted) observer.disconnect();
  });
  window.addEventListener('pageshow', event => { if (event.persisted) start(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else start(); });
}
