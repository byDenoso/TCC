import { expect, it } from 'vitest';
import chapters from '../../src/data/chapters.json';
import { LESSON_GUIDES } from '../../src/data/lesson-guides';

it('todas as 36 experiências têm orientação e interpretação próprias', () => {
  const ids = chapters.flatMap(ch => ch.sections.map(s => s.id));
  expect(ids).toHaveLength(36);
  expect(Object.keys(LESSON_GUIDES).sort()).toEqual(ids.sort());
  for (const id of ids) {
    const guide = LESSON_GUIDES[id];
    expect(guide.observe.length).toBeGreaterThan(30);
    expect(guide.connect.length).toBeGreaterThan(30);
    expect(guide.try.length).toBeGreaterThan(20);
  }
  expect(new Set(Object.values(LESSON_GUIDES).map(g => g.observe)).size).toBe(36);
});
