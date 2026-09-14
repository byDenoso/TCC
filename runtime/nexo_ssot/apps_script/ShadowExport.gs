var SSOT_SHEETS=Object.freeze({projects:1824797708,work:2044152479,tests:1726857669,events:5082632,knowledge:339447707,relations:765989212,decisions:47761960,summary_source:418617595,system:1745215367});
function ssotShadowExport_(publicMode){
  var b=SpreadsheetApp.openById(DENER_SSOT_ID),s=readSystemById_(b),o={schema_version:'1.0',ssot_revision:Number(s.ssot_revision||0),generated_at:new Date().toISOString(),projects:readById_(b,SSOT_SHEETS.projects),work:readById_(b,SSOT_SHEETS.work),tests:readById_(b,SSOT_SHEETS.tests),events:readById_(b,SSOT_SHEETS.events),knowledge:readById_(b,SSOT_SHEETS.knowledge),relations:readById_(b,SSOT_SHEETS.relations),decisions:readById_(b,SSOT_SHEETS.decisions),system:s};
  var rows=readById_(b,SSOT_SHEETS.summary_source);o.olympus_summary=ssotPublicSummary_(rows);if(!publicMode)o.internal_summary_source=rows;sortShadow_(o);o.state_hash=ssotHash_(o);o.ok=true;return o;
}
function sheetById_(b,id){var sheets=b.getSheets();for(var i=0;i<sheets.length;i++)if(sheets[i].getSheetId()===id)return sheets[i];throw new Error('SCHEMA_NOT_READY:'+id);}
function readById_(b,id){var v=sheetById_(b,id).getDataRange().getDisplayValues();if(v.length<2)return[];var h=v[0].map(function(x){return String(x).trim();});return v.slice(1).filter(function(r){return r.some(function(x){return String(x).trim()!=='';});}).map(function(r){var o={};h.forEach(function(k,i){if(k)o[k]=r[i];});return o;});}
function readSystemById_(b){var o={};readById_(b,SSOT_SHEETS.system).forEach(function(r){if(r.key)o[String(r.key)]=r.value;});return o;}
function sortShadow_(p){['projects','work','tests','events','knowledge','relations','decisions','olympus_summary','internal_summary_source'].forEach(function(k){if(Array.isArray(p[k]))p[k].sort(function(a,b){return shadowId_(a).localeCompare(shadowId_(b));});});}
function shadowId_(r){return String(r.id||r.record_id||r.work_id||r.test_id||r.project_id||r.relation_id||r.decision_id||r.event_id||'');}
