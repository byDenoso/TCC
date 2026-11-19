import Head from 'next/head';
import { useEffect } from 'react';
export default function Redirect({ to }: { to: string }) {
  useEffect(() => {
    location.replace(to);
  }, [to]);
  return (
    <>
      <Head>
        <title>Acervo Cosmos</title>
        <link rel="canonical" href={'https://cosmos.denerpereira.com.br' + to} />
        <meta httpEquiv="refresh" content={'0;url=' + to} />
      </Head>
      <div className="wrap block">
        <a href={to}>Abrir conteúdo no Cosmos</a>
      </div>
    </>
  );
}
