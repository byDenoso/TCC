import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { STORIES } from '../../src/lib/story-scenes';

describe('legendas das seis explicações',()=>{
 for(const id of Object.keys(STORIES))it(`${id}: um único momento legendado em cada transição`,()=>{
  const vtt=readFileSync(new URL(`../../public/media/stories/${id}.vtt`,import.meta.url),'utf8');
  const cues=[...vtt.matchAll(/00:(\d{2}\.\d{3}) --> 00:(\d{2}\.\d{3})/g)].map(m=>({start:Number(m[1]),end:Number(m[2])}));
  expect(cues).toHaveLength(3);
  expect(cues[0].start).toBe(0);
  expect(cues[2].end).toBe(20);
  for(let i=0;i<cues.length;i++){
   expect(cues[i].end).toBeGreaterThan(cues[i].start);
   if(i)expect(cues[i-1].end,`duas legendas no mesmo instante: ${cues[i].start}s`).toBeLessThan(cues[i].start);
  }
 });
});
