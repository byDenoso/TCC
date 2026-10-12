import terra from '../assets/planets/terra.webp';
import mercurio from '../assets/planets/mercurio.webp';
import venus from '../assets/planets/venus.webp';
import marte from '../assets/planets/marte.webp';
import jupiter from '../assets/planets/jupiter.webp';
import saturno from '../assets/planets/saturno.webp';
import saturnoGlobo from '../assets/planets/saturno-globo.webp';
import urano from '../assets/planets/urano.webp';
import netuno from '../assets/planets/netuno.webp';
import andromeda from '../assets/photos/andromeda-wise.webp';
import carina from '../assets/photos/carina-cosmic-cliffs.webp';
import iss from '../assets/photos/iss-sunrise.webp';
import type { PlanetId } from '../types';

/** Ilustração artística de cada planeta (RGBA, fundo transparente). Saturno inclui os anéis. */
export const planetArt: Record<PlanetId, ImageMetadata> = { mercurio, venus, terra, marte, jupiter, saturno, urano, netuno };
/** Versão sem anéis, usada onde a escala é o raio equatorial (comparador e régua de tamanhos). */
export const planetGlobe: Record<PlanetId, ImageMetadata> = { mercurio, venus, terra, marte, jupiter, saturno: saturnoGlobo, urano, netuno };
export const photos = { 'andromeda-wise': andromeda, 'carina-cosmic-cliffs': carina, 'iss-sunrise': iss } as const;
