import { useState } from 'react';
import { useRouter } from 'next/router';
import { Lead, Meta } from '../../src/components/Frame';
import { AnswerInput } from '../../src/components/Study';
import { levels, type Lesson, grade } from '../../src/lib/school';
import { record } from '../../src/lib/student';
import { curriculum } from '../../src/lib/content';
export function getStaticPaths() {
  return { paths: levels.map((_, i) => ({ params: { id: String(i + 1) } })), fallback: false };
}
export function getStaticProps({ params }: { params: { id: string } }) {
  const id = +params.id;
  return {
    props: {
      id,
      questions: curriculum()
        .filter((c) => c.meta.level === id)
        .map(({ meta: m }) => ({
          slug: m.slug,
          subject: m.subject,
          order: m.order,
          exercise: m.exercise,
          graph: m.graph,
          lab: m.lab,
        })),
    },
  };
}
import { Plot } from '../../src/components/Plot';
type Item = Pick<Lesson, 'slug' | 'subject' | 'order' | 'exercise' | 'graph' | 'lab'>;
function Assessment({
  id,
  questions,
  diagnostic,
}: {
  id: number;
  questions: Item[];
  diagnostic: boolean;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({}),
    [result, setResult] = useState(''),
    [submitted, setSubmitted] = useState(false),
    [busy, setBusy] = useState(false);
  const qs = questions.filter((q) => q.order === (diagnostic ? 1 : 2));
  return (
    <>
      <Meta title={(diagnostic ? 'Diagnóstico' : 'Avaliação') + ' de ' + levels[id - 1].name} />
      <Lead
        tag={'Nível ' + id + ' / ' + levels[id - 1].name}
        title={diagnostic ? 'Diagnóstico do nível' : 'Avaliação do nível'}
        text={
          diagnostic
            ? 'Uma questão por disciplina para identificar por onde começar.'
            : 'Resolva uma aplicação de cada disciplina. A aprovação exige 70% de acertos.'
        }
      />
      <form
        className="wrap reading block"
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy || submitted) return;
          setBusy(true);
          const score = qs.filter((q) => grade(q.exercise, answers[q.slug])).length;
          try {
            const entry = await record({
              kind: 'assessment',
              lesson: (diagnostic ? 'diagnostico-' : 'avaliacao-') + id,
              value: JSON.stringify(answers),
              score,
              total: qs.length,
            });
            setResult(
              (entry.score ?? 0) +
                ' de ' +
                qs.length +
                ' respostas corretas. ' +
                (diagnostic
                  ? 'Consulte abaixo os conceitos para revisar.'
                  : (entry.score ?? 0) / qs.length >= 0.7
                    ? 'Nível aprovado.'
                    : 'Revise os itens indicados e tente novamente.')
            );
            setSubmitted(true);
          } catch (e) {
            setResult((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {qs.map((q, i) => (
          <fieldset className="exam-question" key={q.slug}>
            <legend>
              <small>
                {i + 1} / {qs.length} · {q.subject}
              </small>
              {q.exercise.prompt}
            </legend>
            {q.exercise.kind === 'graph' && <Plot {...q.graph} />}{' '}
            {q.exercise.kind === 'experiment' && (
              <a href={'/laboratorios/' + q.lab + '/'} target="_blank" rel="noreferrer">
                Abrir experimento em outra aba
              </a>
            )}
            <AnswerInput
              question={q.exercise}
              name={q.slug}
              value={answers[q.slug] ?? ''}
              onChange={(v) => {
                if (!submitted) setAnswers({ ...answers, [q.slug]: v });
              }}
            />
            {submitted && (
              <p className="feedback">
                {grade(q.exercise, answers[q.slug]) ? 'Correto. ' : 'Revisão indicada. '}
                {q.exercise.feedback} <a href={'/aulas/' + q.slug + '/'}>Rever a aula</a>
              </p>
            )}
          </fieldset>
        ))}
        {!submitted && (
          <button className="btn dark" disabled={busy || qs.some((q) => !answers[q.slug]?.trim())}>
            {busy ? 'Salvando…' : 'Corrigir avaliação'}
          </button>
        )}
        <p aria-live="polite" className="result">
          {result}
        </p>
        {submitted && (
          <div className="row-actions">
            <a className="btn dark" href="/painel/">
              Ver meu progresso
            </a>
            <button
              type="button"
              className="small-btn"
              onClick={() => {
                setAnswers({});
                setSubmitted(false);
                setResult('');
                window.scrollTo(0, 0);
              }}
            >
              Nova tentativa
            </button>
          </div>
        )}
      </form>
    </>
  );
}
export default function Page({ id, questions }: { id: number; questions: Item[] }) {
  const diagnostic = useRouter().query.modo === 'diagnostico';
  return <Assessment key={String(diagnostic)} {...{ id, questions, diagnostic }} />;
}
