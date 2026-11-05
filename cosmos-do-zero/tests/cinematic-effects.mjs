// Independent visual comparisons on a synthetic scene and real WebGPU backend.
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {chromium} from 'playwright';
import sharp from 'sharp';

const server=await createServer({configFile:false,root:process.cwd(),logLevel:'error',server:{host:'127.0.0.1',port:0,strictPort:false}});
await server.listen();const address=server.httpServer.address(),base=`http://127.0.0.1:${address.port}`;
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,headless:true,args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist',...(process.platform==='win32'?['--use-angle=d3d11']:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])]});
try{
 for(const projection of ['perspective','orthographic']){
  const page=await browser.newPage({viewport:{width:320,height:240}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  await page.goto(`${base}/tests/fixtures/cinematic-effects.html?projection=${projection}`);
  await page.waitForFunction(()=>window.__CINEMATIC_FIXTURE,{timeout:30000});
  const backend=await page.evaluate(()=>window.__CINEMATIC_FIXTURE.backend);
  assert.equal(backend,'webgpu','isolated effects require actual WebGPU');
  const no={depthOfField:false,bloom:false,cameraBlur:false,antialias:false};
  const shot=async(options,moving=false,focusZ=0)=>{await page.evaluate(({options,moving,focusZ})=>window.__CINEMATIC_FIXTURE.render(options,moving,focusZ),{options,moving,focusZ});return await sharp(await page.locator('canvas').screenshot()).raw().toBuffer();};
  const diff=(a,b)=>{assert.equal(a.length,b.length);let sum=0;for(let i=0;i<a.length;i++)sum+=Math.abs(a[i]-b[i]);return sum/a.length;};
  const baseline=await shot(no),dof=await shot({...no,depthOfField:true}),glow=await shot({...no,bloom:true}),aa=await shot({...no,antialias:true});
  const nearFocus=await shot({...no,depthOfField:true},false,2),farFocus=await shot({...no,depthOfField:true},false,-4);
  const still=await shot({...no,cameraBlur:true}),moved=await shot(no,true),movedBlur=await shot({...no,cameraBlur:true},true);
  const rows={depthOfField:diff(baseline,dof),focusChange:diff(nearFocus,farFocus),bloom:diff(baseline,glow),smaa:diff(baseline,aa),cameraBlurStationary:diff(baseline,still),cameraBlurMoving:diff(moved,movedBlur)};
  console.log(`CINEMATIC_EFFECTS ${JSON.stringify({projection,backend,meanPixelDelta:rows})}`);
  assert.ok(rows.depthOfField>.01,'depth of field changes the image');
  assert.ok(rows.focusChange>.01,'changing focus changes the image');
  assert.ok(rows.bloom>.01,'bloom changes the image');
  assert.ok(rows.smaa>.001,'SMAA changes the image');
  assert.ok(rows.cameraBlurStationary<.05,'stationary camera is not blurred');
  assert.ok(rows.cameraBlurMoving>.01,'moving camera is blurred');
  const hdr=await page.evaluate(()=>window.__CINEMATIC_FIXTURE.readHdr());
  console.log(`CINEMATIC_HDR ${JSON.stringify({projection,backend,...hdr})}`);
  assert.ok(hdr.maximum>1,'linear render target retains values above one before tone mapping');
  assert.deepEqual(errors,[]);
  await page.evaluate(()=>window.__CINEMATIC_FIXTURE.dispose());await page.close();
 }
}finally{await browser.close();await server.close();}
