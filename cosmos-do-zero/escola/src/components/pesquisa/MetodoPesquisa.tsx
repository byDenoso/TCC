import { useMemo, useState } from 'react';
import dados from './desi-dr2-bao.json';
import { NEXO } from '../../lib/school';

/*
 * Distâncias da régua acústica (BAO) medidas pelo DESI DR2 contra a previsão do ΛCDM plano.
 * D_M = c/H0 ∫dz/E(z), D_H = c/H(z), D_V = (z D_M² D_H)^(1/3), todas divididas por r_d.
 * Com h·r_d fixo, só c/(H0 r_d) = 2997,92458 Mpc / (h r_d) multiplica a forma de E(z).
 * O χ² usa a covariância completa publicada (13 × 13).
 */

type Ponto = { z: number; valor: number; tipo: 'DM' | 'DH' | 'DV' };
const pontos = dados.pontos as Ponto[];
const N = pontos.length;

function inversa(m: number[][]) {
  const n = m.length;
  const a = m.map((linha, i) => [...linha, ...Array.from({ length: n }, (_, j) => (i === j ? 1 : 0))]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let i = c + 1; i < n; i++) if (Math.abs(a[i][c]) > Math.abs(a[p][c])) p = i;
    [a[c], a[p]] = [a[p], a[c]];
    const piv = a[c][c];
    for (let j = 0; j < 2 * n; j++) a[c][j] /= piv;
    for (let i = 0; i < n; i++) {
      if (i === c) continue;
      const f = a[i][c];
      for (let j = 0; j < 2 * n; j++) a[i][j] -= f * a[c][j];
    }
  }
  return a.map((linha) => linha.slice(n));
}
const icov = inversa(dados.cov);

const ZMAX = 2.6;
const DZ = 0.005;
/** Integral acumulada de dz/E(z) numa grade, regra do trapézio. */
function distancias(om: number) {
  const E = (z: number) => Math.sqrt(om * (1 + z) ** 3 + 1 - om);
  const n = Math.round(ZMAX / DZ);
  const acum = new Float64Array(n + 1);
  for (let i = 1; i <= n; i++) acum[i] = acum[i - 1] + (DZ * (1 / E((i - 1) * DZ) + 1 / E(i * DZ))) / 2;
  const integral = (z: number) => {
    const x = z / DZ;
    const i = Math.min(n - 1, Math.floor(x));
    return acum[i] + (acum[i + 1] - acum[i]) * (x - i);
  };
  return { E, integral };
}

function modelo(om: number, hrd: number) {
  const k = 2997.92458 / hrd;
  const { E, integral } = distancias(om);
  const DM = (z: number) => k * integral(z);
  const DH = (z: number) => k / E(z);
  const DV = (z: number) => Math.cbrt(z * DM(z) ** 2 * DH(z));
  return { DM, DH, DV };
}

function qui2(om: number, hrd: number) {
  const m = modelo(om, hrd);
  const r = pontos.map((p) => p.valor - m[p.tipo](p.z));
  let s = 0;
  for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) s += r[i] * icov[i][j] * r[j];
  return s;
}

const PRESETS = [
  { nome: 'Planck 2018', om: 0.3153, hrd: 99.08 },
  { nome: 'Melhor ajuste só com o DESI', om: 0.2975, hrd: 101.54 },
];

const W = 560;
const H = 340;
const M = { l: 46, r: 16, t: 16, b: 40 };
const sx = (z: number) => M.l + (z / ZMAX) * (W - M.l - M.r);
const sy = (v: number) => H - M.b - (v / 44) * (H - M.t - M.b);
const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt3 = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3, minimumFractionDigits: 3 });
const fmt2 = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2, minimumFractionDigits: 2 });

export function MetodoPesquisa() {
  const [om, setOm] = useState(PRESETS[0].om);
  const [hrd, setHrd] = useState(PRESETS[0].hrd);
  const m = useMemo(() => modelo(om, hrd), [om, hrd]);
  const x2 = useMemo(() => qui2(om, hrd), [om, hrd]);
  const curva = (f: (z: number) => number, z0 = 0.02, z1 = ZMAX) => {
    const pts: string[] = [];
    for (let z = z0; z <= z1 + 1e-9; z += 0.02) pts.push(`${sx(z).toFixed(1)},${sy(f(z)).toFixed(1)}`);
    return 'M' + pts.join('L');
  };
  const sig = (i: number) => Math.sqrt(dados.cov[i][i]);
  const cor = { DM: '#8fd0c6', DH: '#e8b779', DV: '#e7ecf2' } as const;
  return (
    <section className="research-band">
      <div className="wrap research-grid">
        <div>
          <p className="kicker">A escola e a pesquisa</p>
          <h2>A mesma conta, com dados de 2025</h2>
          <p>
            Nas aulas, você escreve uma relação, calcula a previsão e compara com a medida. Aqui está a mesma
            sequência com dados de pesquisa: as distâncias que o DESI mediu com a régua acústica das galáxias,
            em sete intervalos de redshift, e a previsão do modelo ΛCDM.
          </p>
          <p>
            Com os parâmetros do Planck, a previsão fica a χ² ≈ 30 das 13 medidas; o melhor ΛCDM ajustado só ao
            DESI fica em χ² ≈ 10. A diferença entre os dois conjuntos é uma das tensões estudadas hoje na
            cosmologia e uma das linhas do NEXO Research.
          </p>
          <a className="text-link" href={NEXO}>
            Conhecer o NEXO Research ↗
          </a>
        </div>
        <figure className="metodo-figura">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Distâncias BAO do DESI DR2 e previsão do ΛCDM com Ωm = ${fmt3.format(om)}; χ² = ${fmt.format(x2)} para 13 medidas.`}>
            {[0, 10, 20, 30, 40].map((v) => (
              <g key={v}>
                <line x1={M.l} x2={W - M.r} y1={sy(v)} y2={sy(v)} className="metodo-grade" />
                <text x={M.l - 8} y={sy(v) + 4} textAnchor="end" className="metodo-eixo">{v}</text>
              </g>
            ))}
            {[0, 0.5, 1, 1.5, 2, 2.5].map((z) => (
              <text key={z} x={sx(z)} y={H - M.b + 18} textAnchor="middle" className="metodo-eixo">{String(z).replace('.', ',')}</text>
            ))}
            <text x={(W + M.l) / 2} y={H - 4} textAnchor="middle" className="metodo-eixo">redshift z</text>
            <text x={12} y={M.t + 4} className="metodo-eixo">D / r_d</text>
            <path d={curva(m.DM)} stroke={cor.DM} className="metodo-curva" />
            <path d={curva(m.DH)} stroke={cor.DH} className="metodo-curva" />
            <path d={curva(m.DV, 0.05, 0.8)} stroke={cor.DV} className="metodo-curva" strokeDasharray="4 4" />
            {pontos.map((p, i) => (
              <g key={i} stroke={cor[p.tipo]}>
                <line x1={sx(p.z)} x2={sx(p.z)} y1={sy(p.valor - 2 * sig(i))} y2={sy(p.valor + 2 * sig(i))} strokeWidth={1.4} />
                <circle cx={sx(p.z)} cy={sy(p.valor)} r={3.6} fill="#0d1b29" strokeWidth={1.6} />
              </g>
            ))}
            <text x={sx(1.62)} y={sy(m.DM(1.62)) - 12} fill={cor.DM} className="metodo-rotulo" textAnchor="end">D_M (transversal)</text>
            <text x={sx(1.9)} y={sy(m.DH(1.9)) + 20} fill={cor.DH} className="metodo-rotulo">D_H (radial)</text>
            <text x={sx(0.36)} y={sy(m.DV(0.3)) - 14} fill={cor.DV} className="metodo-rotulo">D_V</text>
          </svg>
          <div className="metodo-controles">
            <label>
              <span>Densidade de matéria Ωm</span>
              <output>{fmt3.format(om)}</output>
              <input type="range" min={0.25} max={0.36} step={0.0005} value={om} onChange={(e) => setOm(Number(e.target.value))} />
            </label>
            <label>
              <span>h · r_d</span>
              <output>{fmt2.format(hrd)} Mpc</output>
              <input type="range" min={95} max={105} step={0.05} value={hrd} onChange={(e) => setHrd(Number(e.target.value))} />
            </label>
            <p className="metodo-qui2">
              χ² = <strong>{fmt.format(x2)}</strong> <span>para 13 medidas</span>
            </p>
            <div className="metodo-presets">
              {PRESETS.map((p) => (
                <button key={p.nome} type="button" onClick={() => { setOm(p.om); setHrd(p.hrd); }}>
                  {p.nome}
                </button>
              ))}
            </div>
          </div>
          <figcaption>
            Pontos: DESI DR2, barras de 2σ (DESI Collaboration 2025, arXiv:2503.14738). Linhas: ΛCDM plano, sem
            radiação. O χ² usa a covariância completa publicada.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
