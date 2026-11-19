import settings from '../../public/models/saturn/scene.json';

export function initSaturn(): void {
  const root = document.querySelector<HTMLElement>('[data-saturn]');
  if (!root || root.dataset.controlsReady) return;
  const stage = root.querySelector<HTMLElement>('[data-saturn-stage]')!;
  const image = stage.querySelector<HTMLImageElement>('[data-saturn-frame]')!;
  const slider = root.querySelector<HTMLInputElement>('[data-saturn-slider]')!;
  const output = root.querySelector<HTMLOutputElement>('[data-saturn-angle]')!;
  const presets = root.querySelectorAll<HTMLButtonElement>('[data-saturn-preset]');
  const rings = stage.querySelectorAll<SVGGElement>('[data-saturn-rings]');
  const globe = stage.querySelectorAll<SVGEllipseElement>('[data-saturn-globe]');
  const edge = stage.querySelector<SVGPathElement>('[data-saturn-edge]')!;
  const unit = globe[0].rx.baseVal.value;
  let pending = 0;

  function source(degree: number) {
    const file = degree === settings.camera.openAngle ? 'poster.webp' : `frames/${String(degree).padStart(2, '0')}.webp`;
    return `${stage.dataset.media}/${file}`;
  }

  function showLoaded() {
    const current = image.getAttribute('src') === source(Number(slider.value));
    if (current && !image.complete && image.loading === 'lazy') return;
    image.hidden = !(current && image.complete && image.naturalWidth > 0);
    stage.dataset.renderer = image.hidden ? 'diagram' : 'webp';
    if (!image.hidden && !performance.getEntriesByName('saturn:first-image').length) {
      performance.mark('saturn:first-image');
    }
  }

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

    cancelAnimationFrame(pending);
    showLoaded();
    if (image.getAttribute('src') !== source(degrees) || (image.complete && !image.naturalWidth)) {
      pending = requestAnimationFrame(() => {
        image.loading = 'eager';
        image.src = source(degrees);
      });
    }
  }

  image.addEventListener('load', showLoaded);
  image.addEventListener('error', showLoaded);
  slider.disabled = false;
  slider.addEventListener('input', () => setAngle(Number(slider.value)));
  for (const button of presets) {
    button.disabled = false;
    button.addEventListener('click', () => setAngle(Number(button.dataset.saturnPreset)));
  }
  setAngle(Number(slider.value));
  root.dataset.controlsReady = 'true';
  performance.mark('saturn:controls-ready');
}
