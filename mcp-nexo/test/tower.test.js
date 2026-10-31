import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readTowerResults } from '../lib/tower.js';

test('reads bounded latest Tower result rows with provenance and read-only scopes', async () => {
  const calls=[];
  const headers=['data','task','item','titulo','resultado','metodo','numeros','limites','referencias','link_dados'];
  const fetchImpl=async (url,options)=>{
    calls.push({url:String(url),options});
    if(String(url).includes('api.vercel.com')) return Response.json({token:'synthetic-google-token'});
    if(String(url).includes('fields=sheets')) return Response.json({sheets:[{properties:{title:'RESULTADOS',gridProperties:{rowCount:100}}}]});
    if(String(url).includes('A1%3AJ1')) return Response.json({values:[headers]});
    if(String(url).includes('spreadsheets/')) return Response.json({values:[['2026-01-01','S1','ID','title','result','method','{}','limit','ref','link']]});
    throw Error('unexpected');
  };
  const value=await readTowerResults({oidcToken:'synthetic-oidc',connector:'google/example',subject:'owner',spreadsheetId:'fixture',limit:1,fetchImpl});
  assert.equal(value.rows[0].resultado,'result');
  assert.equal(value.source.tab,'RESULTADOS');
  assert.equal(calls.length,4);
  assert.deepEqual(JSON.parse(calls[0].options.body).scopes,['https://www.googleapis.com/auth/spreadsheets.readonly']);
  assert.match(calls[3].url,/RESULTADOS/);
  assert.equal(calls[3].options.method,'GET');
  assert.ok(!JSON.stringify(value).includes('synthetic'));
});

test('missing project identity fails closed without provider call', async()=>{
  await assert.rejects(readTowerResults({oidcToken:'',connector:'google/example',subject:'owner',fetchImpl:()=>{throw Error('called')}}),/CONNECT_NOT_CONFIGURED/);
});

test('provider errors expose only HTTP status, not response contents', async()=>{
  const fetchImpl=async()=>new Response('sensitive-provider-response',{status:403});
  await assert.rejects(readTowerResults({oidcToken:'x',connector:'google/example',subject:'owner',spreadsheetId:'fixture',fetchImpl}), {message:'CONNECT_UNAVAILABLE_HTTP_403'});
});

test('missing consent starts authorization for the same subject and read scope', async()=>{
  const calls=[];
  const fetchImpl=async(url,options)=>{
    calls.push({url:String(url),body:JSON.parse(options.body)});
    return calls.length===1 ? Response.json({error:{code:'user_authorization_required'}},{status:401}) : Response.json({url:'https://connect.vercel.com/authorize/example',verifier:'do-not-return'});
  };
  const value=await readTowerResults({oidcToken:'x',connector:'google/example',subject:'owner',spreadsheetId:'fixture',fetchImpl});
  assert.deepEqual(value,{authorization_required:true,authorization_url:'https://connect.vercel.com/authorize/example'});
  assert.deepEqual(calls[0].body,calls[1].body);
  assert.match(calls[1].url,/\/v1\/connect\/authorize\//);
});
