"""Validate legacy service account access to existing NEXO Tower (no secrets logged)."""
import json
import os
import urllib.parse

HEADERS = (
 'event_id','work_id','family_id','owner_front','kind','mode_requested',
 'mode_executed','stage','status','executor','attempt','budget_units',
 'spec_id','spec_sha256','input_manifest_id','parents_json','result_id',
 'artifact_manifest_id','lease_until','created_at','note'
)

EVENT = (
 'N31-OLD-SA-AUTH-20261109-V1','NEXO-TOWER-CREDENTIAL-SMOKE-20261109',
 'NEXO-PERSIST-V31','P','TECNICO','PREPARACAO','PREPARACAO',
 'CRED_TEST','TOWER_WRITABLE_CONFIRMED','SA_TCC','0','0',
 '','','','[]','','','','2026-11-09',
 'Existing credential read/write smoke. SCI_TEST_NEW=0; no Drive file created.'
)

class ProbeError(Exception):
 pass


def exact_event(rows):
    matches = [x for x in rows if x and x[0] == EVENT[0]]
    if len(matches) > 1:
        raise ProbeError('DUPLICATE_EVENT_ID')
    if matches:
        normalized = tuple(str(x) if x is not None else '' for x in matches[0])
        if normalized != EVENT:
            raise ProbeError('EVENT_PAYLOAD_MISMATCH')
        return True
    return False


def check(session):
    def response(r, step):
        if r.status_code != 200:
            raise ProbeError(f'{step}_HTTP_{r.status_code}')
        return r.json()

    # The old credential sees only Drive entries granted to its service-account identity.
    payload = response(session.get('https://www.googleapis.com/drive/v3/files',
      params={'q': "name = 'NEXO Tower · Operação' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false",
              'pageSize': 100,'fields':'nextPageToken,files(id,name)'},timeout=25), 'TOWER_SEARCH')
    files = payload.get('files', [])
    if payload.get('nextPageToken') or len(files) != 1:
        raise ProbeError('TOWER_NOT_UNIQUELY_ACCESSIBLE')
    sid = files[0]['id']
    base = 'https://sheets.googleapis.com/v4/spreadsheets/' + urllib.parse.quote(sid,safe='')
    def read():
        result=response(session.get(base+'/values/TRABALHOS!A1:U600',timeout=35),'TOWER_READ')
        vals=result.get('values',[])
        if not vals or tuple(vals[0]) != HEADERS:
            raise ProbeError('TOWER_HEADER_MISMATCH')
        return vals[1:]
    if exact_event(read()):
        return 'ALREADY_CONFIRMED'
    meta=response(session.get(base,params={'fields':'sheets(properties(sheetId,title))'},timeout=25),'TOWER_META')
    matches=[s['properties']['sheetId'] for s in meta.get('sheets',[]) if s.get('properties',{}).get('title')=='TRABALHOS']
    if len(matches)!=1:
        raise ProbeError('TOWER_TAB_NOT_UNIQUE')
    req={'requests':[{'appendCells':{'sheetId':matches[0],
        'rows':[{'values':[{'userEnteredValue':{'stringValue':v}} for v in EVENT]}],
        'fields':'userEnteredValue'}}]}
    response(session.post(base+':batchUpdate',json=req,timeout=35),'TOWER_APPEND')
    if not exact_event(read()):
        raise ProbeError('TOWER_READBACK_MISSING')
    return 'TOWER_READ_WRITE_CONFIRMED'


def main():
    raw = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON','')
    if not raw:
        raise SystemExit('LEGACY_CREDENTIAL_UNAVAILABLE')
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    info=json.loads(raw)
    if info.get('type')!='service_account':
        raise SystemExit('LEGACY_CREDENTIAL_NOT_SERVICE_ACCOUNT')
    scopes=['https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/spreadsheets']
    session=AuthorizedSession(service_account.Credentials.from_service_account_info(info,scopes=scopes))
    try:
        print(check(session))
    except ProbeError as exc:
        raise SystemExit(str(exc)) from None

if __name__=='__main__':
    main()
