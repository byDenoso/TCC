// Measure gzip-compressed bytes of all same-origin HTML/CSS/JS loaded on first visit.
// This conservative superset is not an attribution of individual files as critical.
import {chromium} from 'playwright';
import {gzipSync} from 'node:zlib';
import assert from 'node:assert/strict';

const base=(process.env.BASE_URL??'http://127.0.0.1:4321').replace(/\/$/,'');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,headless:true});
const rows=[];
try {
  for(const viewport of [{width:1440,height:900},{width:390,height:844}]) {
    const context=await browser.newContext({viewport,reducedMotion:'no-preference'});
    const page=await context.newPage(),pending=[],resources=new Map(),failures=[],pageErrors=[];
    page.on('pageerror',error=>pageErrors.push(error.message));
    page.on('response',response=>{
      const request=response.request(),url=new URL(response.url());
      const type=request.resourceType();
      if(url.origin!==new URL(base).origin||!['document','script','stylesheet'].includes(type))return;
      if(response.status()!==200){failures.push({path:url.pathname,error:`HTTP ${response.status()}`});return;}
      pending.push(response.body().then(body=>resources.set(url.pathname,{type,bytes:body.length,gzip:gzipSync(body,{level:6}).length})).catch(error=>failures.push({path:url.pathname,error:String(error)})));
    });
    page.on('requestfailed',request=>{const url=new URL(request.url());if(url.origin===new URL(base).origin&&['document','script','stylesheet'].includes(request.resourceType()))failures.push({path:url.pathname,error:request.failure()?.errorText??'request failed'});});
    await page.goto(`${base}/`,{waitUntil:'load'});
    await page.waitForTimeout(1500);
    await Promise.all(pending);
    assert.deepEqual(failures,[],'loaded resources must be measurable');
    assert.deepEqual(pageErrors,[],'first visit must not raise browser errors');
    const files=[...resources].map(([path,size])=>({path,...size}));
    for(const type of ['document','script','stylesheet'])assert.ok(files.some(file=>file.type===type),`missing ${type} response`);
    const gzip=files.reduce((sum,item)=>sum+item.gzip,0);
    const row={viewport:`${viewport.width}x${viewport.height}`,gzipBytes:gzip,files};rows.push(row);
    if(process.env.ASSERT_BUDGET!=='0')assert.ok(gzip<=300000,`first-visit HTML/CSS/JS: ${gzip} gzip bytes > 300000`);
    await context.close();
  }
  console.log(JSON.stringify({method:'same-origin HTML/CSS/JS responses until load+1.5s, gzip level 6 computed from actual response bodies; viewport emulation, not on-wire transfer',rows}));
} finally {await browser.close();}
