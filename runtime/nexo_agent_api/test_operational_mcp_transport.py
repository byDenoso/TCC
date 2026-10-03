"""Regression tests for the real deployment's HTTP response decoding failure."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from .operational_mcp_transport import decode_rpc_response
from .operational_control import OperationalError
from .operational_tick import tick_existing_writer, WRITER_REF


def response(body, content_type='application/json', status=200):
    if not isinstance(body,bytes):body=json.dumps(body).encode()
    return SimpleNamespace(content=body, status_code=status, headers={'content-type':content_type})


class McpTransportTest(unittest.TestCase):
    def test_json_response(self):
        r=response({'jsonrpc':'2.0','id':1,'result':{'ok':True}})
        self.assertEqual(decode_rpc_response(r,1,'initialize'),{'ok':True})
    def test_legacy_sse_response(self):
        raw=b': keepalive\r\n\r\nevent: message\r\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\r\n\r\n'
        self.assertEqual(decode_rpc_response(response(raw,'text/event-stream'),1,'initialize'),{'ok':True})
    def test_sse_notification_and_multiline_response(self):
        raw=b'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\nevent: message\ndata: {"jsonrpc":"2.0","id":1,\ndata: "result":{}}\n\n'
        self.assertEqual(decode_rpc_response(response(raw,'text/event-stream'),1,'tools/list'),{})
    def test_html_empty_and_oversized_are_safe_errors(self):
        for raw,kind in [(b'<html>private-content</html>','text/html'),(b'','application/json'),(b'a'*262145,'application/json')]:
            with self.subTest(kind=kind):
                with self.assertRaises(OperationalError) as raised:decode_rpc_response(response(raw,kind),1,'initialize')
                self.assertNotIn('private-content',str(raised.exception))
    def test_duplicate_id_unknown_id_and_rpc_error_rejected(self):
        good=b'data: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'
        for raw in [good+good,good.replace(b'"id":1',b'"id":2'),good.replace(b'"result":{}',b'"error":{"code":-1}')]:
            with self.assertRaises(OperationalError):decode_rpc_response(response(raw,'text/event-stream'),1,'tools/list')
    def test_malformed_json_is_a_labeled_error(self):
        with self.assertRaisesRegex(OperationalError,'MCP_JSON_INITIALIZE'):decode_rpc_response(response(b'{'),1,'initialize')
    def test_dry_run_performs_no_io(self):
        with patch('runtime.nexo_agent_api.operational_tick.TowerWriterStore',side_effect=AssertionError('no store in dry run')):
            self.assertEqual(tick_existing_writer(None,{'NEXO_ROBOT_DRY':'1'})['reason'],'DRY_RUN')
    def test_canonical_change_signals_existing_workflow(self):
        before={'revision':'sha256:'+'a'*64};after={'revision':'sha256:'+'b'*64}
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'out'
            with patch('runtime.nexo_agent_api.operational_tick.TowerWriterStore') as store, patch('runtime.nexo_agent_api.operational_tick._tick',return_value={'status':'OK'}):
                store.return_value._load.side_effect=[(None,None,before),(None,None,after)]
                tick_existing_writer(None,{'GITHUB_ACTIONS':'true','GITHUB_WORKFLOW_REF':WRITER_REF,'GITHUB_OUTPUT':str(target)})
            self.assertEqual(target.read_text(),'tower_revision='+after['revision']+'\n')


if __name__=='__main__':unittest.main()
