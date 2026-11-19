import { useEffect, useRef, useState } from 'react';
import type { Lesson, Question } from '../lib/school';
import { grade } from '../lib/school';
import { record, useStudent, usePublished } from '../lib/student';
import { summarize } from '../lib/records';
export function AnswerInput({
  question,
  value,
  onChange,
  name,
}: {
  question: Question;
  value: string;
  onChange: (v: string) => void;
  name: string;
}) {
  if (question.kind === 'choice')
    return (
      <div className="choices">
        {question.choices?.map((a, i) => (
          <label key={a}>
            <input
              type="radio"
              name={name}
              checked={value === String(i)}
              onChange={() => onChange(String(i))}
            />
            {a}
          </label>
        ))}
      </div>
    );
  return (
    <label className="answer-label">
      Sua resposta {question.unit && <span>({question.unit})</span>}
      <input
        className="field"
        type="text"
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        placeholder="Digite um valor"
      />
    </label>
  );
}
export function Exercise({ lesson }: { lesson: Lesson }) {
  const [value, setValue] = useState(''),
    [feedback, setFeedback] = useState(''),
    [busy, setBusy] = useState(false),
    [correct, setCorrect] = useState(false);
  const q = lesson.exercise;
  return (
    <section id="exercicio" className="exercise">
      <p className="kicker">Verifique sua compreensão</p>
      <h2>Exercício</h2>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!value.trim() || busy) return;
          setBusy(true);
          try {
            const ok = grade(q, value);
            const result = await record({ kind: 'attempt', lesson: lesson.slug, value, correct: ok });
            setCorrect(!!result.correct);
            setFeedback((result.correct ? 'Resposta correta. ' : 'Revise o cálculo. ') + q.feedback);
          } catch (err) {
            setCorrect(false);
            setFeedback((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset>
          <legend>{q.prompt}</legend>
          <AnswerInput
            name={lesson.slug}
            question={q}
            value={value}
            onChange={(v) => {
              setValue(v);
              setFeedback('');
            }}
          />
        </fieldset>
        <button className="btn dark" disabled={!value.trim() || busy}>
          {busy ? 'Registrando…' : 'Verificar resposta'}
        </button>
      </form>
      {feedback && (
        <p className={'feedback ' + (correct ? 'ok' : '')} role="status">
          {feedback}
        </p>
      )}
    </section>
  );
}
export function StudyTools({ slug }: { slug: string }) {
  const student = useStudent(),
    stats = summarize(student.entries),
    logged = useRef(''),
    [note, setNote] = useState(''),
    [msg, setMsg] = useState('');
  useEffect(() => {
    if (!student.loaded) return;
    const key = slug + ';' + (student.account?.name ?? 'guest');
    if (logged.current === key) return;
    logged.current = key;
    record({ kind: 'open', lesson: slug, value: '' }).catch((e) => setMsg(e.message));
  }, [slug, student.loaded, student.account?.name]);
  const saved = stats.notes[slug] ?? '';
  useEffect(() => {
    setNote(saved);
  }, [slug, saved]);
  return (
    <div className="study-tools">
      <button
        className="small-btn"
        aria-pressed={stats.favorites.has(slug)}
        onClick={async () => {
          try {
            await record({
              kind: 'favorite',
              lesson: slug,
              value: stats.favorites.has(slug) ? 'no' : 'yes',
            });
          } catch (e) {
            setMsg((e as Error).message);
          }
        }}
      >
        {stats.favorites.has(slug) ? '★ Favorito' : '☆ Favoritar'}
      </button>
      <details>
        <summary>Minhas anotações</summary>
        <label>
          Anotação sobre a aula
          <textarea maxLength={2400} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <button
          className="small-btn"
          onClick={async () => {
            try {
              await record({ kind: 'note', lesson: slug, value: note });
              setMsg('Anotação salva.');
            } catch (e) {
              setMsg((e as Error).message);
            }
          }}
        >
          Salvar anotação
        </button>
      </details>
      <span role="status">{msg || student.sync}</span>
    </div>
  );
}
export function PublishedNote({ slug }: { slug: string }) {
  const items = usePublished().filter((i) => i.key === slug);
  return (
    <>
      {items.map((i) => (
        <aside className="method" key={i.key}>
          <p className="kicker">Revisão científica · versão {i.version}</p>
          <h3>{i.payload.title}</h3>
          <p>{i.payload.body}</p>
          <a href={'/leitura/?id=' + encodeURIComponent(i.key)}>Abrir edição publicada</a>
        </aside>
      ))}
    </>
  );
}
