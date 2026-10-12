import { defineConfig } from 'astro/config';

const deploymentHost = process.env.VERCEL_ENV === 'production'
  ? process.env.VERCEL_PROJECT_PRODUCTION_URL || process.env.VERCEL_URL
  : process.env.VERCEL_URL;
const site = process.env.SITE_URL || (deploymentHost ? `https://${deploymentHost}` : 'http://localhost:4321');

// Site estático. Sem adaptadores nem funções de servidor.
export default defineConfig({
  site,
  // Pages padrão: /TCC/cosmos-do-zero; cosmos.denerpereira.com.br: /.
  base: process.env.SITE_BASE || '/',
  trailingSlash: 'always',
  build: { format: 'directory', inlineStylesheets: 'auto' },
  devToolbar: { enabled: false },
  vite: {
    define: {
      'import.meta.env.PUBLIC_SITE_INDEXING': JSON.stringify(
        process.env.VERCEL_ENV === 'production' || process.env.SITE_PUBLIC === 'true' ? 'true' : 'false'
      )
    },
    build: { assetsInlineLimit: 0 }
  }
});
