function getSsotId_(){
  var value=PropertiesService.getScriptProperties().getProperty('DENER_SSOT_ID');
  if(!value)throw new Error('CONFIG_MISSING:DENER_SSOT_ID');
  return value;
}
