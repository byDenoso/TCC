import { $, $$, setText } from './dom';
import { createLocalStore, mainCompletedCount, nextUnfinished, progressLabel } from '../lib/progress';
import { PRIMARY_CHAPTER_IDS, type ChapterId } from '../types';
import { chapterUrl } from '../lib/url';
import { readPlace } from './reader';

export const store = createLocalStore();

function progressStatus(): HTMLElement | null {
  const existing = $('[data-progress-status]');
  if (existing) return existing;
  const resetButton = $<HTMLButtonElement>('[data-reset-progress]');
  if (!resetButton) return null;
  const status = document.createElement('span');
  status.dataset.progressStatus = '';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  resetButton.insertAdjacentElement('afterend', status);
  return status;
}

export function refreshProgress(): void {
  const done = store.read();
  document.dispatchEvent(new CustomEvent('cosmos:progress', { detail: { done } }));
  const mainCount = mainCompletedCount(done);
  $$<HTMLProgressElement>('[data-progress-bar]').forEach((b) => (b.value = mainCount));
  $$('[data-progress-label]').forEach((n) => setText(n, progressLabel(mainCount)));
  $$('[data-journey]').forEach((row) => { const m = $('.completion-mark', row); if (m) m.hidden = !done.includes(row.dataset.journey as ChapterId); });
  $$('[data-reset-progress]').forEach((b) => (b.hidden = done.length === 0));
  $$<HTMLButtonElement>('[data-complete]').forEach((b) => {
    const isDone = done.includes(b.dataset.complete as ChapterId);
    b.dataset.done = String(isDone);
    const label = $('[data-complete-label]', b);
    if (label) setText(label, isDone ? 'Capítulo concluído' : 'Concluir este capítulo');
    b.setAttribute('aria-pressed', String(isDone));
  });
  // Abertura: continuar de onde parou (o último passo visitado de uma aula não concluída)
  const place = readPlace();
  const resumeAt = place && !done.includes(place.chapter as ChapterId) && place.step > 0 ? place : null;
  for (const card of $$<HTMLAnchorElement>('[data-resume]')) {
    card.hidden = !resumeAt;
    if (!resumeAt) continue;
    let titles: Record<string, string> = {};
    try { titles = JSON.parse(card.dataset.titles ?? '{}'); } catch { /* ignora */ }
    card.href = `${chapterUrl(resumeAt.chapter)}#${resumeAt.section}`;
    setText($('[data-resume-title]', card), titles[resumeAt.chapter] ?? 'Sua aula');
    setText($('[data-resume-step]', card), `Passo ${resumeAt.step + 1} de ${resumeAt.total}: ${resumeAt.title}`);
  }
  for (const cta of $$<HTMLAnchorElement>('[data-start-journey]')) {
    const next = nextUnfinished(done);
    const completed = mainCount === PRIMARY_CHAPTER_IDS.length;
    cta.href = resumeAt ? `${chapterUrl(resumeAt.chapter)}#${resumeAt.section}` : chapterUrl(next ?? PRIMARY_CHAPTER_IDS[0]);
    const inHeader = !!cta.closest('.header');
    setText($('[data-start-label]', cta), completed ? (inHeader ? 'Revisar aulas' : 'Revisar a jornada principal') : mainCount > 0 || resumeAt ? (inHeader ? 'Continuar a aula' : 'Continuar a jornada') : (inHeader ? 'Começar a aula' : 'Começar a jornada'));
  }
}

export function initProgress(): void {
  refreshProgress();
  document.addEventListener('click', (e) => {
    const t = e.target as Element;
    const complete = t.closest<HTMLButtonElement>('[data-complete]');
    if (complete) {
      const id = complete.dataset.complete as ChapterId;
      const ids = store.read();
      const was = ids.includes(id);
      const next = was ? ids.filter((x) => x !== id) : [...ids, id];
      const saved = store.write(next);
      refreshProgress();
      const status = $('[data-complete-status]', complete.parentElement ?? document);
      if (status) setText(status, saved
        ? was ? 'Capítulo desmarcado. Progresso salvo neste navegador.' : 'Progresso salvo neste navegador. Continue para a próxima jornada.'
        : was ? 'Capítulo desmarcado nesta sessão. O armazenamento deste navegador está indisponível.' : 'Capítulo concluído nesta sessão. O armazenamento deste navegador está indisponível.');
    }
    if (t.closest('[data-reset-progress]')) {
      const saved = store.write([]);
      refreshProgress();
      setText(progressStatus(), saved ? 'Progresso reiniciado neste navegador.' : 'Progresso reiniciado nesta sessão. O armazenamento deste navegador está indisponível.');
    }
  });
  window.addEventListener('storage', refreshProgress);
  // Terminar o desafio da aula conclui a aula automaticamente
  document.addEventListener('cosmos:quiz-done', (e) => {
    const id = (e as CustomEvent<{ chapter: ChapterId | '' }>).detail.chapter;
    if (!id) return;
    const ids = store.read();
    if (!ids.includes(id)) { store.write([...ids, id]); refreshProgress(); }
  });
}
