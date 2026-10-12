import { $, $$ } from './dom';
import { questions } from '../data/client';
import { advance, answer, createQuiz, missed, poolFor, score, verdict, type QuizState } from '../lib/quiz';
import { chapterUrl } from '../lib/url';
import { getParam, setParams } from '../lib/url-state';
import { pad2 } from '../lib/format';
import { PRIMARY_CHAPTER_IDS, type ChapterId } from '../types';
const quizPool = (chapter: ChapterId | '') => poolFor(chapter ? questions : questions.filter(q => (PRIMARY_CHAPTER_IDS as readonly ChapterId[]).includes(q.chapter)), chapter);

function mount(root: HTMLElement, opts: { chapter: ChapterId | ''; inChapter: boolean }): { setChapter(c: ChapterId | ''): void } {
  const counter = $('[data-quiz-counter]', root)!;
  const question = $('[data-quiz-question]', root)!;
  const answers = $('[data-quiz-answers]', root)!;
  const feedback = $('[data-quiz-feedback]', root)!;
  const next = $<HTMLButtonElement>('[data-quiz-next]', root)!;
  const retry = $<HTMLButtonElement>('[data-quiz-retry-missed]', root)!;
  let state: QuizState = createQuiz(quizPool(opts.chapter));
  let chapterNow = opts.chapter;
  // A tentativa sobrevive a ir rever um trecho e voltar.
  const key = () => `cosmos-quiz:${location.pathname}:${chapterNow}`;
  const save = () => { try { sessionStorage.setItem(key(), JSON.stringify({ ids: state.pool.map((q) => q.id), position: state.position, answered: state.answered, choice: state.choice, history: state.history, finished: state.finished })); } catch { /* sem armazenamento */ } };
  const restore = (): boolean => {
    try {
      const raw = sessionStorage.getItem(key()); if (!raw) return false;
      const s = JSON.parse(raw) as { ids: string[]; position: number; answered: boolean; choice: number | null; history: QuizState['history']; finished: boolean };
      if (!s || !Array.isArray(s.ids) || !Array.isArray(s.history) || !Number.isInteger(s.position) || s.position < 0 ||
          typeof s.answered !== 'boolean' || typeof s.finished !== 'boolean') return false;
      const pool = s.ids.map((id) => questions.find((q) => q.id === id)).filter((q): q is (typeof questions)[number] => !!q);
      if (pool.length !== s.ids.length || !pool.length || s.position >= pool.length || new Set(s.ids).size !== s.ids.length ||
          !pool.every((q) => quizPool(chapterNow).some((allowed) => allowed.id === q.id)) || (!s.history.length && !s.finished)) return false;
      if (s.answered && (!Number.isInteger(s.choice) || s.choice === null || s.choice < 0 || s.choice >= pool[s.position].answers.length)) return false;
      if (s.history.some((h) => !h || !pool.some((q) => q.id === h.id && Number.isInteger(h.choice) && h.choice >= 0 && h.choice < q.answers.length && h.correct === (h.choice === q.correct)))) return false;
      state = { pool, position: Math.min(s.position, pool.length - 1), answered: false, choice: null, history: s.answered ? s.history.slice(0, -1) : s.history, finished: false };
      if (s.finished) { state = { ...state, history: s.history, answered: true, finished: true }; renderResult(false); return true; }
      renderQuestion();
      if (s.answered && s.choice !== null) choose(s.choice, false);
      return true;
    } catch { return false; }
  };

  const reviewHref = (q: { chapter: ChapterId; section?: string }) => (opts.inChapter ? '' : chapterUrl(q.chapter)) + (q.section ? `#${q.section}` : '');
  const reviewLink = (q: { chapter: ChapterId; section?: string }, label: string) => {
    const a = document.createElement('a');
    a.className = 'textlink quiz-review-link'; a.textContent = label; a.href = reviewHref(q) || chapterUrl(q.chapter);
    return a;
  };
  const renderQuestion = (focus = false) => {
    const q = state.pool[state.position];
    feedback.hidden = true; next.hidden = true; retry.hidden = true; feedback.replaceChildren();
    counter.textContent = `PERGUNTA ${pad2(state.position + 1)} / ${pad2(state.pool.length)}`;
    question.textContent = q.question;
    answers.replaceChildren(...q.answers.map((text, i) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'quiz-answer'; b.dataset.answer = String(i);
      const letter = document.createElement('span'); letter.className = 'letter'; letter.setAttribute('aria-hidden', 'true'); letter.textContent = String.fromCharCode(65 + i);
      const label = document.createElement('span'); label.textContent = text;
      b.append(letter, label);
      b.addEventListener('click', () => choose(i));
      return b;
    }));
    if (focus) question.focus();
  };
  const choose = (i: number, focusNext = true) => {
    if (state.answered) return;
    state = answer(state, i);
    save();
    const q = state.pool[state.position];
    const correct = i === q.correct;
    $$<HTMLButtonElement>('button', answers).forEach((node, j) => {
      node.disabled = true;
      node.classList.toggle('correct', j === q.correct);
      node.classList.toggle('wrong', j === i && !correct);
      if (j === q.correct) node.setAttribute('aria-label', `${node.textContent?.slice(1)}. Resposta correta`);
      if (j === i && !correct) node.setAttribute('aria-label', `${node.textContent?.slice(1)}. Sua resposta, incorreta`);
    });
    const p = document.createElement('p');
    const v = document.createElement('span'); v.className = 'verdict'; v.textContent = correct ? 'Você acertou. ' : 'A resposta correta está indicada. ';
    p.append(v, q.explanation);
    feedback.replaceChildren(p);
    if (!opts.inChapter) feedback.append(reviewLink(q, correct ? 'Ver o trecho que explica isso ↗' : 'Ir direto ao trecho que explica isso ↗'));
    else if (!correct && q.section) feedback.append(reviewLink(q, 'Rever o trecho que explica isso ↑'));
    feedback.hidden = false;
    next.hidden = false;
    next.textContent = state.position === state.pool.length - 1 ? 'Ver meu resultado ↗' : 'Próxima pergunta ↗';
    if (focusNext) next.focus({ preventScroll: true });
  };
  const renderResult = (fresh = true) => {
    save();
    if (fresh) root.dispatchEvent(new CustomEvent('cosmos:quiz-done', { bubbles: true, detail: { chapter: opts.inChapter ? opts.chapter : '', hits: score(state), total: state.pool.length } }));
    const hits = score(state), total = state.pool.length, wrong = missed(state);
    counter.textContent = 'JORNADA DE PERGUNTAS CONCLUÍDA';
    question.replaceChildren();
    const big = document.createElement('span'); big.className = 'quiz-score'; big.textContent = `${hits}/${total}`; big.setAttribute('aria-hidden', 'true');
    const line = document.createElement('span'); line.style.display = 'block'; line.style.marginTop = '12px'; line.textContent = `Você acertou ${hits} de ${total} ${total === 1 ? 'pergunta' : 'perguntas'}.`;
    question.append(big, line);
    answers.replaceChildren();
    if (wrong.length) {
      const ul = document.createElement('ul'); ul.className = 'quiz-review';
      for (const q of wrong) {
        const li = document.createElement('li');
        li.append(`${q.question} `);
        const a = reviewLink(q, opts.inChapter ? 'Rever o trecho' : 'Ir ao trecho que explica'); li.append(a);
        ul.append(li);
      }
      const h = document.createElement('p'); h.textContent = 'Para uma segunda olhada:'; h.style.margin = '0 0 10px'; h.style.fontWeight = '700';
      answers.append(h, ul);
    }
    const p = document.createElement('p'); p.textContent = verdict(total, hits);
    const activity = document.createElement('p');
    activity.dataset.quizActivity = '';
    activity.textContent = opts.inChapter
      ? 'Aula concluída! Seu progresso registra a participação. Use a pontuação e os trechos de revisão para escolher o que praticar de novo.'
      : 'Você concluiu esta tentativa. A pontuação e os trechos de revisão ajudam a escolher o que praticar de novo.';
    feedback.replaceChildren(p, activity); feedback.hidden = false;
    next.hidden = false; next.textContent = 'Tentar novamente ↻';
    retry.hidden = wrong.length === 0;
    if (fresh) question.focus();
  };
  next.addEventListener('click', () => {
    const was = state;
    state = advance(state);
    if (state.finished) renderResult(); else { save(); renderQuestion(true); }
    void was;
  });
  retry.addEventListener('click', () => {
    state = createQuiz(missed(state));
    save();
    renderQuestion(true);
  });
  if (!restore()) renderQuestion(); // liga os eventos aos botões; o HTML estático já mostra a 1ª pergunta
  return {
    setChapter(c) {
      chapterNow = c;
      state = createQuiz(quizPool(c));
      if (!restore()) renderQuestion();
    }
  };
}

export function initQuizzes(): void {
  const cards = $$<HTMLElement>('[data-quiz]');
  cards.forEach((root) => {
    const inChapter = !!root.closest('.reader-page');
    const chapter = (root.dataset.chapterFilter ?? '') as ChapterId | '';
    const api = mount(root, { chapter, inChapter });
    const select = $<HTMLSelectElement>('[data-quiz-filter]');
    if (select && !inChapter) {
      const fromUrl = getParam('assunto');
      if (fromUrl && [...select.options].some((o) => o.value === fromUrl)) { select.value = fromUrl; api.setChapter(fromUrl as ChapterId); }
      select.addEventListener('change', () => { api.setChapter(select.value as ChapterId | ''); setParams({ assunto: select.value || null }); });
    }
  });
}
