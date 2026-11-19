import { useState } from 'react';
import { CourseImage } from './CourseImage';
import { canon, levels, type Card } from '../lib/school';
import { usePublished } from '../lib/student';
export function LevelCard({ i }: { i: number }) {
  const l = levels[i];
  return (
    <a className="level-card" href={'/niveis/' + (i + 1) + '/'}>
      <div className="card-art">
        <CourseImage
          file={l.image}
          sizes="(max-width: 680px) calc(100vw - 36px), (max-width: 900px) 45vw, (max-width: 1300px) 30vw, 390px"
          alt={
            i === 2
              ? 'Fotografia de M51 e sua companheira, Hubble'
              : i === 4
                ? 'Mapa de temperatura do céu observado pelo Planck'
                : ''
          }
        />
        <span className="level-index">Nível {String(i + 1).padStart(2, '0')}</span>
      </div>
      <div className="card-copy">
        <small>{l.subjects.length} disciplinas</small>
        <h3>{l.name}</h3>
        <p>{l.blurb}</p>
      </div>
    </a>
  );
}
export function LessonList({ items }: { items: Card[] }) {
  return (
    <ol className="lesson-list">
      {items.map((l) => (
        <li key={l.slug}>
          <a href={'/aulas/' + l.slug + '/'}>
            <div>
              <small>
                {l.subject} · Aula {l.order}
              </small>
              <strong>{l.title}</strong>
            </div>
            <span aria-hidden="true">›</span>
          </a>
        </li>
      ))}
    </ol>
  );
}
export function LibrarySearch({ all }: { all: Card[] }) {
  const [s, setS] = useState(''),
    [lvl, setLvl] = useState(0);
  const items = all.filter(
    (l) => (!lvl || l.level === lvl) && canon(l.title + l.subject + l.objective).includes(canon(s))
  );
  const extra = usePublished().filter(
    (e) =>
      (!lvl || e.payload.level === lvl) && canon(e.payload.title + e.payload.subject).includes(canon(s))
  );
  return (
    <section className="wrap block">
      <div className="section-title">
        <div>
          <p className="kicker">Catálogo</p>
          <h2>Encontre uma aula</h2>
        </div>
      </div>
      <div className="search-row">
        <label>
          Buscar por tema
          <input
            className="field"
            type="search"
            placeholder="Ex.: gravitação, galáxias, energia"
            value={s}
            onChange={(e) => setS(e.target.value)}
          />
        </label>
        <label>
          Nível
          <select className="field" value={lvl} onChange={(e) => setLvl(+e.target.value)}>
            <option value="0">Todos os níveis</option>
            {levels.map((l, i) => (
              <option key={l.name} value={i + 1}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p role="status">
        {items.length} aulas no currículo
        {extra.length ? ' e ' + extra.length + ' publicações editoriais' : ''}.
      </p>
      <LessonList items={items} />
      {extra.map((e) => (
        <p key={e.key}>
          <a href={'/leitura/?id=' + e.key}>{e.payload.title}</a> · {e.payload.type}
        </p>
      ))}
      {!items.length && !extra.length && (
        <p>Experimente pesquisar pela disciplina ou escolher outro nível.</p>
      )}
    </section>
  );
}
