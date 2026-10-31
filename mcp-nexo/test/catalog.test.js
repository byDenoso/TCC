import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createHash } from 'node:crypto';
const mod = await import('../lib/catalog.js').catch(() => ({}));
const runtime = { contract:'MCP_RUNTIME_CONTRACT_V1', schema_version:'4.0', revision:'fixture-1', resources:{agents:'fixture-agents',writer:'fixture-writer',tower:'fixture-tower'}, capabilities:[{id:'camb.portable',state:'VERIFIED_LINUX_SCOPED',scope:'Linux only',validation:{remote_mcp_execution:'NOT_DEPLOYED'}},{id:'remote.science.dispatch',state:'NOT_CERTIFIED'},{id:'tower.read',state:'VERIFIED_INTERACTIVE'}] };
const sources = [{id:'runtime',fileId:'fixture-runtime',format:'runtime'},{id:'datasets',fileId:'fixture-datasets',format:'datasets_csv'}];
const csv = 'resource_id,name,family,adapter,integration_status,validation_state,sha256\nasset-1,"file, one",CMB,CobayaExactAdapter,BLOCKED,UNINSPECTED,\nasset-2,file2,BAO,BAOAdapter,INTEGRATED,SCOPED_PASS,abc\n';
const reader = async s => ({text:s.id==='runtime'?JSON.stringify(runtime):csv,modifiedTime:'2026-10-30T00:00:00Z',version:'1'});
function service(){ assert.equal(typeof mod.createCatalogService,'function','catalog discovery must be implemented'); return mod.createCatalogService({sources,readSource:reader}); }
test('catalog distinguishes recorded validation from remote execution', async()=>{const s=service();const r=await s.get({id:'runtime:capability:camb.portable'});assert.equal(r.readiness.remoteExecution,false);assert.equal(r.record.state,'VERIFIED_LINUX_SCOPED');assert.equal(r.readiness.catalogued,true);assert.equal(r.provenance.sha256,createHash('sha256').update(JSON.stringify(runtime)).digest('hex'));});
test('typed CSV preserves quoted names and dataset contract',async()=>{const r=await service().search({category:'dataset'});assert.equal(r.items.length,2);assert.equal(r.items[0].label,'file, one');assert.equal(r.items[0].state,'BLOCKED');});
test('adapters are discoverable but never promoted from dataset metadata',async()=>{const r=await service().search({category:'adapter'});assert.equal(r.items.length,2);for(const x of r.items)assert.equal(x.remoteExecution,false);});
test('references expose skills and Writer/Tower routes, not new services',async()=>{const s=service();assert.equal((await s.search({category:'skill'})).items.length,1);assert.equal((await s.search({category:'writer'})).items.length,1);assert.ok((await s.search({category:'tower'})).items.length>=1);});
test('pagination is stable, bounded, and tied to query and source hash',async()=>{const s=service();const a=await s.search({limit:2});assert.equal(a.items.length,2);assert.ok(a.nextCursor);const b=await s.search({limit:2,cursor:a.nextCursor});assert.ok(!a.items.some(x=>b.items.some(y=>x.id===y.id)));await assert.rejects(s.search({q:'other',cursor:a.nextCursor}),/cursor/i);await assert.rejects(s.search({limit:101}),/limit/i);await assert.rejects(s.search({cursor:'bad'}),/cursor/i);});
test('source errors are explicit and do not leak upstream secrets or pretend empty',async()=>{const s=mod.createCatalogService({sources,readSource:async()=>{throw Error('Bearer SECRET');}});const r=await s.status();assert.equal(r.state,'BLOCKED');assert.equal(r.sources[0].state,'UNAVAILABLE');assert.ok(!JSON.stringify(r).includes('SECRET'));});
test('hash mismatch fails closed',async()=>{const s=mod.createCatalogService({sources:[{...sources[0],sha256:'0'.repeat(64)}],readSource:reader});assert.equal((await s.status()).sources[0].state,'HASH_MISMATCH');});
test('unknown ID is rejected, no arbitrary file fetch',async()=>{await assert.rejects(service().get({id:'../../secret'}),/not_found/);});
test('unsupported source format is explicit',async()=>{const s=mod.createCatalogService({sources:[{id:'x',fileId:'fixture',format:'invented'}],readSource:reader});assert.equal((await s.status()).sources[0].state,'UNSUPPORTED_FORMAT');});
test('generic index records remain catalogued without inferred validation',async()=>{const s=mod.createCatalogService({sources:[{id:'index',fileId:'fixture',format:'index_json'}],readSource:async()=>({text:JSON.stringify({resources:[{id:'r',name:'recipe',category:'recipe',status:'READY'}]})})});const r=await s.get({id:'index:recipe:r'});assert.equal(r.record.status,'READY');assert.equal(r.readiness.remoteExecution,false);});
test('malformed CSV and duplicate identifiers fail instead of truncating inventory',async()=>{const s=mod.createCatalogService({sources:[sources[1]],readSource:async()=>({text:'resource_id,name\nx,"unclosed'})});assert.equal((await s.status()).state,'BLOCKED');});
test('real LOOKUP sheet schema decodes resource_json without promoting metadata',async()=>{
 const s=mod.createCatalogService({sources:[{id:'lookup',fileId:'fixture',format:'lookup_sheet'}],readSource:async()=>({text:JSON.stringify({values:[['drive_file_id','name_category_aliases','canonical_path','resource_json'],['abc','Nome: test','path',JSON.stringify({resource_id:'drive:abc',drive_file_id:'abc',name:'test',category:'04_DATASETS',validation_state:'CONTENT_UNINSPECTED'})]]})})});
 const r=await s.get({id:'lookup:dataset:drive:abc'});assert.equal(r.record.validation_state,'CONTENT_UNINSPECTED');assert.equal(r.readiness.remoteExecution,false);
});
test('lookup taxonomy maps documented likelihood and Tower categories, preserves source category',async()=>{
 const records=[{resource_id:'a',drive_file_id:'a',category:'05_LIKELIHOODS',name:'release'},{resource_id:'b',drive_file_id:'b',category:'09_TOWERS_AND_SNAPSHOTS',name:'snapshot'}];
 const s=mod.createCatalogService({sources:[{id:'l',fileId:'x',format:'lookup_sheet'}],readSource:async()=>({text:JSON.stringify({values:[['drive_file_id','name_category_aliases','canonical_path','resource_json'],...records.map(r=>[r.drive_file_id,'','',JSON.stringify(r)])]})})});
 assert.equal((await s.search({category:'likelihood'})).total,1);assert.equal((await s.get({id:'l:tower:b'})).record.category,'09_TOWERS_AND_SNAPSHOTS');
});
test('reject non-string and oversized IDs instead of returning uncallable records',async()=>{
 for(const id of [42,'x'.repeat(1100)]) {const s=mod.createCatalogService({sources:[sources[0]],readSource:async()=>({text:JSON.stringify({...runtime,capabilities:[{id}]})})});assert.equal((await s.status()).state,'BLOCKED');}
});
test('concurrent readers share one in-flight snapshot',async()=>{
 let calls=0;const s=mod.createCatalogService({sources:[sources[0]],readSource:async()=>{calls++;await new Promise(r=>setTimeout(r,10));return reader(sources[0]);}});
 await Promise.all([s.status(),s.search({}),s.status()]);assert.equal(calls,1);
});
test('search status and revision belong to one snapshot across cache expiry',async()=>{
 const now=Date.now;let clocks=0,calls=0;Date.now=()=>clocks++===0?0:30001;
 try{const s=mod.createCatalogService({sources:[sources[0]],readSource:async()=>{if(++calls>1)throw Error('upstream');return reader(sources[0]);}});const r=await s.search({});assert.ok(r.items.length);assert.equal(r.sourceStatus,'AVAILABLE');assert.equal(calls,1);}finally{Date.now=now;}
});
