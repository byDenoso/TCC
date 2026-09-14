var SSOT_TABLES = Object.freeze({
  projects:'PROJECTS', work:'WORK', tests:'TESTS', events:'EVENTS', knowledge:'KNOWLEDGE',
  relations:'RELATIONS', decisions:'DECISIONS', olympus:'OLYMPUS'
});

function ssotExport_(publicMode) {
  var book = SpreadsheetApp.openById(DENER_SSOT_ID);
  var system = ssotReadSystem_(book);
  var out = {
    schema_version:'1.0',
    ssot_revision:Number(system.ssot_revision || 0),
    generated_at:new Date().toISOString(),
    projects:ssotReadTable_(book,SSOT_TABLES.projects),
    work:ssotReadTable_(book,SSOT_TABLES.work),
    tests:ssotReadTable_(book,SSOT_TABLES.tests),
    events:ssotReadTable_(book,SSOT_TABLES.events),
    knowledge:ssotReadTable_(book,SSOT_TABLES.knowledge),
    relations:ssotReadTable_(book,SSOT_TABLES.relations),
    decisions:ssotReadTable_(book,SSOT_TABLES.decisions),
    olympus_summary:[], system:system
  };
  var olympus = ssotReadTable_(book,SSOT_TABLES.olympus);
  out.olympus_summary = ssotSanitizeOlympus_(olympus);
  if (!publicMode) out.olympus = olympus;
  out = ssotStableSort_(out);
  out.state_hash = ssotHash_(out);
  out.ok = true;
  return out;
}

function ssotReadTable_(book,name) {
  var sheet = book.getSheetByName(name);
  if (!sheet) throw new Error('SCHEMA_NOT_READY: missing '+name);
  var values = sheet.getDataRange().getDisplayValues();
  if (values.length < 2) return [];
  var headers = values[0].map(function(v){return String(v).trim();});
  return values.slice(1).filter(function(row){return row.some(function(v){return String(v).trim() !== '';});}).map(function(row){
    var obj = {};
    headers.forEach(function(h,i){if(h) obj[h]=row[i];});
    return obj;
  });
}

function ssotReadSystem_(book) {
  var rows = ssotReadTable_(book,'SYSTEM');
  var out = {};
  rows.forEach(function(row){
    var key = row.key || row.Key || row.setting || row.id;
    var value = row.value || row.Value || row.detail || row.status;
    if (key) out[String(key)] = value;
  });
  return out;
}

function ssotStableSort_(payload) {
  Object.keys(SSOT_TABLES).forEach(function(key){
    var target = key === 'olympus' ? 'olympus_summary' : key;
    if (Array.isArray(payload[target])) payload[target].sort(function(a,b){return ssotId_(a).localeCompare(ssotId_(b));});
  });
  if (Array.isArray(payload.olympus)) payload.olympus.sort(function(a,b){return ssotId_(a).localeCompare(ssotId_(b));});
  return payload;
}

function ssotId_(row) {
  return String(row.id || row.record_id || row.work_id || row.test_id || row.project_id || row.relation_id || row.decision_id || row.event_id || '');
}
