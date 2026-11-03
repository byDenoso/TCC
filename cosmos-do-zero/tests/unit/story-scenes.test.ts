import { describe, expect, it } from 'vitest';
import { STORIES, renderStory, sampleStory, storyProgress } from '../../src/lib/story-scenes';
const ids=['galaxias-e-nebulosas','origem-do-universo','misterios-do-cosmos','vida-das-estrelas','sistema-solar','terra-e-atmosfera'];

describe('histórias visuais da escola', () => {
  it('oferece as seis aulas com três momentos e texto para aprender sem som', () => {
    expect(Object.keys(STORIES)).toEqual(ids);
    for (const story of Object.values(STORIES)) {
      expect(story.phases).toHaveLength(3);
      expect(story.phases.every(p => p.label.length > 3 && p.say.length > 25)).toBe(true);
      expect(story.limit.length).toBeGreaterThan(25);
    }
  });
  it('a expansão duplica o comprimento de onda e preserva o tamanho das galáxias', () => {
    const before=sampleStory('origem-do-universo',0),after=sampleStory('origem-do-universo',1);
    expect(after.scale/before.scale).toBeCloseTo(2);
    expect(after.wavelength/before.wavelength).toBeCloseTo(2);
    expect(before.galaxyRadius).toBe(after.galaxyRadius);
    expect(after.redshift).toBeCloseTo(1);
  });
  it('as órbitas externas levam mais tempo conforme a terceira lei de Kepler', () => {
    const frame=sampleStory('sistema-solar',.5);
    expect(frame.periods[1]).toBeCloseTo(1);
    expect(frame.periods[0]).toBeCloseTo(.241,2);
    expect(frame.periods[2]).toBeCloseTo(1.88,2);
    for(let i=0;i<frame.periods.length;i++)expect(frame.periods[i]**2).toBeCloseTo(frame.axes[i]**3);
    expect(frame.periods[0]).toBeLessThan(frame.periods[1]);
    expect(frame.periods[2]).toBeGreaterThan(frame.periods[1]);
  });
  it('a leitura de altitude fica entre o solo e 120 km e sobe continuamente', () => {
    const heights=Array.from({length:21},(_,i)=>sampleStory('terra-e-atmosfera',i/20).altitude);
    expect(heights[0]).toBe(0);expect(heights.at(-1)).toBe(120);
    expect(heights.every((h,i)=>i===0||h>=heights[i-1])).toBe(true);
  });
  it('deixa tempo inicial e final para ler e limita a régua ao intervalo da história', () => {
    expect(storyProgress(-1)).toBe(0);expect(storyProgress(3)).toBe(0);
    expect(storyProgress(15)).toBe(1);expect(storyProgress(21)).toBe(1);
  });
  it('seleciona exatamente a etapa pedida quando a régua converte tempo em progresso', () => {
    for(const [id,story] of Object.entries(STORIES))story.phases.forEach((phase,i)=>{
      const seconds=i===0?0:3+phase.at*12;
      expect(sampleStory(id,storyProgress(seconds)).phase,`${id}: ${phase.label}`).toBe(i);
    });
  });
  it('renderiza diagramas determinísticos sem números inválidos e com IDs locais', () => {
    for(const id of ids)for(const p of [0,.5,1]){
      const svg=renderStory(id,p,'a');
      expect(svg).toContain('<svg');expect(svg).toContain('viewBox="0 0 960 540"');
      expect(svg).not.toMatch(/NaN|Infinity|undefined/);
      expect(renderStory(id,p,'a')).toBe(svg);
      const ids=[...svg.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
      const other=renderStory(id,p,'b');
      for(const value of ids)expect(other).not.toContain(`id="${value}"`);
    }
  });
});
