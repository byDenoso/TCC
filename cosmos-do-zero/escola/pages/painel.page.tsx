import { useEffect, useMemo, useState } from 'react';
import { Meta, Lead } from '../src/components/Frame';
import { cards } from '../src/lib/content';
import { levels, type Card } from '../src/lib/school';
import {
  api,
  CLASSROOM,
  guestCount,
  importGuest,
  isPages,
  loadStudent,
  useStudent,
} from '../src/lib/student';
import { chapters } from '../src/lib/legacy';
import { summarize } from '../src/lib/records';
export function getStaticProps() {
  return { props: { all: cards() } };
}
function Account() {
  const s = useStudent(),
    [register, setReg] = useState(false),
    [msg, setMsg] = useState(''),
    [busy, setBusy] = useState(false),
    [pages, setPages] = useState(false),
    [ready, setReady] = useState<boolean | null>(null);
  useEffect(() => {
    const remote = isPages();
    setPages(remote);
    if (!remote)
      api('session')
        .then((d) => setReady(!!d.available))
        .catch(() => setReady(false));
  }, []);
  if (s.account)
    return (
      <section className="account-box">
        <h2>Conta de {s.account.name}</h2>
        <p>O histórico desta sessão está vinculado à sua conta.</p>
        <div className="row-actions">
          {guestCount() > 0 && (
            <button
              className="small-btn"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await importGuest();
                  setMsg('Histórico deste navegador importado.');
                } catch (e) {
                  setMsg((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Importar estudo de visitante
            </button>
          )}
          <button
            className="small-btn"
            onClick={async () => {
              try {
                await api('logout', {});
                await loadStudent();
              } catch (e) {
                setMsg((e as Error).message);
              }
            }}
          >
            Sair da conta
          </button>
          {s.account.role === 'editor' && <a href="/gestao/">Gestão editorial</a>}
        </div>
        <p role="status">{msg}</p>
      </section>
    );
  return (
    <section className="account-box">
      <h2>Conta do estudante</h2>
      <p>Como visitante, seu estudo fica salvo neste navegador.</p>
      {pages ? (
        <a className="btn dark" href={CLASSROOM + '/painel/'}>
          Acessar o ambiente de contas
        </a>
      ) : ready === false ? (
        <p className="notice">
          O cadastro e a sincronização entre dispositivos aguardam a conexão do banco da escola. Você já
          pode estudar e registrar seu progresso aqui.
        </p>
      ) : (
        <form
          className="login-form"
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget,
              fd = new FormData(form);
            setBusy(true);
            try {
              await api(register ? 'register' : 'login', {
                name: fd.get('name'),
                password: fd.get('password'),
              });
              form.reset();
              await loadStudent();
              setMsg('');
            } catch (err) {
              setMsg((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Nome de usuário
            <input
              autoComplete="username"
              required
              name="name"
              minLength={3}
              maxLength={40}
              pattern="[a-zA-Z0-9_.-]{3,40}"
              className="field"
            />
          </label>
          <label>
            Senha {register && '(12 caracteres ou mais)'}
            <input
              type="password"
              name="password"
              autoComplete={register ? 'new-password' : 'current-password'}
              minLength={register ? 12 : 1}
              maxLength={128}
              required
              className="field"
            />
          </label>
          <div className="row-actions">
            <button className="btn dark" disabled={busy || ready !== true}>
              {busy ? 'Aguarde…' : register ? 'Cadastrar' : 'Entrar'}
            </button>
            <button
              type="button"
              className="text-link"
              onClick={() => {
                setReg(!register);
                setMsg('');
              }}
            >
              {register ? 'Usar conta existente' : 'Criar conta'}
            </button>
          </div>
        </form>
      )}
      <p role="status">{msg}</p>
    </section>
  );
}
export default function Panel({ all }: { all: Card[] }) {
  const s = useStudent(),
    stats = useMemo(() => summarize(s.entries), [s.entries]),
    lookup = new Map(all.map((l) => [l.slug, l])),
    [sel, setSel] = useState('Revisão'),
    [cert, setCert] = useState(''),
    [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (s.account)
      api('session')
        .then((r) => setEnabled(r.certificates === true))
        .catch(() => {});
  }, [s.account?.name]);
  const [legacy, setLegacy] = useState<string[]>([]);
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('cosmos-v3-progress') ?? '[]');
      if (Array.isArray(stored)) setLegacy(stored.filter((x) => Object.hasOwn(chapters, x)));
    } catch {}
  }, []);
  const resume = lookup.get(stats.latest) ?? all[0];
  const label = (id: string) => lookup.get(id)?.title ?? id;
  return (
    <>
      <Meta title="Meu espaço" />
      <Lead
        tag="Área do estudante"
        title="Meu espaço"
        text="Retome a última aula e acompanhe os conceitos que já praticou."
      >
        <a className="btn light" href={'/aulas/' + resume.slug + '/'}>
          {stats.latest ? 'Retomar aula' : 'Começar a aprender'}
        </a>
      </Lead>
      <div className="wrap block panel-grid">
        <div>
          <h2>Seu percurso</h2>
          {s.loaded ? (
            <p>
              {stats.done.size} de {all.length} aulas com exercício resolvido · {stats.attempts.length}{' '}
              tentativas
            </p>
          ) : (
            <p>Carregando seu progresso…</p>
          )}
          <div className="progress-list">
            {levels.map((l, i) => {
              const items = all.filter((a) => a.level === i + 1);
              const n = items.filter((a) => stats.done.has(a.slug)).length;
              return (
                <div key={l.name}>
                  <a href={'/niveis/' + (i + 1) + '/'}>{l.name}</a>
                  <span>
                    {n} / {items.length}
                  </span>
                  <progress value={n} max={items.length}>
                    {n}
                  </progress>
                </div>
              );
            })}
          </div>
          {legacy.length > 0 && (
            <details className="legacy">
              <summary>Capítulos concluídos na edição anterior ({legacy.length})</summary>
              {legacy.map((k) => (
                <p key={k}>
                  <a href={'/aulas/' + chapters[k] + '/'}>{k.replace(/-/g, ' ')}</a>
                </p>
              ))}
            </details>
          )}
          <h2>Atividade</h2>
          <div className="tabs">
            {['Revisão', 'Favoritos', 'Anotações', 'Histórico', 'Avaliações', 'Conquistas'].map((t) => (
              <button key={t} type="button" aria-pressed={sel === t} onClick={() => setSel(t)}>
                {t}
              </button>
            ))}
          </div>
          <div className="activity">
            {sel === 'Revisão' && (
              <>
                {!stats.reviews.length && (
                  <p>
                    Nenhuma revisão vencida. Uma resposta correta agenda o próximo encontro com o
                    conceito.
                  </p>
                )}
                {stats.reviews.map((id) => (
                  <p key={id}>
                    <a href={'/aulas/' + id + '/#exercicio'}>{label(id)}</a>
                  </p>
                ))}
              </>
            )}
            {sel === 'Favoritos' && (
              <>
                {!stats.favorites.size && <p>Use “Favoritar” na aula que deseja guardar.</p>}
                {[...stats.favorites].map((id) => (
                  <p key={id}>
                    <a href={'/aulas/' + id + '/'}>{label(id)}</a>
                  </p>
                ))}
              </>
            )}
            {sel === 'Anotações' && (
              <>
                {!Object.values(stats.notes).some(Boolean) && <p>Suas anotações aparecerão aqui.</p>}
                {Object.entries(stats.notes)
                  .filter(([, v]) => v)
                  .map(([id, v]) => (
                    <div key={id}>
                      <h3>
                        <a href={'/aulas/' + id + '/'}>{label(id)}</a>
                      </h3>
                      <p>{v}</p>
                    </div>
                  ))}
              </>
            )}
            {sel === 'Histórico' && (
              <>
                {!s.entries.length && <p>Abra sua primeira aula para iniciar o histórico.</p>}
                {s.entries
                  .filter((e) => e.kind === 'open' || e.kind === 'attempt' || e.kind === 'lab')
                  .slice(-60)
                  .reverse()
                  .map((e) => (
                    <p key={e.id}>
                      <small>{new Date(e.at).toLocaleDateString('pt-BR')}</small> ·{' '}
                      <a
                        href={
                          e.kind === 'lab'
                            ? '/laboratorios/' + e.lesson + '/'
                            : '/aulas/' + e.lesson + '/'
                        }
                      >
                        {label(e.lesson)}
                      </a>{' '}
                      · {e.kind === 'open' ? 'Leitura' : e.correct ? 'Acerto' : 'Tentativa'}
                    </p>
                  ))}
              </>
            )}
            {sel === 'Avaliações' && (
              <>
                {!stats.assessments.length && (
                  <p>Escolha o diagnóstico ou a avaliação na página do seu nível.</p>
                )}
                {stats.assessments
                  .slice()
                  .reverse()
                  .map((e) => (
                    <p key={e.id}>
                      {e.lesson.startsWith('diagnostico') ? 'Diagnóstico' : 'Avaliação'} do nível{' '}
                      {e.lesson.split('-')[1]} · {e.score}/{e.total}
                    </p>
                  ))}
              </>
            )}
            {sel === 'Conquistas' && (
              <>
                {s.entries.some((e) => e.kind === 'lab' && e.correct) && (
                  <p>
                    ✦ Experimentos reproduzidos ·{' '}
                    {
                      new Set(
                        s.entries.filter((e) => e.kind === 'lab' && e.correct).map((e) => e.lesson)
                      ).size
                    }{' '}
                    de 15 bancadas
                  </p>
                )}
                {!stats.done.size && <p>Resolva um exercício para conquistar seu primeiro registro.</p>}
                {stats.done.size > 0 && <p>✦ Primeiro conceito aplicado · exercício resolvido</p>}
                {levels.map((l, i) => {
                  const full = all.filter((a) => a.level === i + 1).every((a) => stats.done.has(a.slug));
                  return (
                    full && (
                      <div key={l.name}>
                        <p>✦ Trilha concluída · {l.name}</p>
                        {enabled && (
                          <button
                            className="small-btn"
                            onClick={async () => {
                              try {
                                const r = await api('certificate', { level: i + 1 });
                                setCert(location.origin + '/certificado/?id=' + r.id);
                              } catch (e) {
                                setCert((e as Error).message);
                              }
                            }}
                          >
                            Emitir certificado
                          </button>
                        )}
                      </div>
                    )
                  );
                })}
                {cert && (
                  <p>
                    {cert.startsWith('https:') || cert.startsWith('http:') ? (
                      <a href={cert}>Abrir certificado</a>
                    ) : (
                      cert
                    )}
                  </p>
                )}
              </>
            )}
          </div>
        </div>
        <aside>
          <Account />
          {s.sync && <p role="status">{s.sync}</p>}
        </aside>
      </div>
    </>
  );
}
