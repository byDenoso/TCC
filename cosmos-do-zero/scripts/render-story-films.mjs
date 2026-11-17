import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import sharp from 'sharp';
import { STORIES, renderStory, storyProgress, storyComposition } from '../src/lib/story-scenes.ts';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.join(root,'public/media/stories');
const fps=24, duration=20;
const arg=process.argv[2];
const ids=arg?[arg]:Object.keys(STORIES);
const time=s=>`00:${s.toFixed(3).padStart(6,'0')}`;
const wrap=(s,n)=>{const lines=[];let current='';for(const word of s.split(' ')){if((current+' '+word).trim().length>n){lines.push(current);current=word;}else current=(current+' '+word).trim();}lines.push(current);return lines.join('\n');};
for(const id of ids){
 const story=STORIES[id], images=new Set();
 for(const p of [0,.10,.22,.32,.4,.50,.72,.82,1])for(const {src} of storyComposition(id,p).planes)images.add(src);
 if(id==='sistema-solar')images.add('/media/stories/studio-field.webp');
 const encoded=new Map();
 for(const src of images){
  const input=sharp(path.join(root,'public',src)).resize({width:1280,height:900,fit:'inside',withoutEnlargement:true});
  const alpha=(await input.metadata()).hasAlpha;
  const buffer=alpha?await input.png().toBuffer():await input.jpeg({quality:88}).toBuffer();
  encoded.set(src,'data:image/'+(alpha?'png':'jpeg')+';base64,'+buffer.toString('base64'));
 }
 const imageSrc=src=>{if(!encoded.has(src))throw Error('Plate missing: '+src);return encoded.get(src);};
 const frame=p=>Buffer.from(renderStory(id,p,'film',imageSrc).replace('<svg ','<svg width="1280" height="720" ').replace(/ href="data:[^"]+"/g,''));
 const target=path.join(out,id+'.mp4'),temp=target+'.tmp';
 const ff=spawn('ffmpeg',['-y','-hide_banner','-loglevel','error','-f','rawvideo','-pixel_format','rgb24','-video_size','1280x720','-framerate',String(fps),'-i','pipe:0','-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','26','-g',String(fps*3),'-pix_fmt','yuv420p','-movflags','+faststart','-f','mp4',temp],{stdio:['pipe','ignore','pipe']});
 let error='';ff.stderr.on('data',d=>error+=d);const done=once(ff,'close');
 let previous, pixels;
 for(let i=0;i<duration*fps;i++){
  const p=storyProgress(i/fps);
  if(p!==previous){pixels=await sharp(frame(p)).removeAlpha().raw().toBuffer();previous=p;}
  if(!ff.stdin.write(pixels))await once(ff.stdin,'drain');
 }
 ff.stdin.end();const [code]=await done;if(code)throw Error(error);await fs.rename(temp,target);
 await sharp(frame(0)).webp({quality:87}).toFile(path.join(out,id+'.webp'));
 const starts=story.phases.map(s=>s.at===0?0:3+s.at*12);
 const captions='WEBVTT\n\n'+story.phases.map((s,i)=>`${time(starts[i])} --> ${time(starts[i+1]===undefined?duration:starts[i+1]-.001)}\n${wrap(s.say,75)}\n`).join('\n');
 await fs.writeFile(path.join(out,id+'.vtt'),captions);
 console.log(id, (await fs.stat(target)).size);
}
if(!arg)await fs.writeFile(path.join(out,'provenance.json'),JSON.stringify({source:'src/lib/story-scenes.ts',artwork:'scripts/prepare-story-plates.py',duration,fps,dimensions:[1280,720],captions:'VTT em português',credits:{earth:'Retrato planetário do estúdio do Cosmos do Zero; mapas e créditos em assets/source/solar-materials.',galaxies:'Ilustrações de Via Láctea, teia, disco e halo do acervo public/renders. O render conceitual não mede posições de galáxias.',orion:'NASA, ESA, M. Robberto (STScI/ESA) and the Hubble Space Telescope Orion Treasury Project Team, CC BY 4.0; detalhe recortado. https://esahubble.org/images/heic0601a/',atmosphere:'Atmosfera: fotografia da NASA, Estação Espacial Internacional. Fonte na página de créditos.',remnants:'Ilustração procedural original; remanescentes em escalas independentes.'},ids:Object.keys(STORIES)},null,2)+'\n');
