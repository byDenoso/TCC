"""Bounded MCP JSON/SSE response decoding; never log credentials or bodies."""
from __future__ import annotations
import json
from .operational_control import OperationalError, require

MAX_RESPONSE = 262144


def json_object(raw, code):
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise OperationalError(code) from exc
    require(isinstance(value, dict), code)
    return value


def decode_rpc_response(response, request_id, stage):
    """Streamable HTTP may negotiate SSE for older MCP protocol clients."""
    label = stage.upper().replace('/', '_')
    require(response.status_code == 200, 'MCP_HTTP_' + str(response.status_code) + '_' + label)
    raw = response.content
    require(0 < len(raw) <= MAX_RESPONSE, 'MCP_RESPONSE_SIZE_' + label)
    kind = response.headers.get('content-type', '').split(';')[0].strip().lower()
    if kind == 'text/event-stream' or raw.lstrip().startswith((b'event:', b'data:', b':')):
        try:
            text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
        except UnicodeError as exc:
            raise OperationalError('MCP_SSE_ENCODING_' + label) from exc
        matching = []
        for block in text.split('\n\n'):
            data = []
            for line in block.split('\n'):
                if line.startswith('data:'):
                    value = line[5:]
                    data.append(value[1:] if value.startswith(' ') else value)
            if not data:
                continue
            value = json_object('\n'.join(data), 'MCP_SSE_JSON_' + label)
            if value.get('id') == request_id:
                matching.append(value)
            elif 'id' in value:
                raise OperationalError('MCP_UNEXPECTED_RESPONSE_ID_' + label)
        require(len(matching) == 1, 'MCP_SSE_RESPONSE_COUNT_' + label)
        message = matching[0]
    else:
        require(kind in ('application/json', 'application/json-rpc'), 'MCP_CONTENT_TYPE_' + label)
        message = json_object(raw, 'MCP_JSON_' + label)
    require(message.get('jsonrpc') == '2.0' and message.get('id') == request_id, 'MCP_RPC_ID_' + label)
    require(not message.get('error') and 'result' in message, 'MCP_RPC_ERROR_' + label)
    return message['result']
