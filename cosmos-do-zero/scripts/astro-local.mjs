// Keep builds and development runs local: no Astro telemetry is sent.
process.env.ASTRO_TELEMETRY_DISABLED = '1';
await import('../node_modules/astro/bin/astro.mjs');
