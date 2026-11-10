import { observedWavelengthNm } from '../lib/cosmology';
import { motionPreference } from './motion-preference';

const decimal = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const wavelength = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function initLightExhibit(): void {
  const exhibit = document.querySelector<HTMLElement>('[data-light-exhibit]');
  if (!exhibit) return;
  const steps = [...exhibit.querySelectorAll<HTMLElement>('[data-light-step]')];
  const buttons = [...exhibit.querySelectorAll<HTMLButtonElement>('[data-light-go]')];
  const photo = exhibit.querySelector<HTMLElement>('[data-light-view="photo"]')!;
  const spectrum = exhibit.querySelector<HTMLElement>('[data-light-view="spectrum"]')!;
  const kind = exhibit.querySelector<HTMLElement>('[data-light-kind]')!;
  const control = exhibit.querySelector<HTMLElement>('[data-light-control]')!;
  const lineMode = exhibit.querySelector<HTMLElement>('[data-light-mode]')!;
  const modes = [...exhibit.querySelectorAll<HTMLButtonElement>('[data-light-kind-button]')];
  const caption = exhibit.querySelector<HTMLElement>('[data-light-caption]')!;
  const sample = exhibit.querySelector<HTMLElement>('[data-light-sample]')!;
  const wavelengths = {
    emission: [486.1, 500.7, 656.3], // Hβ, [O III], Hα
    absorption: [434.0, 486.1, 656.3] // Hγ, Hβ, Hα
  } as const;
  let mode: keyof typeof wavelengths = 'emission';
  const restLines = spectrum.querySelector<SVGPathElement>('.light-rest path')!;
  const plotX = (observed: number) => 40 + (observed - 400) * 0.6;
  const slider = exhibit.querySelector<HTMLInputElement>('#light-redshift')!;
  const lines = [...exhibit.querySelectorAll<SVGPathElement>('[data-light-line]')];
  const redshift = exhibit.querySelector<HTMLOutputElement>('[data-light-value]')!;
  const readout = exhibit.querySelector<HTMLElement>('[data-light-readout]')!;
  const scale = exhibit.querySelector<HTMLElement>('[data-light-scale]')!;
  const compact = matchMedia('(max-width: 720px)');
  const sticky = matchMedia('(min-height: 651px)');
  const example = Number(slider.defaultValue);
  const maxRedshift = Number(slider.max);
  let z = slider.valueAsNumber;
  let scene = -1;
  let manual = false;
  let visible = false;

  function show(index: number) {
    if (index === scene) return;
    scene = index;
    exhibit!.dataset.lightScene = String(index);
    kind.textContent = `0${index + 1} / ${steps[index].dataset.lightLabel}`;
    photo.hidden = index !== 0;
    spectrum.hidden = index === 0;
    control.hidden = index !== 2;
    lineMode.hidden = index === 0;
    steps.forEach((step, i) => { step.dataset.active = String(i === index); });
    buttons.forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
  }

  function updateSpectrum(next = z) {
    z = next;
    const wavelengthsNm = wavelengths[mode];
    restLines.setAttribute('d', wavelengthsNm.map((value) => `M${plotX(value)} 45v29`).join(''));
    lines.forEach((line, i) => {
      line.setAttribute('transform', `translate(${plotX(observedWavelengthNm(z, wavelengthsNm[i]))} 0)`);
    });
    redshift.value = decimal.format(z);
    sample.textContent = `z = ${redshift.value}`;
    slider.setAttribute('aria-valuetext', `z igual a ${redshift.value}`);
    readout.textContent = `${wavelength.format(observedWavelengthNm(z, wavelengthsNm[2]))} nm`;
    scale.textContent = decimal.format(1 / (1 + z));
  }

  const readingLine = () => window.innerHeight * (compact.matches ? 0.62 : 0.78);

  function syncToScroll() {
    if (!visible || !sticky.matches || document.hidden) return;
    // Use a line in the reading column so the active scene stays stable between panels.
    const line = readingLine();
    let index = 0;
    while (index + 1 < steps.length && steps[index + 1].getBoundingClientRect().top <= line) index++;
    show(index);
    if (index === 0 || manual || motionPreference.matches) return;
    const plot = spectrum.getBoundingClientRect();
    if (plot.bottom <= 0 || plot.top >= window.innerHeight) return;
    const step = steps[index].getBoundingClientRect();
    const progress = Math.max(0, Math.min(1, (line - step.top) / step.height));
    const next = index === 1 ? example * progress : example + (maxRedshift - example) * progress;
    if (next === z) return;
    slider.value = String(next);
    updateSpectrum(next);
  }

  let scrollFrame = 0;
  function onScroll() {
    if (scrollFrame) return;
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = 0;
      syncToScroll();
    });
  }
  if ('IntersectionObserver' in window) new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible) {
      window.addEventListener('scroll', onScroll, { passive: true });
      window.addEventListener('resize', onScroll);
      onScroll();
    } else {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      cancelAnimationFrame(scrollFrame);
      scrollFrame = 0;
    }
  }).observe(exhibit);
  buttons.forEach((button, i) => button.addEventListener('click', () => {
    show(i);
    if (!sticky.matches) return;
    if (compact.matches) {
      window.scrollBy({ top: steps[i].getBoundingClientRect().top - readingLine() + 12, behavior: 'instant' });
    } else {
      steps[i].scrollIntoView({ block: 'center', behavior: 'instant' });
    }
  }));
  slider.addEventListener('input', () => {
    manual = true;
    updateSpectrum(slider.valueAsNumber);
  });
  function setLineMode(next: keyof typeof wavelengths) {
    mode = next;
    spectrum.dataset.lineMode = mode;
    modes.forEach((item) => item.setAttribute('aria-pressed', String(item.dataset.lightKindButton === mode)));
    caption.textContent = mode === 'emission'
      ? 'Emissão calculada · Hβ, [O III] e Hα.'
      : 'Absorção calculada · Hγ, Hβ e Hα.';
    updateSpectrum();
  }

  modes.forEach((button) => button.addEventListener('click', () => {
    setLineMode(button.dataset.lightKindButton as keyof typeof wavelengths);
  }));
  exhibit.querySelectorAll<HTMLButtonElement>('[data-light-preset]').forEach((button) => {
    button.addEventListener('click', () => {
      manual = true;
      slider.value = button.dataset.lightPreset!;
      z = slider.valueAsNumber;
      if (z === example) setLineMode('emission');
      else updateSpectrum();
    });
  });
  exhibit.querySelectorAll<HTMLAnchorElement>('[data-light-choose]').forEach((link) => {
    link.hidden = false;
    link.addEventListener('click', () => show(Number(link.dataset.lightChoose)));
  });
  function syncHash() {
    const step = steps.findIndex((item) => '#' + item.id === location.hash);
    if (step >= 0) show(step);
  }
  window.addEventListener('hashchange', syncHash);
  document.addEventListener('visibilitychange', onScroll);
  motionPreference.addEventListener('change', onScroll);
  show(0);
  syncHash();
  exhibit.querySelector<HTMLElement>('[data-light-nav]')!.hidden = false;
  exhibit.querySelector<HTMLElement>('[data-light-presets]')!.hidden = false;
  updateSpectrum();
  exhibit.dataset.lightReady = 'true';
}
