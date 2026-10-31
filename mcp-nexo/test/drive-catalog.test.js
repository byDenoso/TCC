import assert from 'node:assert/strict';
import {test} from 'node:test';
const mod=await import('../lib/drive-catalog.js').catch(()=>({}));
function reader(fetchImpl,token='test-only'){assert.equal(typeof mod.createDriveReader,'function');return mod.createDriveReader({token,fetchImpl});}
const meta={mimeType:'application/json',modifiedTime:'2026-01-01T00:00:00Z',version:'1'};
test('Drive loader uses GET only, fixed Google origin and Bearer outside query',async()=>{const calls=[];const read=reader(async(url,opts)=>{calls.push(url);assert.equal(new URL(url).origin,'https://www.googleapis.com');assert.equal(opts.method,'GET');assert.equal(opts.headers.authorization,'Bearer test-only');return url.includes('alt=media')?new Response('{"a":1}'):Response.json(meta);});assert.equal((await read({fileId:'test_file'})).text,'{"a":1}');assert.equal(calls.length,3);});
test('Drive loader rejects arbitrary URLs and missing auth before fetch',async()=>{let count=0;const f=async()=>{count++;};await assert.rejects(reader(f)({fileId:'https://evil.test'}),/CONFIG/);await assert.rejects(reader(f,'')({fileId:'abc'}),/CONFIG/);assert.equal(count,0);});
test('Drive loader refuses changed versions and redirects',async()=>{let n=0;const read=reader(async(url)=>url.includes('alt=media')?new Response('{}'):Response.json({...meta,version:String(++n)}));await assert.rejects(read({fileId:'abc'}),/SOURCE_CHANGED/);await assert.rejects(reader(async()=>new Response('',{status:302}))({fileId:'abc'}),/UNAVAILABLE/);});
test('Drive loader exports native Docs but does not silently export spreadsheets',async()=>{const read=reader(async url=>url.includes('/export?')?new Response('text'):Response.json({...meta,mimeType:'application/vnd.google-apps.document'}));assert.equal((await read({fileId:'abc'})).text,'text');await assert.rejects(reader(async()=>Response.json({...meta,mimeType:'application/vnd.google-apps.spreadsheet'}))({fileId:'abc'}),/UNSUPPORTED/);});
test('Drive loader caps response bytes',async()=>{await assert.rejects(reader(async url=>url.includes('alt=media')?new Response('x',{headers:{'content-length':'999999999'}}):Response.json(meta))({fileId:'abc'}),/SOURCE_TOO_LARGE/);});
test('LOOKUP uses bounded Sheets GET, same file and version readback',async()=>{
 const read=reader(async url=>url.includes('/v4/spreadsheets/')?Response.json({values:[['drive_file_id','name_category_aliases','canonical_path','resource_json']]}):Response.json({...meta,mimeType:'application/vnd.google-apps.spreadsheet'}));
 assert.ok(JSON.parse((await read({fileId:'abc',format:'lookup_sheet'})).text).values);
});
test('invalid UTF-8 is rejected rather than changing bytes before hashing',async()=>{
 await assert.rejects(reader(async url=>url.includes('alt=media')?new Response(new Uint8Array([255])):Response.json(meta))({fileId:'abc'}));
});
test('LOOKUP reads complete columns rather than silently omitting sparse tail rows',async()=>{
 let range;
 const read=reader(async url=>{if(url.includes('sheets.googleapis.com')){range=decodeURIComponent(new URL(url).pathname.split('/values/')[1]);return Response.json({values:[['drive_file_id','name_category_aliases','canonical_path','resource_json']]});}return Response.json({...meta,mimeType:'application/vnd.google-apps.spreadsheet'});});
 await read({fileId:'abc',format:'lookup_sheet'});assert.equal(range,'LOOKUP!A:D');
});
