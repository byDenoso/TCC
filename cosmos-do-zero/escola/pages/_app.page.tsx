import type { AppProps } from 'next/app';
import '@fontsource-variable/inter/wght.css';
import '@fontsource/ibm-plex-mono/latin-400.css';
import 'katex/dist/katex.min.css';
import '../styles/globals.css';
import '../src/components/hero/hero-sky.css';
import '../src/components/explorer/explorer.css';
import '../styles/premium.css';
import '../styles/institutional.css';
import { Frame } from '../src/components/Frame';
export default function App({ Component, pageProps }: AppProps) {
  return (
    <Frame>
      <Component {...pageProps} />
    </Frame>
  );
}
