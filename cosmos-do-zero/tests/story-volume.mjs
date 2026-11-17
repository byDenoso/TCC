import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import sharp from 'sharp';

const base=process.env.BASE_URL||'http://127.0.0.1:4173';
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH,
  args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const ids=['galaxias-e-nebulosas','origem-do-universo','misterios-do-cosmos','vida-das-estrelas','sistema-solar','terra-e-atmosfera'];
try {
  for (const id of ids) {
    const page=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce',hasTouch:true});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error' && /shader|link_program|uniform|GL_INVALID/i.test(m.text()))errors.push(m.text());});
    await page.goto(base+'/capitulos/'+id+'/#resumo',{waitUntil:'domcontentloaded'});
    const root=page.locator('[data-story]'), controls=root.locator('[data-story-volume]');
    await root.locator('[data-story-phase="0"]').click();
    await root.getByRole('button',{name:'Explorar em 3D'}).click();
    await root.getByRole('button',{name:'Fechar 3D'}).waitFor({timeout:60000});
    const canvas=controls.locator('canvas');
    for(let i=0;i<3;i++){
      await root.locator('[data-story-phase="'+i+'"]').click();
      await page.waitForFunction(([id,i])=>document.querySelector('[data-story="'+id+'"]').dataset.storyPhase===String(i),[id,i]);
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      const image=await canvas.screenshot();
      const stats=await sharp(image).stats();
      assert.ok(stats.channels.some(c=>c.stdev>5 && c.max-c.min>70), id+' fase '+i+' precisa conter geometria visível');
      if(process.env.ATLAS_FRAMES)await sharp(image).png().toFile(process.env.ATLAS_FRAMES+'/'+id+'-'+i+'.png');
    }
    await controls.getByRole('button',{name:'Girar vista'}).click();
    await canvas.focus();await canvas.press('ArrowLeft');
    await root.getByRole('button',{name:'Fechar 3D'}).click();
    assert.ok(await canvas.isHidden());
    assert.deepEqual(errors,[]);
    console.log(id+' · três fases, câmera, retorno 2D');
    await page.close();
  }
}finally {await browser.close();}
