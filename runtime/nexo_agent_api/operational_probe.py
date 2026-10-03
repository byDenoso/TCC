"""Bounded role-session canary using the Writer's already-issued GitHub OIDC.

No persistent credential, cron, scientific request or direct Tower write is
created here. All role actions go through the real deployed MCP endpoint.
"""
from __future__ import annotations
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .operational_control import require, role_context
from .operational_prompts import PROMPTS
from .operational_bootstrap import WRITER_REF

ENDPOINT = 'https://nexo-one-two.vercel.app/api/mcp'
WORK_ID = 'OPERATIONAL-CONTROL-DRIVE-SUM-V1'


def probe_role_session(store, config, env, http=None):
    if config.get('pilot_auto_start') is not True:
        return {'state': 'DISABLED'}
    work = store.get(WORK_ID)
    if work['state'] != 'READY' or work.get('owner') or work.get('outbox'):
        return {'state': 'NOT_NEEDED', 'canonical_state': work['state']}
    require(env.get('GITHUB_WORKFLOW_REF') == WRITER_REF and env.get('GITHUB_ACTIONS') == 'true', 'WRITER_OIDC_REQUIRED')
    require(env.get('ACTIONS_ID_TOKEN_REQUEST_URL') and env.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN'), 'EXISTING_WRITER_OIDC_UNAVAILABLE')
    if http is None:
        import requests
        http = requests.Session()
    url = urlsplit(env['ACTIONS_ID_TOKEN_REQUEST_URL'])
    require(url.scheme == 'https', 'OIDC_URL_INVALID')
    query = dict(parse_qsl(url.query));query['audience'] = 'nexo-inbox'
    url = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), ''))
    response = http.get(url, headers={'Authorization': 'Bearer ' + env['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}, timeout=30)
    require(response.status_code == 200, 'WRITER_OIDC_UNAVAILABLE')
    token = response.json().get('value')
    require(isinstance(token, str) and len(token) < 16384, 'WRITER_OIDC_INVALID')
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json, text/event-stream'}
    sequence = 0
    def rpc(method, params):
        nonlocal sequence
        sequence += 1
        response = http.post(ENDPOINT, headers=headers,
                             json={'jsonrpc': '2.0', 'id': sequence, 'method': method, 'params': params}, timeout=45)
        require(response.status_code == 200, 'MCP_HTTP_FAILED')
        if response.headers.get('mcp-session-id'):
            headers['Mcp-Session-Id'] = response.headers['mcp-session-id']
        data = response.json()
        require(not data.get('error') and data.get('id') == sequence, 'MCP_RPC_FAILED')
        return data['result']
    hello = rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                             'clientInfo': {'name': 'nexo-writer-role-canary', 'version': '1'}})
    headers['MCP-Protocol-Version'] = hello['protocolVersion']
    names = {item['name'] for item in rpc('tools/list', {}).get('tools', [])}
    require({'get_role_session', 'request_execution', 'get_result'} <= names, 'MCP_OPERATIONAL_TOOLS_UNAVAILABLE')
    def call(name, args):
        result = rpc('tools/call', {'name': name, 'arguments': args})
        require(not result.get('isError'), 'MCP_OPERATIONAL_ACTION_FAILED')
        if result.get('structuredContent', {}).get('result') is not None:
            return result['structuredContent']['result']
        import json
        return json.loads(result['content'][0]['text'])
    session = call('get_role_session', {'role': 'EXECUTOR'})
    require(session.get('prompt') == PROMPTS['EXECUTOR'], 'MCP_ROLE_PROMPT_MISMATCH')
    supplied = [row for row in session.get('available', []) if row.get('id') == WORK_ID]
    require(len(supplied) == 1 and supplied[0].get('role_session') == role_context(work, PROMPTS['EXECUTOR']), 'MCP_ROLE_CONTEXT_MISMATCH')
    first = call('request_execution', {'work_id': WORK_ID})
    second = call('request_execution', {'work_id': WORK_ID})
    require(first.get('state') == 'PENDING_WRITER' and first.get('queue_readback') == 'PASS', 'MCP_QUEUE_NOT_VERIFIED')
    require(first.get('intent_id') == second.get('intent_id') and second.get('idempotent') is True, 'MCP_REPEAT_NOT_IDEMPOTENT')
    return {'state': 'ROLE_SESSION_AND_IDEMPOTENCY_VERIFIED', 'work_id': WORK_ID,
            'mcp_endpoint': ENDPOINT, 'role_session': supplied[0]['role_session'],
            'intent_id': first['intent_id'], 'queue_readback': 'PASS', 'repeat_idempotent': True,
            'run_id': env.get('GITHUB_RUN_ID'), 'event': env.get('GITHUB_EVENT_NAME')}
