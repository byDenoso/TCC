/** Subconjunto leve enviado ao navegador (sem o texto dos capítulos). */
import planetsJson from './planets.json';
import erasJson from './eras.json';
import questionsJson from './questions.json';
import termsJson from './terms.json';
import type { Era, Planet, Question, Term } from '../types';
export const planets = planetsJson as Planet[];
export const eras = erasJson as Era[];
export const questions = questionsJson as Question[];
export const terms = termsJson as Term[];
