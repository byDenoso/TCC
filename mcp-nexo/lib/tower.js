import { createHash } from 'node:crypto';
const SCHEMA=['data','task','item','titulo','resultado','metodo','numeros','limites','referencias','link_dados'];
const SCOPE='https://www.googleapis.com/auth/spreadsheets.readonly';

const CONNECT_STATE = new WeakMap();
function getConnectionState(fetchImpl, oidcToken, connector, subject, scopes) {
  let byKey = CONNECT_STATE.get(fetchImpl);
  if (!byKey) { byKey = new Map(); CONNECT_STATE.set(fetchImpl, byKey); }
  const key = createHash('sha256').update(JSON.stringify([oidcToken, connector, subject, [...scopes].sort()])).digest('hex');
  let state = byKey.get(key);
  if (!state) { state = {}; byKey.set(key, state); }
  return state;
}

export async function getGoogleConnectToken({oidcToken,connector,subject,scopes=[SCOPE],fetchImpl=fetch}) {
  if(!oidcToken || !/^[\w.-]+\/[\w.-]+$/.test(connector||'') || !subject) throw Error('CONNECT_NOT_CONFIGURED');
  const state = getConnectionState(fetchImpl, oidcToken, connector, subject, scopes);
  const now = Date.now();
  if (state.token && state.validUntil > now) return {token: state.token};
  if (state.pending) return state.pending;
  if (state.blockedUntil > now) throw Error('CONNECT_UNAVAILABLE_HTTP_429');
  const pending = (async () => {
    const connect=await fetchImpl('https://api.vercel.com/v1/connect/token/'+encodeURIComponent(connector),{
      method:'POST',redirect:'error',headers:{authorization:'Bearer '+oidcToken,'content-type':'application/json'},
      body:JSON.stringify({subject:{type:'user',id:subject},scopes:scopes}),signal:AbortSignal.timeout(10000)
    });
    if(connect.status===429){
      const seconds = Number(connect.headers.get('retry-after'));
      state.blockedUntil = Date.now() + (Number.isFinite(seconds) && seconds > 0 ? Math.min(seconds * 1000,120000) : 30000);
      throw Error('CONNECT_UNAVAILABLE_HTTP_429');
    }
    if(!connect.ok) {
      const payload=await connect.json().catch(()=>null);
      const code=payload?.error?.code;
      if(connect.status===401 && code==='user_authorization_required') {
        const auth=await fetchImpl('https://api.vercel.com/v1/connect/authorize/'+encodeURIComponent(connector),{
          method:'POST',redirect:'error',headers:{authorization:'Bearer '+oidcToken,'content-type':'application/json',accept:'application/json'},
          body:JSON.stringify({subject:{type:'user',id:subject},scopes:scopes}),signal:AbortSignal.timeout(10000)
        });
        if(!auth.ok) throw Error('CONNECT_AUTHORIZATION_UNAVAILABLE_HTTP_'+auth.status);
        const data=await auth.json();
        let url;
        try { url=new URL(data.url); } catch { throw Error('CONNECT_AUTHORIZATION_INVALID'); }
        if(url.protocol!=='https:' || url.hostname!=='connect.vercel.com' || !url.pathname.startsWith('/authorize/')) throw Error('CONNECT_AUTHORIZATION_INVALID');
        return {authorization_required:true,authorization_url:url.href};
      }
      const safeCodes=new Set(['unauthorized','forbidden','invalid_token','invalid_oidc_token','invalid_grant','invalid_subject','not_found','user_authorization_required','invalid_request','unauthenticated']);
      throw Error('CONNECT_UNAVAILABLE_HTTP_'+connect.status+(safeCodes.has(code)?'_'+code:''));
    }
    const {token,expiresAt}=await connect.json();
    if(typeof token!=='string'||!token) throw Error('CONNECT_UNAVAILABLE');
    const expiry = Number(expiresAt);
    const expiryMs = expiry < 1e11 ? expiry * 1000 : expiry;
    if (expiresAt != null && Number.isFinite(expiryMs)) {
      const validUntil = Math.min(expiryMs - 30000, Date.now() + 60000);
      if (validUntil > Date.now()) {
        state.token = token;
        state.validUntil = validUntil;
      }
    }
    state.blockedUntil = 0;
    return {token};
  })();
  state.pending = pending;
  try { return await pending; }
  finally { if (state.pending === pending) state.pending = undefined; }
}

export async function readTowerResults({oidcToken,connector,subject,spreadsheetId,limit=10,fetchImpl=fetch}) {
  if(!/^[\w-]{1,160}$/.test(spreadsheetId||'')) throw Error('CONNECT_NOT_CONFIGURED');
  if(!Number.isSafeInteger(limit)||limit<1||limit>20) throw Error('INVALID_LIMIT');
  const access=await getGoogleConnectToken({oidcToken,connector,subject,fetchImpl});
  if(access.authorization_required) return access;
  const {token}=access;
  const base='https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(spreadsheetId);
  async function get(path){
    const r=await fetchImpl(base+path,{method:'GET',redirect:'error',headers:{authorization:'Bearer '+token},signal:AbortSignal.timeout(15000)});
    if(!r.ok) throw Error('TOWER_UNAVAILABLE');
    return r.json();
  }
  const meta=await get('?fields=sheets.properties.title%2Csheets.properties.gridProperties.rowCount');
  const count=meta.sheets?.find(s=>s.properties?.title==='RESULTADOS')?.properties?.gridProperties?.rowCount;
  if(!Number.isSafeInteger(count)||count<1) throw Error('TOWER_SCHEMA_INVALID');
  const getRange=range=>get('/values/'+encodeURIComponent("'RESULTADOS'!"+range));
  const head=await getRange('A1:J1');
  if(JSON.stringify(head.values?.[0])!==JSON.stringify(SCHEMA)) throw Error('TOWER_SCHEMA_INVALID');
  const start=Math.max(2,count-499);
  const data=count<2?{values:[]}:await getRange(`A${start}:J${count}`);
  const rows=(data.values||[]).map((row,i)=>({row:start+i,values:row})).filter(r=>r.values.some(Boolean)).slice(-limit).reverse().map(r=>({row:r.row,...Object.fromEntries(SCHEMA.map((key,i)=>[key,r.values[i]??'']))}));
  return {source:{spreadsheetId,tab:'RESULTADOS',readAt:new Date().toISOString(),rangeStart:start,rangeEnd:count},rows};
}
