import base64, unittest
from nexo_persist.relay import relay_one, ContentConflict

def meta(body, sha='s1'):
    return {'content':base64.b64encode(body.encode()).decode(),'sha':sha}

class Fake:
    def __init__(self, gets, puts):
        self.gets=list(gets); self.puts=list(puts); self.put_calls=0
    def get(self, target): return self.gets.pop(0)
    def put(self, target, body):
        self.put_calls += 1
        return self.puts.pop(0)

class RelayTests(unittest.TestCase):
    def test_409_then_readback_missing_then_retry(self):
        b='{"x":1}\n'; f=Fake([(404,{}),(404,{}),(200,meta(b))],[(409,{}),(201,{})])
        self.assertEqual(relay_one(f,'inbox/x.json',b,sleep=lambda _:None),'relayed')
        self.assertEqual(f.put_calls,2)
    def test_timeout_after_write_is_recovered_by_readback(self):
        b='{"x":1}\n'; f=Fake([(404,{}),(200,meta(b))],[(0,{'uncertain':True})])
        self.assertEqual(relay_one(f,'inbox/x.json',b,sleep=lambda _:None),'recovered_after_uncertain_write')
        self.assertEqual(f.put_calls,1)
    def test_lost_response_is_recovered_by_readback(self):
        b='{"x":1}\n'; f=Fake([(404,{}),(200,meta(b))],[(503,{})])
        self.assertEqual(relay_one(f,'inbox/x.json',b,sleep=lambda _:None),'recovered_after_uncertain_write')
    def test_duplicate_same_content_is_noop(self):
        b='{"x":1}\n'; f=Fake([(200,meta(b))],[])
        self.assertEqual(relay_one(f,'inbox/x.json',b,sleep=lambda _:None),'already_relayed')
        self.assertEqual(f.put_calls,0)
    def test_same_id_different_content_is_terminal_conflict(self):
        f=Fake([(200,meta('{"x":2}\n'))],[])
        with self.assertRaises(ContentConflict):
            relay_one(f,'inbox/x.json','{"x":1}\n',sleep=lambda _:None)

if __name__=='__main__': unittest.main()
