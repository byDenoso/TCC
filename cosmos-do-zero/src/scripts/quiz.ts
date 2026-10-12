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

  const reviewLink = (chapter: ChapterId, label: string) => {
    const a = document.createElement('a');
    a.className = 'textlink'; a.textContent = label; a.href = chapterUrl(chapter);
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
  const choose = (i: number) => {
    if (state.answered) return;
    state = answer(state, i);
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
    if (!opts.inChapter) feedback.append(reviewLink(q.chapter, 'Revisitar a ideia no capítulo ↗'));
    feedback.hidden = false;
    next.hidden = false;
    next.textContent = state.position === state.pool.length - 1 ? 'Ver meu resultado ↗' : 'Próxima pergunta ↗';
    next.focus({ preventScroll: true });
  };
  const renderResult = () => {
    root.dispatchEvent(new CustomEvent('cosmos:quiz-done', { bubbles: true, detail: { chapter: opts.inChapter ? opts.chapter : '', hits: score(state), total: state.pool.length } }));
    const hits = score(state), total = state.pool.length, wrong = missed(state);
    counter.textContent = 'JORNADA DE PERGUNTAS CONCLUÍDA';
    question.replaceChildren();
    const big = document.createElement('span'); big.className = 'quiz-score'; big.textContent = `${hits}/${total}`;
    const txt = document.createElement('span'); txt.className = 'visually-hidden'; txt.textContent = `Você acertou ${hits} de ${total} perguntas. `;
    const line = document.createElement('span'); line.style.display = 'block'; line.style.marginTop = '12px'; line.textContent = `Você acertou ${hits} de ${total} ${total === 1 ? 'pergunta' : 'perguntas'}.`;
    question.append(big, txt, line);
    answers.replaceChildren();
    if (wrong.length) {
      const ul = document.createElement('ul'); ul.className = 'quiz-review';
      for (const q of wrong) {
        const li = document.createElement('li');
        li.append(`${q.question} `);
        const a = document.createElement('a'); a.href = chapterUrl(q.chapter); a.textContent = 'Rever no capítulo'; li.append(a);
        ul.append(li);
      }
      const h = document.createElement('p'); h.textContent = 'Para uma segunda olhada:'; h.style.margin = '0 0 10px'; h.style.fontWeight = '700';
      answers.append(h, ul);
    }
    const p = document.createElement('p'); p.textContent = verdict(total, hits);
    feedback.replaceChildren(p); feedback.hidden = false;
    next.hidden = false; next.textContent = 'Tentar novamente ↻';
    retry.hidden = wrong.length === 0;
    question.focus();
  };
  next.addEventListener('click', () => {
    const was = state;
    state = advance(state);
    if (state.finished) renderResult(); else if (was.finished) renderQuestion(true); else renderQuestion(true);
  });
  retry.addEventListener('click', () => {
    state = createQuiz(missed(state));
    renderQuestion(true);
  });
  renderQuestion(); // liga os eventos aos botões; o HTML estático já mostra a 1ª pergunta
  return {
    setChapter(c) {
      state = createQuiz(quizPool(c));
      renderQuestion();
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
