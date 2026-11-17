import sharp from 'sharp';
import { fileURLToPath } from 'node:url';
import { cmbMapPixels } from '../src/lib/cmb-map.ts';

const width = 480;
const height = 240;
const target = fileURLToPath(new URL('../public/posters/cmb-field.webp', import.meta.url));
await sharp(cmbMapPixels(width, height), { raw: { width, height, channels: 4 } })
  .webp({ quality: 90, smartSubsample: true })
  .toFile(target);
