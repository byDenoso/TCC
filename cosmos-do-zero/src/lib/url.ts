/** Prefixa caminhos internos com o `base` do Astro (permite publicar em subpasta sem editar componentes). */
export const u = (path: string): string => {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
};
export const chapterUrl = (id: string): string => u(`/capitulos/${id}/`);
