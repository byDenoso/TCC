import { createHash } from 'node:crypto';

export const CATEGORIES = Object.freeze(['runtime','solver','adapter','likelihood','dataset','recipe','skill','contract','tower','writer','resource','capability']);
const sha = value => createHash('sha256').update(value).digest('hex');
const MAX_BYTES = 64 * 1024 * 1024;
const MAX_RECORDS = 50000;
const cleanString = x => typeof x === 'string' ? x : '';
function category(id) {
  if (/writer|append/.test(id)) return 'writer';
  if (/tower/.test(id)) return 'tower';
  if (/camb|cosmorec|solver/.test(id)) return 'solver';
  if (/science.local|runtime/.test(id)) return 'runtime';
  return 'capability';
}
// Strict RFC4180 subset: comma, quoted fields, escaped quotes, CRLF and embedded newlines.
function csvRows(text) {
  const rows=[]; let row=[], field='', quoted=false, closed=false;
  for(let i=0;i<text.length;i++) {
    const c=text[i];
    if(quoted) { if(c==='"') { if(text[i+1]==='"'){field+='"';i++;}else{quoted=false;closed=true;} }else field+=c; continue; }
    if(c==='"') { if(field || closed) throw Error('INVALID_SOURCE');quoted=true;continue; }
    if(c===',' || c==='\n' || c==='\r') { row.push(field);field='';closed=false;if(c!==','){if(c==='\r'&&text[i+1]==='\n')i++;rows.push(row);row=[];}continue; }
    if(closed) throw Error('INVALID_SOURCE');field+=c;
  }
  if(quoted) throw Error('INVALID_SOURCE');
  if(field || row.length || closed){row.push(field);rows.push(row);}
  const headers=rows.shift();
  if(!headers?.includes('resource_id') || new Set(headers).size!==headers.length) throw Error('INVALID_SOURCE');
  return rows.filter(r=>r.some(Boolean)).map(r=>{if(r.length!==headers.length)throw Error('INVALID_SOURCE');return Object.fromEntries(headers.map((h,i)=>[h,r[i]]));});
}
function parse(source,text) {
  const records=[];
  function add(id,kind,label,record) {
    if(typeof id!=='string' || !id || id.length>900 || (typeof label==='string' && label.length>4096) || !CATEGORIES.includes(kind)) throw Error('INVALID_SOURCE');
    records.push({id:`${source.id}:${kind}:${id}`,category:kind,label:cleanString(label)||id,record});
  }
  if(source.format==='runtime') {
    const data=JSON.parse(text);
    if(data.contract!=='MCP_RUNTIME_CONTRACT_V1' || !Array.isArray(data.capabilities))throw Error('INVALID_SOURCE');
    for(const c of data.capabilities) {
      // Stable capability IDs keep their namespace even if their display category evolves.
      add(c.id,'capability',c.id,c); records.at(-1).category=category(c.id);
    }
    add('runtime-contract','contract',data.contract,{revision:data.revision,schema_version:data.schema_version,status:data.status});
    for(const [name,ref] of Object.entries(data.resources||{})) {
      const kind=['agents','closed_loop'].includes(name)?'skill':name==='writer'?'writer':name==='tower'?'tower':'resource';
      add(name,kind,name,{reference:ref,state:'CATALOGUED_REFERENCE'});
    }
  } else if(source.format==='datasets_csv') {
    const adapters=new Map();
    for(const r of csvRows(text)) {
      add(r.resource_id,'dataset',r.name,r);
      if(r.adapter){if(!adapters.has(r.adapter))adapters.set(r.adapter,[]);adapters.get(r.adapter).push({resource_id:r.resource_id,family:r.family,integration_status:r.integration_status,validation_state:r.validation_state,scope:r.integration_scope});}
    }
    for(const [name,bindings] of adapters)add(name,'adapter',name,{state:'CATALOGUED_BINDINGS',bindings});
  } else if(source.format==='lookup_sheet') {
    const rows=JSON.parse(text).values;
    if(!Array.isArray(rows)||JSON.stringify(rows[0])!==JSON.stringify(['drive_file_id','name_category_aliases','canonical_path','resource_json']))throw Error('INVALID_SOURCE');
    if(rows.length>MAX_RECORDS+1)throw Error('SOURCE_TOO_LARGE');
    for(const row of rows.slice(1)){
      if(!row.some(Boolean))continue;
      const r=JSON.parse(row[3]);
      if(r.drive_file_id!==row[0]||!r.resource_id)throw Error('INVALID_SOURCE');
      const mapped={'04_DATASETS':'dataset','01_SKILLS':'skill','03_CONTRACTS':'contract','05_LIKELIHOODS':'likelihood','09_TOWERS_AND_SNAPSHOTS':'tower'};
      const kind=CATEGORIES.includes(r.category)?r.category:mapped[r.category]||'resource';
      add(r.resource_id,kind,r.name,r);
    }
  } else if(source.format==='index_json') {
    const data=JSON.parse(text);const rows=Array.isArray(data)?data:data.resources??data.entries??data.items;
    if(!Array.isArray(rows))throw Error('INVALID_SOURCE');
    for(const r of rows){const id=r.id??r.resource_id??r.file_id;const kind=CATEGORIES.includes(r.category)?r.category:'resource';add(id,kind,r.name??r.title,r);}
  } else throw Error('UNSUPPORTED_FORMAT');
  if(records.length>MAX_RECORDS || new Set(records.map(r=>r.id)).size!==records.length)throw Error('INVALID_SOURCE');
  return records;
}

export function createCatalogService({sources=[],readSource}) {
  if(!Array.isArray(sources)||sources.length>32||new Set(sources.map(s=>s.id)).size!==sources.length)throw Error('INVALID_CONFIG');
  for(const s of sources)if(!/^[a-zA-Z0-9_-]{1,80}$/.test(s.id)||!s.fileId)throw Error('INVALID_CONFIG');
  let cached;let until=0;let pending;
  async function buildSnapshot() {
    const records=[];const sourceStates=[];
    for(const source of sources){
      try{
        const loaded=await readSource(source);const text=loaded.text;
        if(typeof text!=='string'||Buffer.byteLength(text)>MAX_BYTES)throw Error('SOURCE_TOO_LARGE');
        const digest=sha(text);
        if(source.sha256 && source.sha256!==digest)throw Error('HASH_MISMATCH');
        const parsed=parse(source,text.replace(/^\uFEFF/,''));
        const provenance={source:source.id,fileId:source.fileId,sha256:digest,modifiedTime:loaded.modifiedTime??null,version:loaded.version??null,readAt:new Date().toISOString(),hashMeaning:'SHA256 of catalog bytes read, not proof of referenced payload integrity'};
        for(const r of parsed)records.push({...r,provenance,readiness:{catalogued:true,recordedState:r.record.state??r.record.integration_status??r.record.status??r.record.validation_state??'UNKNOWN',remoteExecution:false,reason:'Discovery only; no execution backend or grant is implied'}});
        sourceStates.push({id:source.id,format:source.format,state:'READ',records:parsed.length,provenance});
      }catch(e){const known=['UNSUPPORTED_FORMAT','HASH_MISMATCH','INVALID_SOURCE','SOURCE_TOO_LARGE','SOURCE_CHANGED'];sourceStates.push({id:source.id,format:source.format,state:known.includes(e.message)?e.message:'UNAVAILABLE'});}
    }
    records.sort((a,b)=>a.id.localeCompare(b.id,'en'));
    const revision=sha(JSON.stringify(sourceStates.map(s=>[s.id,s.state,s.provenance?.sha256])));
    cached={records,sourceStates,revision};until=Date.now()+30000;return cached;
  }
  async function snapshot(){
    if(cached && Date.now()<until)return cached;
    if(!pending)pending=buildSnapshot().finally(()=>{pending=undefined;});
    return pending;
  }
  function stateOf(s){const ok=s.sourceStates.filter(x=>x.state==='READ').length;return !sources.length?'NOT_CONFIGURED':ok===sources.length?'AVAILABLE':ok?'PARTIAL':'BLOCKED';}
  async function status(){const s=await snapshot();return {state:stateOf(s),revision:s.revision,sources:s.sourceStates,total:s.records.length,remoteExecution:false};}
  async function search({q='',category:kind,limit=25,cursor}={}) {
    if(!Number.isSafeInteger(limit)||limit<1||limit>100)throw Error('invalid limit');
    if(typeof q!=='string'||q.length>200||kind&&!CATEGORIES.includes(kind))throw Error('invalid query');
    const s=await snapshot();const query=sha(JSON.stringify([q,kind??null,limit]));let offset=0;
    if(cursor){try{if(typeof cursor!=='string'||cursor.length>1024)throw Error();const c=JSON.parse(Buffer.from(cursor,'base64url').toString());if(c.query!==query||c.revision!==s.revision||!Number.isSafeInteger(c.offset)||c.offset<0)throw Error();offset=c.offset;}catch{throw Error('invalid or stale cursor');}}
    const found=s.records.filter(r=>(!kind||r.category===kind)&&(!q||JSON.stringify([r.id,r.label,r.record]).toLowerCase().includes(q.toLowerCase())));
    if(offset>found.length)throw Error('invalid cursor offset');
    const items=found.slice(offset,offset+limit).map(r=>({id:r.id,category:r.category,label:r.label,state:r.readiness.recordedState,remoteExecution:false,source:r.provenance.source}));
    const next=offset+items.length;
    return {items,total:found.length,revision:s.revision,nextCursor:next<found.length?Buffer.from(JSON.stringify({offset:next,query,revision:s.revision})).toString('base64url'):null,sourceStatus:stateOf(s)};
  }
  async function get({id}) {const s=await snapshot();const r=s.records.find(r=>r.id===id);if(!r)throw Error('not_found');return structuredClone(r);}
  return {status,search,get};
}
