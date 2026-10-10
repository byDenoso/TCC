function ssotHash_(payload){
  var copy=JSON.parse(JSON.stringify(payload)); delete copy.generated_at; delete copy.state_hash; delete copy.ok;
  var text=ssotCanonicalJson_(copy); var bytes=Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,text,Utilities.Charset.UTF_8);
  return 'sha256:'+bytes.map(function(b){var v=(b<0?b+256:b).toString(16);return v.length===1?'0'+v:v;}).join('');
}
function ssotCanonicalJson_(value){
  if(value===null||typeof value!=='object')return JSON.stringify(value);
  if(Array.isArray(value))return '['+value.map(ssotCanonicalJson_).join(',')+']';
  var keys=Object.keys(value).sort(); return '{'+keys.map(function(k){return JSON.stringify(k)+':'+ssotCanonicalJson_(value[k]);}).join(',')+'}';
}
