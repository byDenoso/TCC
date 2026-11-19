import { useState } from 'react';
import { simulate, type Lab } from '../lib/model';
import { compact } from '../lib/school';
import { record } from '../lib/student';
export default function LabChallenge({
  lab,
  values,
  onMeasure,
}: {
  lab: Lab;
  values: number[];
  onMeasure: () => void;
}) {
  const [answer, setAnswer] = useState(''),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false);
  const target =
    lab.presets.find((p) => p.values.some((v, i) => v !== lab.parameters[i].initial)) ?? lab.presets[1];
  const meter = simulate(lab.id, target.values, 0).metric;
  return (
    <section className="challenge">
      <p className="kicker">Experimento avaliativo</p>
      <h3>Reproduza uma medida</h3>
      <p>
        Configure{' '}
        {lab.parameters
          .map((p, i) => p.label.toLowerCase() + ' = ' + compact(target.values[i]) + ' ' + p.unit)
          .join(' e ')}
        . Faça a leitura na posição inicial do relógio. A correção aceita 1% de diferença no valor.
      </p>
      <div className="row-actions">
        <button
          className="small-btn"
          onClick={() => {
            onMeasure();
            setMessage('Relógio em t = 0. Leia o resultado da bancada.');
          }}
        >
          Medir em t = 0
        </button>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy) return;
          setBusy(true);
          const s = answer.trim().replace(',', '.'),
            n = Number(s);
          const ok =
            values.every((v, i) => Math.abs(v - target.values[i]) < 1e-6) &&
            s !== '' &&
            Number.isFinite(n) &&
            Math.abs(n - meter.value) <= Math.max(Math.abs(meter.value) * 0.01, 1e-12);
          try {
            const logged = await record({
              kind: 'lab',
              lesson: lab.id,
              value: JSON.stringify({ values, answer: s }),
              correct: ok,
            });
            setMessage(
              logged.correct
                ? 'Medida reproduzida. Experimento registrado.'
                : 'Confira os dois parâmetros, a unidade e a leitura em t = 0.'
            );
          } catch (e) {
            setMessage((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label className="answer-label">
          {meter.label} ({meter.unit})
          <input
            className="field"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            inputMode="decimal"
            required
          />
        </label>
        <button className="btn dark" disabled={!answer.trim() || busy}>
          Registrar medida
        </button>
      </form>
      <p role="status">{message}</p>
    </section>
  );
}
