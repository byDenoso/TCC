#!/usr/bin/env python3
import base64, json, os, re, subprocess, time
from pathlib import Path

MAX_ATTEMPTS = 5

class RelayError(RuntimeError): pass
class ContentConflict(RelayError): pass
class TerminalTransportError(RelayError): pass

class GitHubContents:
    def __init__(self, repo, branch='nexo-inbox', timeout=30):
        self.repo, self.branch, self.timeout = repo, branch, timeout
    def _run(self, args, data=None):
        try:
            p = subprocess.run(['gh','api',*args], input=data, capture_output=True,
                               text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return 0, {'message':'timeout','uncertain':True}
        if p.returncode == 0:
            try: return 200, json.loads(p.stdout or '{}')
            except Exception: return 200, {}
        m = re.search(r'HTTP\s+(\d{3})', p.stderr or '')
        return (int(m.group(1)) if m else 0), {'message':(p.stderr or '').strip(),'uncertain':not bool(m)}
    def get(self, path):
        return self._run([f'repos/{self.repo}/contents/{path}?ref={self.branch}'])
    def put(self, path, body):
        payload = json.dumps({'message':'NEXO scheduled persistence relay','branch':self.branch,
                              'content':base64.b64encode(body.encode()).decode()})
        return self._run(['--method','PUT',f'repos/{self.repo}/contents/{path}','--input','-'], data=payload)

def decoded(meta):
    return base64.b64decode(meta['content']).decode('utf-8')

def classify(status):
    if status in (401,403,422): return 'terminal'
    if status == 409: return 'conflict'
    if status == 404: return 'missing'
    if status == 0 or status == 429 or 500 <= status <= 599: return 'uncertain'
    return 'other'

def readback(client, target, expected):
    status, meta = client.get(target)
    if status == 200:
        actual = decoded(meta)
        if actual == expected: return 'same'
        raise ContentConflict(f'{target}: same stable ID maps to different content')
    if status == 404: return 'missing'
    if classify(status) == 'terminal':
        raise TerminalTransportError(f'{target}: read denied/invalid HTTP {status}')
    return 'uncertain'

def relay_one(client, target, body, sleep=time.sleep, max_attempts=MAX_ATTEMPTS):
    state = readback(client, target, body)
    if state == 'same': return 'already_relayed'
    for attempt in range(1, max_attempts + 1):
        status, _ = client.put(target, body)
        if status in (200,201):
            if readback(client, target, body) == 'same': return 'relayed'
        elif classify(status) == 'terminal':
            raise TerminalTransportError(f'{target}: write denied/invalid HTTP {status}')
        elif classify(status) in ('conflict','uncertain'):
            if readback(client, target, body) == 'same': return 'recovered_after_uncertain_write'
        else:
            raise RelayError(f'{target}: unexpected HTTP {status}')
        if attempt < max_attempts:
            sleep(min(2 ** (attempt - 1), 8))
    raise RelayError(f'{target}: delivery unresolved after {max_attempts} attempts')

def collect_changed():
    event = os.environ.get('EVENT','')
    before = os.environ.get('BEFORE','') or '0'
    if event == 'push' and not re.fullmatch(r'0+', before):
        cp = subprocess.run(['git','diff','--name-only','--diff-filter=AM',before,os.environ['GITHUB_SHA']],
                            capture_output=True,text=True,check=True)
        changed = cp.stdout.split()
    else:
        changed = [str(p) for p in Path('nexo_persist/requests').glob('*.json')]
    if any(Path(f).name.startswith('replay-all') for f in changed):
        changed = [str(p) for p in Path('nexo_persist/requests').glob('*.json')]
    return [f for f in changed if f.startswith('nexo_persist/requests/') and
            f.endswith('.json') and not Path(f).name.startswith('replay-all')]

def load_request(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    env = data['envelope'] if isinstance(data.get('envelope'), dict) else data
    if not isinstance(env.get('kind'), str) or 'payload' not in env:
        raise ValueError('invalid envelope')
    raw_id = str(data.get('stable_id') or Path(path).stem)
    sid = re.sub(r'[^a-z0-9-]+','-',raw_id.lower()).strip('-')[:60] or 'request'
    target = f'inbox/scheduled-{sid}.json'
    body = json.dumps(env, ensure_ascii=False, separators=(',',':'), sort_keys=True) + '\n'
    return target, body

def main():
    client = GitHubContents(os.environ['GITHUB_REPOSITORY'])
    ok = failures = 0
    for f in collect_changed():
        try:
            target, body = load_request(f)
            print(f'{target}: {relay_one(client, target, body)}')
            ok += 1
        except Exception as exc:
            print(f'::error::{f}: {type(exc).__name__}: {exc}')
            failures += 1
    print(f'verified={ok} failed={failures}')
    raise SystemExit(1 if failures else 0)

if __name__ == '__main__': main()
