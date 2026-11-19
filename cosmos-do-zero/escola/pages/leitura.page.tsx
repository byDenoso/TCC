import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { Meta, Lead } from '../src/components/Frame';
import { usePublished, record } from '../src/lib/student';
export default function Reader() {
  const key = useRouter().query.id,
    items = usePublished(),
    item = items.find((i) => i.key === key),
    [value, set] = useState(''),
    [msg, setMsg] = useState('');
  useEffect(() => {
    set('');
    setMsg('');
  }, [key]);
  if (!item)
    return (
      <>
        <Meta title="Material editorial" />
        <Lead tag="Acervo" title="Material editorial" />
        <div className="wrap block">
          <p>
            Consulte as edições publicadas no <a href="/trilhas/">catálogo de aulas</a>.
          </p>
        </div>
      </>
    );
  const p = item.payload;
  return (
    <>
      <Meta title={p.title} />
      <Lead tag={p.type + ' / Revisão ' + item.version} title={p.title} text={p.subject} />
      <article className="wrap reading block prose">
        <p style={{ whiteSpace: 'pre-line' }}>{p.body}</p>
        {p.lab && (
          <p>
            <a href={'/laboratorios/' + p.lab + '/'}>Abrir o experimento associado</a>
          </p>
        )}
        {p.question && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const num = Number(value.trim().replace(',', '.'));
              try {
                const a = await record({
                  kind: 'attempt',
                  lesson: 'edicao-' + item.key,
                  value,
                  correct:
                    value.trim() !== '' &&
                    Number.isFinite(num) &&
                    Math.abs(num - Number(p.answer)) <= p.tolerance,
                });
                setMsg(a.correct ? 'Resposta correta.' : 'Revise a relação física e tente novamente.');
              } catch (e) {
                setMsg((e as Error).message);
              }
            }}
          >
            {p.options?.length ? (
              <fieldset className="choices">
                <legend>{p.question}</legend>
                {p.options.map((o, i) => (
                  <label key={i}>
                    <input
                      type="radio"
                      name="resposta-editorial"
                      required
                      checked={value === String(i)}
                      onChange={() => set(String(i))}
                    />
                    {o}
                  </label>
                ))}
              </fieldset>
            ) : (
              <label>
                {p.question} {p.unit && '(' + p.unit + ')'}
                <input
                  className="field"
                  required
                  value={value}
                  onChange={(e) => set(e.target.value)}
                  inputMode="decimal"
                />
              </label>
            )}
            <button className="btn dark">Verificar resposta</button>
            <p role="status">{msg}</p>
          </form>
        )}
        {p.reference && (
          <p>
            <a href={p.reference}>Fonte da edição</a>
          </p>
        )}
      </article>
    </>
  );
}
