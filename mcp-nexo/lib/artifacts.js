import { createHash } from 'node:crypto';
import { getGoogleConnectToken } from './tower.js';

const SCHEMA=['data','task','item','titulo','resultado','metodo','numeros','limites','referencias','link_dados'];
const MAX_VERIFY_BYTES=10*1024*1024;
const SCOPE=['https://www.googleapis.com/auth/drive.readonly','https://www.googleapis.com/auth/spreadsheets.readonly'];

export function parseLocalOnly(value){
  if(typeof value!=='string'||!value.startsWith('LOCAL_ONLY|'))return null;
  const items=value.split('|').slice(1);
  const fields=Object.fromEntries(items.filter(x=>x.includes('=')).map(x=>[x.slice(0,x.indexOf('=')),x.slice(x.indexOf('=')+1)]));
  const filename=fields.file||items.find(x=>/\.(zip|json|tar\.gz|zst|csv)$/i.test(x))||'';
  if(!/^[A-Za-z0-9._-]{1,180}$/.test(filename)||filename==='.'||filename==='..')return {state:'INVALID_LOCAL_REFERENCE'};
  const sha256=/^[0-9a-f]{64}$/i.test(fields.sha256||'')?fields.sha256.toLowerCase():null;
  const bytes=fields.bytes!==undefined&&/^\d+$/.test(fields.bytes)?Number(fields.bytes):null;
  return {filename,sha256,bytes:Number.isSafeInteger(bytes)?bytes:null,origin:'LOCAL_ONLY'};
}

async function json(url,token,fetchImpl){
  const r=await fetchImpl(url,{method:'GET',redirect:'error',headers:{authorization:'Bearer '+token},signal:AbortSignal.timeout(15000)});
  if(!r.ok)throw Error('READ_UNAVAILABLE');
  return r.json();
}

export async function inspectLocalArtifact({row,oidcToken,connector,subject,spreadsheetId,fetchImpl=fetch}){
  if(!Number.isSafeInteger(row)||row<2)throw Error('INVALID_ROW');
  if(!/^[\w-]{1,160}$/.test(spreadsheetId||''))throw Error('CONNECT_NOT_CONFIGURED');
  const access=await getGoogleConnectToken({oidcToken,connector,subject,scopes:SCOPE,fetchImpl});
  if(access.authorization_required)return access;
  const token=access.token;
  const base='https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(spreadsheetId);
  const metadata=await json(base+'?fields=sheets.properties.title%2Csheets.properties.gridProperties.rowCount',token,fetchImpl);
  const last=metadata.sheets?.find(x=>x.properties?.title==='RESULTADOS')?.properties?.gridProperties?.rowCount;
  if(!Number.isSafeInteger(last)||row>last)throw Error('INVALID_ROW');
  const range=async r=>json(base+'/values/'+encodeURIComponent("'RESULTADOS'!"+r),token,fetchImpl);
  const head=await range('A1:J1');
  if(JSON.stringify(head.values?.[0])!==JSON.stringify(SCHEMA))throw Error('TOWER_SCHEMA_INVALID');
  const selected=(await range('A'+row+':J'+row)).values?.[0]||[];
  if(!selected.some(Boolean))return {state:'EMPTY_TOWER_ROW',row,readOnly:true};
  const link=selected[9]??'';
  const local=parseLocalOnly(link);
  const result={row,item:selected[2]??'',towerRecord:link.startsWith('LOCAL_ONLY|')?'LOCAL_ONLY':'OTHER',readOnly:true};
  if(!local)return {...result,state:'NOT_LOCAL_ONLY'};
  if(local.state)return {...result,state:local.state};
  const {filename,sha256,bytes}=local;
  const safeName=filename.replaceAll('\\','\\\\').replaceAll("'", "\\'");
  const q="name = '"+safeName+"' and trashed = false";
  const url='https://www.googleapis.com/drive/v3/files?'+new URLSearchParams({q,fields:'nextPageToken,files(id,name,mimeType,size,modifiedTime,webViewLink)',pageSize:'100',supportsAllDrives:'true',includeItemsFromAllDrives:'true'});
  const found=await json(url,token,fetchImpl);
  const items=(found.files||[]).filter(f=>f.name===filename);
  if(found.nextPageToken||items.length>10)return {...result,state:'AMBIGUOUS_DRIVE_MATCH',filename,matches:items.length};
  if(!items.length)return {...result,state:'NOT_FOUND_IN_DRIVE',filename,sha256Expected:sha256,expectedBytes:bytes};
  const candidates=[];
  for(const file of items){
    if(file.mimeType?.startsWith('application/vnd.google-apps.')){candidates.push({id:file.id,state:'UNVERIFIABLE_NATIVE_FILE'});continue;}
    if(bytes!==null&&Number(file.size)!==bytes){candidates.push({id:file.id,state:'SIZE_MISMATCH',observedBytes:Number(file.size)});continue;}
    if(!sha256){candidates.push({id:file.id,state:'HASH_NOT_DECLARED'});continue;}
    if(Number(file.size)>MAX_VERIFY_BYTES){candidates.push({id:file.id,state:'HASH_VERIFY_SIZE_LIMIT'});continue;}
    const response=await fetchImpl('https://www.googleapis.com/drive/v3/files/'+encodeURIComponent(file.id)+'?alt=media&supportsAllDrives=true',{
      method:'GET',redirect:'error',headers:{authorization:'Bearer '+token},signal:AbortSignal.timeout(20000)
    });
    if(!response.ok||!response.body){candidates.push({id:file.id,state:'FILE_READ_UNAVAILABLE'});continue;}
    const digest=createHash('sha256');const reader=response.body.getReader();let read=0,overflow=false;
    try{while(true){const {done,value}=await reader.read();if(done)break;read+=value.length;if(read>MAX_VERIFY_BYTES){overflow=true;break;}digest.update(value);}}
    finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
    if(overflow){candidates.push({id:file.id,state:'HASH_VERIFY_SIZE_LIMIT'});continue;}
    const actual=digest.digest('hex');
    candidates.push({id:file.id,state:actual===sha256&& (bytes===null||bytes===read)?'VERIFIED':'HASH_MISMATCH',observedBytes:read,sha256Actual:actual});
  }
  const matches=candidates.filter(c=>c.state==='VERIFIED');
  return {...result,filename,sha256Expected:sha256,expectedBytes:bytes,state:matches.length===1?'VERIFIED_DRIVE_COPY':matches.length>1?'AMBIGUOUS_VERIFIED_COPIES':'UNRESOLVED_LOCAL_ONLY',candidates};
}
