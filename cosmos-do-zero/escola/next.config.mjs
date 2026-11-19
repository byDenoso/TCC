const pages = process.env.COSMOS_STATIC === '1';
export default {
  ...(pages ? { output: 'export' } : {}),
  outputFileTracingRoot: process.cwd(),
  pageExtensions: pages ? ['page.tsx'] : ['page.tsx', 'api.ts'],
  trailingSlash: true,
  poweredByHeader: false,
  reactStrictMode: true,
  experimental: { cpus: 2 },
  images: { unoptimized: true },
  env: { NEXT_PUBLIC_COSMOS_STATIC: pages ? '1' : '0' },
};
