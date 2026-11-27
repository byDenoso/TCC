import dynamic from 'next/dynamic';
import { useCallback, useEffect, useRef, useState } from 'react';
import { estacoes, type Estacao } from './estacoes';
import { formatar } from './fisica';

const Palco = dynamic(() => import('./Palco'), { ssr: false });
const CHAVE = 'cosmos-viagem';
const n2 = (i: number) => String(i + 1).padStart(2, '0');

function suportaWebGL() {
  try {
    const c = document.createElement('canvas');
    return Boolean(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
}

/** Altura do palco fixo no celular (0 no desktop, onde o palco fica ao lado do texto). */
function alturaPalco() {
  if (window.matchMedia('(min-width: 900px)').matches) return 0;
  return document.querySelector('.viagem-fixo')?.getBoundingClientRect().height ?? window.innerHeight * 0.56;
}

/**
 * Leva o topo da estação para logo abaixo do palco. Calcula a posição e usa scrollTo: no celular,
 * scrollIntoView chamado a partir de um botão dentro do palco fixo era ignorado em um toque sim,
 * outro não.
 */
function rolarAte(sec: HTMLElement, suave: boolean) {
  const topo = window.scrollY + sec.getBoundingClientRect().top - alturaPalco();
  // 'instant' ignora o scroll-behavior: smooth do CSS global; 'auto' viraria animação longa
  window.scrollTo({ top: Math.max(0, Math.round(topo)), behavior: suave ? 'smooth' : 'instant' });
}

/* O controle deslizante trabalha em 0–1000 e converte para a grandeza física. */
const PASSOS = 1000;
function paraFisico(e: Estacao, s: number) {
  const { min, max, log } = e.controle;
  const f = s / PASSOS;
  return log ? min * (max / min) ** f : min + (max - min) * f;
}
function paraSlider(e: Estacao, v: number) {
  const { min, max, log } = e.controle;
  return Math.round(PASSOS * (log ? Math.log(v / min) / Math.log(max / min) : (v - min) / (max - min)));
}
function arredondar(e: Estacao, v: number) {
  const p = e.controle.passo;
  return Math.round(v / p) * p;
}

function Controle({ e, valor, onChange }: { e: Estacao; valor: number; onChange: (v: number) => void }) {
  const id = 'controle-' + e.id;
  const texto = e.controle.formato ? e.controle.formato(valor) : `${formatar(valor)}${e.controle.unidade ? ' ' + e.controle.unidade : ''}`;
  return (
    <div className="viagem-controle">
      <label htmlFor={id}>
        <span>{e.controle.rotulo}</span>
        <output htmlFor={id}>{texto}</output>
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={PASSOS}
        step={1}
        value={paraSlider(e, valor)}
        aria-valuetext={texto}
        onChange={(ev) => onChange(arredondar(e, paraFisico(e, Number(ev.target.value))))}
      />
    </div>
  );
}

export default function Viagem() {
  const [ativa, setAtiva] = useState(0);
  const [valores, setValores] = useState(() => estacoes.map((e) => e.controle.inicial));
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [movimento, setMovimento] = useState(true);
  const [pronta, setPronta] = useState<string | null>(null);
  const [largo, setLargo] = useState(true);
  const [dentro, setDentro] = useState(false);
  const [lendo, setLendo] = useState(false);
  const secoes = useRef<(HTMLElement | null)[]>([]);
  const raiz = useRef<HTMLElement>(null);
  const indice = useRef<HTMLDetailsElement>(null);
  const mexeu = useRef(false);
  const irRef = useRef<(i: number) => void>(() => {});

  useEffect(() => {
    setWebgl(suportaWebGL());
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const mw = window.matchMedia('(min-width: 900px)');
    const sync = () => {
      setMovimento(!mq.matches);
      setLargo(mw.matches);
    };
    sync();
    mq.addEventListener('change', sync);
    mw.addEventListener('change', sync);
    // link direto para uma estação: a página pode voltar ao topo durante a hidratação, então a
    // rolagem é refeita uma vez, a menos que a pessoa já tenha começado a navegar
    const alvo = estacoes.findIndex((e) => '#' + e.id === window.location.hash);
    const timers: number[] = [];
    if (alvo >= 0) {
      setAtiva(alvo);
      const ir0 = () => {
        const sec = secoes.current[alvo];
        if (!sec || mexeu.current) return;
        const topo = sec.getBoundingClientRect().top;
        if (Math.abs(topo - alturaPalco()) > 24) rolarAte(sec, false);
      };
      timers.push(window.setTimeout(ir0, 30), window.setTimeout(ir0, 450), window.setTimeout(ir0, 1200));
    }
    const marcar = () => (mexeu.current = true);
    const eventos = ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const;
    eventos.forEach((ev) => window.addEventListener(ev, marcar, { passive: true }));
    // troca de âncora na mesma página (links do índice, botão voltar do navegador)
    const ancora = () => {
      const i = estacoes.findIndex((e) => '#' + e.id === window.location.hash);
      const sec = secoes.current[i];
      if (sec) rolarAte(sec, false);
    };
    window.addEventListener('hashchange', ancora);
    const clique = (ev: MouseEvent) => {
      const a = (ev.target as HTMLElement | null)?.closest?.('a[href^="#"]') as HTMLAnchorElement | null;
      if (!a || a.closest('.viagem')) return;
      const i = estacoes.findIndex((e) => '#' + e.id === a.getAttribute('href'));
      if (i < 0) return;
      ev.preventDefault();
      history.replaceState(null, '', '#' + estacoes[i].id);
      irRef.current(i);
    };
    document.addEventListener('click', clique);
    return () => {
      mq.removeEventListener('change', sync);
      mw.removeEventListener('change', sync);
      window.removeEventListener('hashchange', ancora);
      document.removeEventListener('click', clique);
      eventos.forEach((ev) => window.removeEventListener(ev, marcar));
      timers.forEach((t) => clearTimeout(t));
    };
  }, []);

  /** Estação que cruza a linha de leitura agora (meio da tela; no celular, 48 px abaixo do palco). */
  const naLinha = useCallback(() => {
    const linha = window.matchMedia('(min-width: 900px)').matches ? window.innerHeight * 0.5 : alturaPalco() + 48;
    let escolhida = -1;
    secoes.current.forEach((sec, i) => {
      if (!sec) return;
      const r = sec.getBoundingClientRect();
      if (r.top <= linha && r.bottom > linha) escolhida = i;
    });
    return escolhida;
  }, []);

  useEffect(() => {
    let quadro = 0;
    const medir = () => {
      quadro = 0;
      const escolhida = naLinha();
      if (escolhida >= 0) setAtiva(escolhida);
      setLendo(escolhida >= 0);
      const caixa = raiz.current?.getBoundingClientRect();
      setDentro(Boolean(caixa && caixa.top < window.innerHeight && caixa.bottom > 0));
    };
    const pedir = () => {
      if (!quadro) quadro = requestAnimationFrame(medir);
    };
    medir();
    window.addEventListener('scroll', pedir, { passive: true });
    window.addEventListener('resize', pedir);
    return () => {
      window.removeEventListener('scroll', pedir);
      window.removeEventListener('resize', pedir);
      if (quadro) cancelAnimationFrame(quadro);
    };
  }, [largo, naLinha]);

  useEffect(() => {
    // o endereço só muda quando uma estação está de fato na linha de leitura
    if (!lendo) return;
    const id = estacoes[ativa].id;
    if (window.location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
    try {
      localStorage.setItem(CHAVE, id);
    } catch {
      /* armazenamento indisponível: a viagem continua sem lembrar a estação */
    }
  }, [ativa, lendo]);

  const ir = useCallback((i: number) => {
    mexeu.current = true;
    const k = Math.max(0, Math.min(estacoes.length - 1, i));
    setAtiva(k);
    const alvo = secoes.current[k];
    // saltos curtos rolam suavemente; saltos longos são imediatos (não ficam no meio do caminho)
    const longe = alvo ? Math.abs(alvo.getBoundingClientRect().top) > window.innerHeight * 1.6 : false;
    // no celular o salto é sempre direto: a rolagem suave atravessaria estações e seria interrompida pelo toque
    const desktop = window.matchMedia('(min-width: 900px)').matches;
    if (alvo) rolarAte(alvo, movimento && !longe && desktop);
    if (indice.current) indice.current.open = false;
  }, [movimento]);

  irRef.current = ir;

  // setas do teclado avançam de estação quando o foco não está num controle
  useEffect(() => {
    const tecla = (ev: KeyboardEvent) => {
      if (!dentro) return;
      const alvo = ev.target as HTMLElement;
      if (alvo.closest('input, textarea, select, summary')) return;
      if (ev.key === 'ArrowRight') ir(ativa + 1);
      if (ev.key === 'ArrowLeft') ir(ativa - 1);
    };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [ativa, dentro, ir]);

  const atual = estacoes[ativa];
  // o palco só troca de modelo quando a estação fica parada um instante: rolar rápido não baixa
  // nem monta os modelos das estações intermediárias
  const [idPalco, setIdPalco] = useState(estacoes[0].id);
  useEffect(() => {
    const t = setTimeout(() => setIdPalco(atual.id), 280);
    return () => clearTimeout(t);
  }, [atual.id]);
  const onPronto = useCallback((id: string) => setPronta(id), []);
  const mostrarPoster = webgl === false || pronta !== atual.id || idPalco !== atual.id;

  return (
    <section className="viagem" ref={raiz} aria-labelledby="viagem-titulo">
      <h2 id="viagem-titulo" className="screen-reader-only">
        Viagem em nove estações
      </h2>
      <noscript>
        <style>{'.viagem-fixo{display:none}.viagem-estacoes{margin-top:0}.viagem-estacao{min-height:0}'}</style>
      </noscript>
      <div className="viagem-fixo">
        <div className="viagem-palco" aria-hidden="true">
          {estacoes.map((e) => (
            <img
              key={e.id}
              className="viagem-poster"
              data-visivel={e.id === atual.id && mostrarPoster ? 'sim' : 'nao'}
              src={`/viagem/${e.id}.webp`}
              srcSet={`/viagem/${e.id}-1200.webp 1200w, /viagem/${e.id}.webp 2400w`}
              sizes="(max-width: 899px) 100vw, 62vw"
              alt=""
              loading={e.id === estacoes[0].id ? 'eager' : 'lazy'}
              decoding="async"
            />
          ))}
          {webgl && dentro && (
            <Palco
              id={idPalco}
              valor={valores[estacoes.findIndex((e) => e.id === idPalco)]}
              movimento={movimento}
              deslocamento={0}
              onPronto={onPronto}
            />
          )}
        </div>
        <nav className="viagem-trilho" aria-label="Estações da viagem">
          <ol>
            {estacoes.map((e, i) => (
              <li key={e.id}>
                <a href={'#' + e.id} aria-current={i === ativa ? 'step' : undefined} onClick={(ev) => { ev.preventDefault(); ir(i); }}>
                  <span>{n2(i)}</span>
                  {e.rotulo}
                </a>
              </li>
            ))}
          </ol>
          <div className="viagem-trilho-curto">
            <button type="button" onClick={() => ir((naLinha() < 0 ? ativa : naLinha()) - 1)} disabled={ativa === 0} aria-label="Estação anterior">
              ←
            </button>
            <span>
              {n2(ativa)} / {n2(estacoes.length - 1)} · {atual.rotulo}
            </span>
            <button type="button" onClick={() => ir((naLinha() < 0 ? ativa : naLinha()) + 1)} disabled={ativa === estacoes.length - 1} aria-label="Próxima estação">
              →
            </button>
          </div>
          <details className="viagem-indice" ref={indice}>
            <summary>
              <span className="viagem-indice-longo">Escolher por onde seguir</span>
              <span className="viagem-indice-curto">Estações</span>
            </summary>
            <div>
              <p className="kicker">Estações</p>
              <ol>
                {estacoes.map((e, i) => (
                  <li key={e.id}>
                    <a href={'#' + e.id} onClick={(ev) => { ev.preventDefault(); ir(i); }}>
                      <span>{n2(i)}</span>
                      {e.titulo}
                    </a>
                  </li>
                ))}
              </ol>
              <p className="kicker">Por conta própria</p>
              <ul>
                <li><a href="/trilhas/">Programa em seis níveis</a></li>
                <li><a href="/laboratorios/">Laboratórios</a></li>
                <li><a href="/explorador/">Atlas do Universo</a></li>
                <li><a href="/fontes/">Fontes e créditos</a></li>
              </ul>
            </div>
          </details>
        </nav>
      </div>
      <div className="viagem-estacoes">
        {estacoes.map((e, i) => {
          const prox = estacoes[i + 1];
          return (
            <article
              key={e.id}
              id={e.id}
              className="viagem-estacao"
              ref={(el) => {
                secoes.current[i] = el;
              }}
              aria-labelledby={'titulo-' + e.id}
            >
              <div className="viagem-painel">
                <noscript>
                  <img className="viagem-figura" src={`/viagem/${e.id}-1200.webp`} alt="" width={1200} height={750} />
                </noscript>
                <p className="kicker">
                  <i />
                  Estação {n2(i)} · {e.rotulo}
                </p>
                <h3 id={'titulo-' + e.id}>{e.titulo}</h3>
                {e.texto.map((p) => (
                  <p key={p.slice(0, 24)}>{p}</p>
                ))}
                <Controle
                  e={e}
                  valor={valores[i]}
                  onChange={(v) => setValores((vs) => vs.map((x, j) => (j === i ? v : x)))}
                />
                <dl className="viagem-leituras">
                  {e.leituras(valores[i]).map((l) => (
                    <div key={l.rotulo}>
                      <dt>{l.rotulo}</dt>
                      <dd>
                        {l.valor}
                        {l.unidade && <span> {l.unidade}</span>}
                      </dd>
                    </div>
                  ))}
                </dl>
                <div className="viagem-acoes">
                  {prox ? (
                    <a className="btn editorial-primary" href={'#' + prox.id} onClick={(ev) => { ev.preventDefault(); ir(i + 1); }}>
                      Próxima estação: {prox.rotulo}
                    </a>
                  ) : (
                    <a className="btn editorial-primary" href="#programa">
                      Continuar no programa
                    </a>
                  )}
                </div>
                <div className="viagem-aprofundar">
                  <p className="kicker">Aprofundar</p>
                  <ul>
                    {e.aprofundar.map((a) => (
                      <li key={a.href}>
                        <a href={a.href}>{a.texto}</a>
                      </li>
                    ))}
                  </ul>
                </div>
                <p className="viagem-nota">{e.nota}</p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

/** Estação salva da última visita, para o botão "continuar" da abertura. */
export function useEstacaoSalva() {
  const [salva, setSalva] = useState<Estacao | null>(null);
  useEffect(() => {
    try {
      const id = localStorage.getItem(CHAVE);
      const e = estacoes.find((x) => x.id === id);
      if (e && e.id !== estacoes[0].id) setSalva(e);
    } catch {
      /* sem armazenamento */
    }
  }, []);
  return salva;
}
