var DENER_SSOT_ID = '1e6s2dKOYVLNsPUguHI85RLVLwJKtlCsQZBJ1BE-UhaY';
var DENER_SSOT_OPS = Object.freeze(['health','export_public','export_internal']);

function jsonOut_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  return routeSsot_(e && e.parameter ? e.parameter.op : 'health');
}

function doPost(e) {
  var op = e && e.parameter ? e.parameter.op : '';
  return routeSsot_(op);
}

function routeSsot_(op) {
  if (DENER_SSOT_OPS.indexOf(op) < 0) return jsonOut_({ok:false,error:'OP_NOT_ALLOWED',op:op});
  if (op === 'health') return jsonOut_({ok:true,service:'dener-ssot-api',mode:'SHADOW',spreadsheet_id:DENER_SSOT_ID});
  try {
    var payload = ssotExport_(op === 'export_public');
    return jsonOut_(payload);
  } catch (err) {
    return jsonOut_({ok:false,error:'SSOT_EXPORT_FAILED',message:String(err && err.message || err)});
  }
}
