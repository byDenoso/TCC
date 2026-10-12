/** Desenho da evolução estelar por massa e etapa. Usado no laboratório estelar. */
import { orbColor, orbDiameter, rgb, stellarPath } from '../../lib/stars';
import { C, clear, ease, el, g, lerp, rng, star, text } from './draw';

/** Rótulo de confiança de cada etapa: típico (observado em muitas estrelas), previsto (ainda não visto) ou pode (um entre vários caminhos). */
export function stageTag(m: number, step: number): 'típico' | 'previsto' | 'pode' {
  if (m < 0.6 && step >= 3) return 'previsto';
  if (m >= 8 && step >= 3) return 'pode';
  return 'típico';
}

export function drawStellar(layer: SVGGElement, m: number, step: number, t = 1): string {
  clear(layer);
  const path = stellarPath(m), k = ease(t);
  const cx = 150, cy = 125;
  const col = rgb(orbColor(m)), r0 = orbDiameter(m) / 2.6;
  const tag = stageTag(m, step);
  const dashed = tag === 'previsto';
  const rnd = rng(3);
  if (step === 0) {
    for (let i = 0; i < 16; i++) el('circle', { cx: cx + (rnd() - 0.5) * 180, cy: cy + (rnd() - 0.5) * 110, r: 22 + rnd() * 26, fill: C.ink2, opacity: 0.06 + 0.04 * k }, layer);
  } else if (step === 1) {
    el('ellipse', { cx, cy, rx: lerp(110, 80, k), ry: 12, fill: C.accent, opacity: 0.18 }, layer);
    star(layer, cx, cy, lerp(26, 18, k), '#c8553a');
  } else if (step === 2) {
    star(layer, cx, cy, r0, col);
  } else if (step === 3) {
    if (m < 0.6) { star(layer, cx, cy, r0, col); el('circle', { cx, cy, r: r0 * 1.6, fill: 'none', stroke: C.muted, 'stroke-dasharray': '5 5' }, layer); }
    else if (m < 8) star(layer, cx, cy, lerp(r0, 95, k), '#e0603a');
    else {
      star(layer, cx, cy, lerp(r0 * 1.4, 22, k), lerp(0, 1, k) > 0.5 ? '#ffd9a0' : col);
      for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; el('line', { x1: cx + Math.cos(a) * 26, y1: cy + Math.sin(a) * 26, x2: cx + Math.cos(a) * (26 + 70 * k), y2: cy + Math.sin(a) * (26 + 70 * k), stroke: C.gold, 'stroke-width': 2, 'stroke-dasharray': '4 4', opacity: 0.8 }, layer); }
    }
  } else {
    if (m < 0.6) { el('circle', { cx, cy, r: 9, fill: 'none', stroke: C.ink, 'stroke-width': 2, 'stroke-dasharray': '3 3' }, layer); }
    else if (m < 8) { el('circle', { cx, cy, r: lerp(40, 90, k), fill: 'none', stroke: '#5fb3a8', 'stroke-width': 10, opacity: 0.35 * (1 - k * 0.5) }, layer); star(layer, cx, cy, 6, '#f4f6ff'); }
    else {
      star(layer, cx - 55, cy, 6, '#cfe0ff');
      text(layer, cx - 55, cy + 40, 'estrela de nêutrons', { class: 'mx-t small', 'text-anchor': 'middle' });
      text(layer, cx, cy + 5, 'ou', { class: 'mx-t small strong', 'text-anchor': 'middle' });
      el('circle', { cx: cx + 55, cy, r: 16, fill: '#000' }, layer);
      el('circle', { cx: cx + 55, cy, r: 22, fill: 'none', stroke: C.gold, 'stroke-width': 2, opacity: 0.7 }, layer);
      text(layer, cx + 55, cy + 40, 'buraco negro', { class: 'mx-t small', 'text-anchor': 'middle' });
    }
  }
  if (dashed) text(layer, cx, 238, 'previsto por modelos', { class: 'mx-t small warm', 'text-anchor': 'middle' });
  // trilha de etapas
  const ox = 310;
  path.steps.forEach((s, i) => {
    const y = 30 + i * 46, on = i === step, past = i < step;
    el('circle', { cx: ox, cy: y, r: on ? 9 : 6, fill: on ? C.accent : past ? C.ink2 : C.surface, stroke: on || past ? 'none' : C.line, 'stroke-width': 1.5 }, layer);
    if (i < path.steps.length - 1) el('line', { x1: ox, y1: y + 10, x2: ox, y2: y + 36, stroke: past ? C.ink2 : C.line, 'stroke-width': 2, 'stroke-dasharray': stageTag(m, i + 1) === 'típico' ? '' : '4 4' }, layer);
    text(layer, ox + 16, y + 5, s.length > 22 ? `${s.slice(0, 21)}…` : s, { class: `mx-t small${on ? ' strong warm' : ''}` });
  });
  const name = path.steps[step];
  const tagText = tag === 'previsto' ? 'Previsto por modelos: o Universo ainda é jovem demais para termos visto isso.' : tag === 'pode' ? 'Um dos caminhos possíveis: massa, rotação, composição e companheiras mudam o resultado.' : 'Etapa típica, observada em muitas estrelas.';
  return `${name}. ${tagText}`;
}

export function initStellarSvg(svg: SVGSVGElement): SVGGElement {
  clear(svg);
  return g(svg);
}
