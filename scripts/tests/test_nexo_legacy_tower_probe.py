import unittest
from scripts.nexo_legacy_tower_probe import EVENT,HEADERS,ProbeError,exact_event,check

class Resp:
    def __init__(self,payload,status=200):self.payload=payload;self.status_code=status
    def json(self):return self.payload

class Fake:
    def __init__(self):self.rows=[list(HEADERS)];self.posts=0
    def get(self,url,params=None,timeout=None):
        if '/drive/v3/files' in url:return Resp({'files':[{'id':'private-sheet'}]})
        if ':U600' in url:return Resp({'values':self.rows})
        if params and params.get('fields')=='sheets(properties(sheetId,title))':
            return Resp({'sheets':[{'properties':{'sheetId':901,'title':'TRABALHOS'}}]})
        raise AssertionError('unexpected request')
    def post(self,url,json,timeout=None):
        self.posts+=1
        self.rows.append([x['userEnteredValue']['stringValue'] for x in json['requests'][0]['appendCells']['rows'][0]['values']])
        return Resp({'replies':[{}]})

class Tests(unittest.TestCase):
    def test_first_write_readback(self):
        f=Fake();self.assertEqual(check(f),'TOWER_READ_WRITE_CONFIRMED');self.assertEqual(f.posts,1)
    def test_retry_does_not_append(self):
        f=Fake();check(f);self.assertEqual(check(f),'ALREADY_CONFIRMED');self.assertEqual(f.posts,1)
    def test_conflicting_duplicate_rejected(self):
        f=Fake();f.rows.append([*EVENT[:-1],'changed'])
        with self.assertRaisesRegex(ProbeError,'EVENT_PAYLOAD_MISMATCH'):check(f)
    def test_duplicate_rejected(self):
        f=Fake();f.rows.extend([list(EVENT),list(EVENT)])
        with self.assertRaisesRegex(ProbeError,'DUPLICATE_EVENT_ID'):check(f)
    def test_wrong_header_rejected(self):
        f=Fake();f.rows[0][0]='other'
        with self.assertRaisesRegex(ProbeError,'TOWER_HEADER_MISMATCH'):check(f)
    def test_non_unique_sheet_rejected(self):
        class Dup(Fake):
            def get(self,url,params=None,timeout=None):
                if '/drive/v3/files' in url:return Resp({'files':[{'id':'x'},{'id':'y'}]})
                return super().get(url,params,timeout)
        with self.assertRaisesRegex(ProbeError,'TOWER_NOT_UNIQUELY_ACCESSIBLE'):check(Dup())

if __name__=='__main__': unittest.main()
