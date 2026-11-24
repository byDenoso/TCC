import { useEffect, useRef } from 'react';

// Cards preserve their intrinsic dimensions and original source/credit.
export function CourseImage({ file, alt = '', sizes }: { file: string; alt?: string; sizes: string }) {
  const base = '/imagens/mini/' + file.replace(/\.webp$/, '');
  const ref = useRef<HTMLImageElement>(null);
  useEffect(() => {
    const img = ref.current;
    if (img) img.dataset.imageState = img.complete ? (img.naturalWidth ? 'ready' : 'error') : 'pending';
  }, [file]);
  return (
    <img
      ref={ref}
      data-image-state="pending"
      onLoad={(event) => { event.currentTarget.dataset.imageState = 'ready'; }}
      onError={(event) => { event.currentTarget.dataset.imageState = 'error'; }}
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
