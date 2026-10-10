var PUBLIC_SUMMARY_FIELDS = Object.freeze(['id','record_id','label','title','status','program','detail','checkin_status','freshness','next_action']);

function ssotPublicSummary_(rows) {
  return rows.map(function(row){
    var out = {};
    PUBLIC_SUMMARY_FIELDS.forEach(function(field){
      if (row[field] !== undefined && row[field] !== '') out[field] = row[field];
    });
    if (!out.id && out.record_id) out.id = out.record_id;
    if (!out.label && out.title) out.label = out.title;
    delete out.record_id;
    delete out.title;
    return out;
  });
}
