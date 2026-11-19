import { depthCanvas } from './lesson-depth';

/** Sample the same oval as the probe. The globe center is the selected map pixel. */
export function cmbSphere(
  canvas: HTMLCanvasElement | null,
  poster: HTMLImageElement,
) {
  let point = [0.5, 0.5],
    field: ImageData | undefined;
  const refresh = depthCanvas(canvas, (ctx, _images, w, h) => {
    if (!field || w !== h) return;
    const lat = (0.5 - point[1]) * Math.PI;
    const lon =
      ((point[0] - 0.5) * 2 * Math.PI) /
      Math.max(0.00001, Math.sqrt(1 - (2 * point[1] - 1) ** 2));
    const out = ctx.createImageData(w, h),
      radius = w * 0.48;
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++) {
        const nx = (x + 0.5 - w / 2) / radius,
          ny = (h / 2 - y - 0.5) / radius;
        const zz = 1 - nx * nx - ny * ny;
        if (zz < 0) continue;
        const nz = Math.sqrt(zz);
        const latitude = Math.asin(
          Math.max(-1, Math.min(1, ny * Math.cos(lat) + nz * Math.sin(lat))),
        );
        const longitude =
          lon + Math.atan2(nx, nz * Math.cos(lat) - ny * Math.sin(lat));
        const v = 0.5 - latitude / Math.PI,
          u = (((longitude / (2 * Math.PI) + 0.5) % 1) + 1) % 1;
        const sourceX =
          0.5 + (u - 0.5) * Math.sqrt(Math.max(0, 1 - (2 * v - 1) ** 2));
        const i =
          4 *
          (Math.min(field.height - 1, Math.floor(v * field.height)) *
            field.width +
            Math.min(field.width - 1, Math.floor(sourceX * field.width)));
        const j = 4 * (y * w + x);
        for (let channel = 0; channel < 3; channel++)
          out.data[j + channel] = field.data[i + channel];
        out.data[j + 3] = 255;
      }
    ctx.putImageData(out, 0, 0);
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, 3.5, 0, 2 * Math.PI);
    ctx.stroke();
    canvas!.hidden = false;
  });
  if (canvas)
    void poster
      .decode()
      .then(() => {
        const buffer = document.createElement('canvas');
        buffer.width = poster.naturalWidth;
        buffer.height = poster.naturalHeight;
        const ctx = buffer.getContext('2d');
        if (!ctx) return;
        ctx.drawImage(poster, 0, 0);
        field = ctx.getImageData(0, 0, buffer.width, buffer.height);
        refresh();
      })
      .catch(() => {});
  return (x: number, y: number) => {
    point = [x, y];
    refresh();
  };
}
