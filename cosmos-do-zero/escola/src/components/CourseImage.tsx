// Cards occupy one to three columns. The full-resolution source and its credit remain in /imagens.
export function CourseImage({ file, alt = '', sizes }: { file: string; alt?: string; sizes: string }) {
  const base = '/imagens/mini/' + file.replace(/\.webp$/, '');
  return (
    <img
      loading="lazy"
      decoding="async"
      src={base + '-440.webp'}
      srcSet={`${base}-440.webp 440w, ${base}-820.webp 820w`}
      sizes={'auto, ' + sizes}
      width={440}
      height={file === 'm51.webp' ? 305 : 293}
      alt={alt}
    />
  );
}
