var SSOT_TABLES={projects:'PROJECTS',work:'WORK',tests:'TESTS',events:'EVENTS',knowledge:'KNOWLEDGE',relations:'RELATIONS',decisions:'DECISIONS',olympus:'OLYMPUS'};
function ssotExport_(publicMode){
  var book=SpreadsheetApp.openById(DENER_SSOT_ID),system=ssotReadSystem_(book),out={schema_version:'1.0',ssot_revision:Number(system.ssot_revision||0),generated_at:new Date().toISOString(),projects:ssotReadTable_(book,'PROJECTS'),work:ssotReadTable_(book,'WORK'),tests:ssotReadTable_(book,'TESTS'),events:ssotReadTable_(book,'EVENTS'),knowledge:ssotReadTable_(book,'KNOWLEDGE'),relations:ssotReadTable_(book,'RELATIONS'),decisions:ssotReadTable_(book,'DECISIONS'),system:system};
  var privateRows=ssotReadTable_(book,'OLYMPUS'); out.olympus_summary=ssotPublicSummary_(privateRows); if(!publicMode)out.olympus=privateRows;
  ssotSort_(out); out.state_hash=ssotHash_(out); out.ok=true; return out;
}
function ssotReadTable_(book,name){
  var sheet=book.getSheetByName(name); if(!sheet)throw new Error('SCHEMA_NOT_READY: missing '+name); var values=sheet.getDataRange().getDisplayValues(); if(values.length<2)return[];
  var headers=values[0].map(function(v){return String(v).trim();}); return values.slice(1).filter(function(r){return r.some(function(v){return String(v).trim()!=='';});}).map(function(r){var o={};headers.forEach(function(h,i){if(h)o[h]=r[i];});return o;});
}
function ssotReadSystem_(book){var out={};ssotReadTable_(book,'SYSTEM').forEach(function(r){var k=r.key||r.Key||r.setting||r.id,v=r.value||r.Value||r.detail||r.status;if(k)out[String(k)]=v;});return out;}
function ssotSort_(p){['projects','work','tests','events','knowledge','relations','decisions','olympus_summary','olympus'].forEach(function(k){if(Array.isArray(p[k]))p[k].sort(function(a,b){return ssotId_(a).localeCompare(ssotId_(b));});});}
function ssotId_(r){return String(r.id||r.record_id||r.work_id||r.test_id||r.project_id||r.relation_id||r.decision_id||r.event_id||'');}
