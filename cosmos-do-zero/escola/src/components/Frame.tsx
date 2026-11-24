import { useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { NEXO, ORIGIN } from '../lib/school';
import { usePremiumMotion } from './premium-motion';
export function OrbitMark() {
  return (
    <svg viewBox="0 0 48 42" fill="none" aria-hidden="true">
      <circle cx="24" cy="21" r="11" stroke="currentColor" strokeWidth="1.7" />
      <ellipse
        cx="24"
        cy="21"
        rx="22"
        ry="6.7"
        transform="rotate(-31 24 21)"
        stroke="currentColor"
        strokeWidth="1.65"
      />
      <circle cx="41.3" cy="9.8" r="2.5" fill="currentColor" />
    </svg>
  );
}
export function AccountIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      aria-hidden="true"
    >
      <circle cx="12" cy="8" r="3.4" />
      <path d="M5 20c0-4 3.1-6 7-6s7 2 7 6" />
    </svg>
  );
}
const nav = [
  ['/trilhas/', 'Trilhas'],
  ['/laboratorios/', 'Laboratórios'],
  ['/explorador/', 'Explorador'],
];
export function Frame({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const disclosure = useRef<HTMLDetailsElement>(null);
  usePremiumMotion(router.asPath);
  useEffect(() => {
    document.documentElement.dataset.ready = 'true';
    if (disclosure.current) disclosure.current.open = false;
  }, [router.asPath]);
  return (
    <>
      <a className="skip" href="#conteudo">
        Pular para o conteúdo
      </a>
      <header className="site-header">
        <div className="bar">
          <a className="wordmark" href="/" aria-label="Cosmos, início">
            <OrbitMark />
            <span>COSMOS</span>
          </a>
          <nav className="desktop-nav" aria-label="Navegação principal">
            {nav.map(([url, name]) => (
              <a key={url} href={url} aria-current={router.asPath.startsWith(url) ? 'page' : undefined}>
                {name}
              </a>
            ))}
          </nav>
          <div className="nav-actions">
            <a className="account-link" href="/painel/">
              <AccountIcon />
              <span>Meu espaço</span>
            </a>
            <details
              className="mobile-disclosure"
              ref={disclosure}
              onKeyDown={(event) => {
                if (event.key === 'Escape' && disclosure.current?.open) {
                  disclosure.current.open = false;
                  disclosure.current.querySelector('summary')?.focus();
                }
              }}
            >
              <summary className="menu-button" role="button" aria-controls="mobile-menu">
                <span className="menu-collapsed">
                  <span aria-hidden="true">☰</span>
                  <span className="screen-reader-only">Abrir menu</span>
                </span>
                <span className="menu-expanded">
                  <span aria-hidden="true">×</span>
                  <span className="screen-reader-only">Fechar menu</span>
                </span>
              </summary>
              <nav id="mobile-menu" aria-label="Menu celular">
                {nav.map(([u, n]) => (
                  <a key={u} href={u} aria-current={router.asPath.startsWith(u) ? 'page' : undefined}>
                    {n}
                  </a>
                ))}
              </nav>
            </details>
          </div>
        </div>
      </header>
      <main id="conteudo" tabIndex={-1}>
        {children}
      </main>
      <footer>
        <div className="foot wrap">
          <a className="wordmark" href="/">
            <OrbitMark />
            COSMOS
          </a>
          <p>Escola de Física, Astronomia e Cosmologia</p>
          <a href="/fontes/">Fontes e créditos</a>
          <a href={NEXO}>NEXO Research ↗</a>
        </div>
      </footer>
    </>
  );
}
export function Meta({
  title,
  desc = 'Aulas, experimentos e viagens guiadas pela física do Universo.',
}: {
  title: string;
  desc?: string;
}) {
  const r = useRouter();
  const path = r.asPath.split(/[?#]/)[0];
  return (
    <Head>
      <title>{title + ' · Cosmos'}</title>
      <meta name="description" content={desc} />
      <link rel="canonical" href={ORIGIN + path} />
      <meta property="og:type" content="website" />
      <meta property="og:locale" content="pt_BR" />
      <meta property="og:site_name" content="Cosmos" />
      <meta property="og:title" content={title + ' · Cosmos'} />
      <meta property="og:description" content={desc} />
      <meta property="og:url" content={ORIGIN + path} />
      <meta property="og:image" content={ORIGIN + '/cosmos-social.jpg'} />
      <meta property="og:image:type" content="image/jpeg" />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:alt" content="Ilustração de Saturno e seus anéis" />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <meta name="theme-color" content="#090e1b" />
      <link rel="icon" href="/simbolo.svg" />
    </Head>
  );
}
export function Lead({
  tag,
  title,
  text,
  children,
}: {
  tag: string;
  title: string;
  text?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="lead">
      <div className="wrap">
        <p className="kicker">{tag}</p>
        <h1>{title}</h1>
        {text && <p className="deck">{text}</p>}
        {children}
      </div>
    </div>
  );
}

