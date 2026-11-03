import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { STORIES, sampleStory, renderStory, storyProgress } from '../src/lib/story-scenes.ts';
const sharp=createRequire(import.meta.url)('sharp');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),out=path.join(root,'public/media/stories');
const duration=20,fps=24;await fs.mkdir(out,{recursive:true});
const esc=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;');
const wrap=(s,n=100)=>{const lines=[];let current='';for(const word of s.split(' ')){if((current+' '+word).trim().length>n){lines.push(current);current=word;}else current=(current+' '+word).trim();}if(current)lines.push(current);return lines;};
function frame(id,seconds){
 const p=storyProgress(seconds),phase=sampleStory(id,p).phase,story=STORIES[id];
 const scene=renderStory(id,p,'film').replace('<svg ','<svg x="160" y="60" width="960" height="540" ');
 const stages=story.phases.map((s,i)=>`<rect x="${64+i*388}" y="16" width="372" height="36" rx="8" fill="${phase===i?'#154660':'#08233d'}" stroke="${phase===i?'#74dceb':'#254661'}"/><text x="${82+i*388}" y="40" font-family="Arial" font-size="17" fill="#eef6ff">${i+1}. ${esc(s.label)}</text>`).join('');
 const caption=wrap(story.phases[phase].say).map((s,i)=>`<text x="64" y="${620+i*28}" font-family="Arial" font-size="23" fill="#eef6ff">${esc(s)}</text>`).join('');
 return `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#031226"/>${stages}${scene}${caption}<text x="64" y="700" font-family="Arial" font-size="12" fill="#aec7db">COSMOS DO ZERO · Ilustração para aprender · ${esc(story.limit)}</text></svg>`;
}
const time=s=>`00:${s.toFixed(3).padStart(6,'0')}`;
for(const id of Object.keys(STORIES)){
 const target=path.join(out,id+'.mp4'),temporary=target+'.tmp';
 const film=spawn('ffmpeg',['-y','-hide_banner','-loglevel','error','-f','image2pipe','-vcodec','png','-r',String(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','-f','mp4',temporary],{stdio:['pipe','ignore','pipe']});
 let error='';film.stderr.on('data',d=>error+=d);const done=once(film,'close');
 for(let i=0;i<duration*fps;i++){const png=await sharp(Buffer.from(frame(id,i/fps))).png({compressionLevel:1}).toBuffer();if(!film.stdin.write(png))await once(film.stdin,'drain');}
 film.stdin.end();const [code]=await done;if(code)throw Error(error);await fs.rename(temporary,target);
 await sharp(Buffer.from(renderStory(id,.5,'poster'))).resize(960,540).webp({quality:85}).toFile(path.join(out,id+'.webp'));
 const story=STORIES[id],starts=story.phases.map(s=>s.at===0?0:3+s.at*12);
 const vtt='WEBVTT\n\n'+story.phases.map((s,i)=>`${time(starts[i])} --> ${time(starts[i+1]??duration)}\n${wrap(s.say,75).join('\n')}\n`).join('\n');
 await fs.writeFile(path.join(out,id+'.vtt'),vtt);
 console.log(`${id}: 20s, 480 quadros; ${Math.round((await fs.stat(path.join(out,id+'.mp4'))).size/1024)} KiB`);
}
await fs.writeFile(path.join(out,'provenance.json'),JSON.stringify({source:'src/lib/story-scenes.ts',duration,fps,dimensions:[1280,720],models:'Ilustrações educativas; limites descritos em cada cena',references:['https://nssdc.gsfc.nasa.gov/planetary/factsheet/mercuryfact.html','https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html','https://science.nasa.gov/asset/webb/what-is-cosmological-redshift/'],ids:Object.keys(STORIES)},null,2));
