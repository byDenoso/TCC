import { createCatalogService } from './catalog.js';
const MAX_BYTES=64*1024*1024;
async function limitedText(response){
  if(Number(response.headers.get('content-length'))>MAX_BYTES)throw Error('SOURCE_TOO_LARGE');
  if(!response.body)return '';
  const reader=response.body.getReader();const chunks=[];let length=0;
  try{while(true){const {value,done}=await reader.read();if(done)break;length+=value.length;if(length>MAX_BYTES)throw Error('SOURCE_TOO_LARGE');chunks.push(value);}}
  finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
  return new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(Buffer.concat(chunks));
}
export function createDriveReader({token,fetchImpl=fetch}){
  return async source=>{
    if(!token||typeof source.fileId!=='string'||!/^[A-Za-z0-9_-]{1,160}$/.test(source.fileId))throw Error('INVALID_CONFIG');
    const base='https://www.googleapis.com/drive/v3/files/'+encodeURIComponent(source.fileId);
    async function get(url){const r=await fetchImpl(url,{method:'GET',redirect:'error',headers:{authorization:'Bearer '+token,accept:'application/json, text/plain'},signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('UNAVAILABLE');return limitedText(r);}
    const url=base+'?fields=id,mimeType,modifiedTime,version&supportsAllDrives=true';
    const before=JSON.parse(await get(url));
    const native=before.mimeType?.startsWith('application/vnd.google-apps.');
    if(native && before.mimeType!=='application/vnd.google-apps.document' && !(source.format==='lookup_sheet' && before.mimeType==='application/vnd.google-apps.spreadsheet'))throw Error('UNSUPPORTED_FORMAT');
    const text=await get(source.format==='lookup_sheet'
      ? 'https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(source.fileId)+'/values/'+encodeURIComponent('LOOKUP!A:D')+'?valueRenderOption=UNFORMATTED_VALUE'
      : native?base+'/export?mimeType=text%2Fplain':base+'?alt=media&supportsAllDrives=true');
    const after=JSON.parse(await get(url));
    if(!before.version||before.version!==after.version||before.modifiedTime!==after.modifiedTime)throw Error('SOURCE_CHANGED');
    return {text,modifiedTime:before.modifiedTime,version:before.version};
  };
}
let service;let configuration;
export function configuredCatalog(){
  const config=process.env.NEXO_CATALOG_SOURCES||'[]';const token=process.env.GOOGLE_DRIVE_ACCESS_TOKEN;
  // Credential rotation invalidates cache. Values are never logged or returned.
  if(!service||configuration?.config!==config||configuration?.token!==token){
    const sources=JSON.parse(config);
    service=createCatalogService({sources,readSource:createDriveReader({token})});configuration={config,token};
  }
  return service;
}
