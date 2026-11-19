import { useEffect, useState } from 'react';
import { Lead, Meta } from '../src/components/Frame';
import { api, CLASSROOM, isPages, useStudent, type Editorial } from '../src/lib/student';
import { levels } from '../src/lib/school';
import { labs } from '../src/lib/model';
import { curriculum } from '../src/lib/content';
type Payload = Editorial['payload'];
const blank: Payload = {
  type: 'Aula',
  title: '',
  body: '',
  level: 1,
  subject: '',
  lab: '',
  reference: '',
  question: '',
  answer: '',
  unit: '',
  tolerance: 0,
};
export function getStaticProps() {
  return {
    props: {
      base: curriculum().map(({ meta: m }) => ({
        key: m.slug,
        payload: {
          type: 'Aula',
          title: m.title,
          body: m.summary,
          level: m.level,
          subject: m.subject,
          lab: m.lab,
          reference: m.reference.url,
          question: m.exercise.prompt,
          options: m.exercise.choices ?? [],
          answer: String(m.exercise.answer),
          unit: m.exercise.unit,
          tolerance: m.exercise.tolerance,
        },
      })),
    },
  };
}
export default function Admin({ base }: { base: { key: string; payload: Payload }[] }) {
  const user = useStudent(),
    [key, setKey] = useState(''),
    [data, setData] = useState(blank),
    [revs, setRevs] = useState<Editorial[]>([]),
    [counts, setCounts] = useState({ students: 0, attempts: 0, correct: 0 }),
    [progress, setProgress] = useState<{ lesson: string; students: number }[]>([]),
    [msg, setMsg] = useState(''),
    [version, setVersion] = useState(0),
    [busy, setBusy] = useState(false);
  const field = <K extends keyof Payload>(k: K, v: Payload[K]) => setData((old) => ({ ...old, [k]: v }));
  async function reload() {
    const r = await api('admin');
    setRevs(r.revisions);
    setCounts(r.counts);
    setProgress(r.progress);
  }
  useEffect(() => {
    if (user.account?.role === 'editor') reload().catch((e) => setMsg(e.message));
  }, [user.account?.role]);
  function choose(k: string) {
    setKey(k);
    const last = revs.find((r) => r.key === k);
    setData(last?.payload ?? base.find((x) => x.key === k)?.payload ?? blank);
    setVersion(last?.version ?? 0);
    setMsg('');
  }
  async function save(status: string) {
    setBusy(true);
    try {
      const r = await api('revision', { key, expected: version, payload: data, status });
      setVersion(r.version);
      await reload();
      setMsg('Versão ' + r.version + ' salva · ' + status + '.');
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Meta title="Gestão editorial" />
      <Lead
        tag="Escola Cosmos"
        title="Gestão editorial"
        text="Revisões científicas, publicações didáticas e progresso agregado."
      />
      <div className="wrap block editor-grid">
        {user.account?.role !== 'editor' ? (
          <p>
            O acesso exige uma conta editorial.{' '}
            <a href={isPages() ? CLASSROOM + '/gestao/' : '/painel/'}>
              {isPages() ? 'Abrir ambiente editorial' : 'Entrar na conta'}
            </a>
          </p>
        ) : (
          <>
            <div className="method">
              <h2>Progresso agregado</h2>
              <p>
                {counts.students} contas · {counts.attempts} tentativas · {counts.correct} acertos
              </p>
              <details>
                <summary>Conclusões por aula</summary>
                {progress.map((p) => (
                  <p key={p.lesson}>
                    {p.lesson} · {p.students} estudantes
                  </p>
                ))}
              </details>
            </div>
            <h2>Conteúdo e revisão</h2>
            <label>
              Selecionar material
              <select
                className="field"
                onChange={(e) => choose(e.target.value)}
                value={base.some((x) => x.key === key) || revs.some((x) => x.key === key) ? key : ''}
              >
                <option value="">Novo material</option>
                {[...new Map([...revs, ...base].map((x) => [x.key, x])).values()].map((x) => (
                  <option value={x.key} key={x.key}>
                    {x.payload.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Identificador público
              <input
                className="field"
                value={key}
                maxLength={95}
                onChange={(e) => {
                  setKey(e.target.value);
                  setVersion(0);
                }}
                placeholder="ex.: gravitacao-em-duas-escalas"
              />
            </label>
            <div className="editor-row">
              <label>
                Tipo de conteúdo
                <select
                  className="field"
                  value={data.type}
                  onChange={(e) => field('type', e.target.value)}
                >
                  {['Disciplina', 'Módulo', 'Aula', 'Exercício', 'Experimento', 'Referência'].map(
                    (x) => (
                      <option key={x}>{x}</option>
                    )
                  )}
                </select>
              </label>
              <label>
                Nível
                <select
                  className="field"
                  value={data.level}
                  onChange={(e) => field('level', +e.target.value)}
                >
                  {levels.map((x, i) => (
                    <option key={x.name} value={i + 1}>
                      {x.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Título
              <input
                className="field"
                value={data.title}
                onChange={(e) => field('title', e.target.value)}
              />
            </label>
            <label>
              Disciplina ou módulo
              <input
                className="field"
                list="disciplinas"
                value={data.subject}
                onChange={(e) => field('subject', e.target.value)}
              />
              <datalist id="disciplinas">
                {levels[data.level - 1].subjects.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </datalist>
            </label>
            <label>
              Texto didático ou revisão científica
              <textarea
                className="field"
                value={data.body}
                onChange={(e) => field('body', e.target.value)}
              />
            </label>
            <label>
              Experimento associado
              <select className="field" value={data.lab} onChange={(e) => field('lab', e.target.value)}>
                <option value="">Sem associação</option>
                {labs.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Referência bibliográfica (URL HTTPS)
              <input
                className="field"
                type="url"
                value={data.reference}
                onChange={(e) => field('reference', e.target.value)}
              />
            </label>
            <label>
              Enunciado da questão
              <textarea
                className="field"
                value={data.question}
                onChange={(e) => field('question', e.target.value)}
              />
            </label>
            <label>
              Formato da resposta
              <select
                className="field"
                value={data.options?.length ? 'choice' : 'numeric'}
                onChange={(e) =>
                  setData({
                    ...data,
                    options: e.target.value === 'choice' ? ['', ''] : [],
                    answer: '0',
                    tolerance: 0,
                  })
                }
              >
                <option value="numeric">Numérica</option>
                <option value="choice">Múltipla escolha</option>
              </select>
            </label>
            {!!data.options?.length && (
              <label>
                Alternativas (uma por linha)
                <textarea
                  className="field"
                  value={data.options.join('\n')}
                  onChange={(e) => field('options', e.target.value.split('\n'))}
                />
              </label>
            )}
            <div className="editor-row">
              <label>
                Gabarito
                {data.options?.length ? (
                  <select
                    className="field"
                    value={data.answer}
                    onChange={(e) => field('answer', e.target.value)}
                  >
                    {data.options.map((o, i) => (
                      <option key={i} value={i}>
                        {i + 1}. {o}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="field"
                    value={data.answer}
                    onChange={(e) => field('answer', e.target.value)}
                  />
                )}
              </label>
              <label>
                Tolerância absoluta
                <input
                  type="number"
                  min="0"
                  step="any"
                  className="field"
                  value={data.tolerance}
                  onChange={(e) => field('tolerance', +e.target.value)}
                />
              </label>
            </div>
            <label>
              Unidade
              <input
                className="field"
                value={data.unit}
                onChange={(e) => field('unit', e.target.value)}
              />
            </label>
            <div className="row-actions">
              {[
                ['rascunho', 'Salvar rascunho'],
                ['revisao', 'Enviar para revisão'],
                ['publicado', 'Publicar revisão'],
              ].map(([s, l]) => (
                <button className="small-btn" disabled={busy} key={s} onClick={() => save(s)}>
                  {l}
                </button>
              ))}
            </div>
            <p role="status">{msg}</p>
            <h2>Histórico de versões</h2>
            {revs
              .filter((r) => r.key === key)
              .map((r) => (
                <details key={r.version} className="review-item">
                  <summary>
                    Versão {r.version} · {r.status}
                  </summary>
                  <h3>{r.payload.title}</h3>
                  <p>{r.payload.body}</p>
                  <p>{r.payload.reference}</p>
                </details>
              ))}
          </>
        )}
      </div>
    </>
  );
}
