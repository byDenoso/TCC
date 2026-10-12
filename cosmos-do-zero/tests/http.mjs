import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const serverScript = join(projectRoot, 'scripts', 'serve-dist.mjs');
const fixtureRoot = await mkdtemp(join(tmpdir(), 'cosmos-http-'));
const distRoot = join(fixtureRoot, 'dist');
const siblingRoot = join(fixtureRoot, 'dist-evil');
await mkdir(join(distRoot, 'nested'), { recursive: true });
await mkdir(siblingRoot, { recursive: true });
await writeFile(join(distRoot, 'index.html'), '<h1>home</h1>');
await writeFile(join(distRoot, 'nested', 'index.html'), '<h1>nested</h1>');
await writeFile(join(distRoot, 'asset.json'), '{"ok":true}');
await writeFile(join(distRoot, '404.html'), '<h1>not found</h1>');
await writeFile(join(siblingRoot, 'secret.txt'), 'outside dist secret');

let child;
let stderr = '';
try {
  child = spawn(process.execPath, [serverScript, '0'], {
    cwd: projectRoot,
    env: { ...process.env, DIST: distRoot },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', (chunk) => { stderr += chunk; });

  const base = await new Promise((resolveAddress, reject) => {
    let output = '';
    const timeout = setTimeout(() => reject(new Error(`server did not start: ${output}${stderr}`)), 5000);
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      output += chunk;
      const match = output.match(/http:\/\/127\.0\.0\.1:(\d+)\//);
      if (match) {
        clearTimeout(timeout);
        resolveAddress(`http://127.0.0.1:${match[1]}`);
      }
    });
    child.once('error', (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    child.once('exit', (code) => {
      clearTimeout(timeout);
      reject(new Error(`server exited before listening (${code}): ${stderr}`));
    });
  });

  const home = await fetch(`${base}/`);
  assert.equal(home.status, 200);
  assert.match(home.headers.get('content-type') ?? '', /^text\/html; charset=utf-8/);
  assert.equal(await home.text(), '<h1>home</h1>');

  const nested = await fetch(`${base}/nested/`);
  assert.equal(nested.status, 200);
  assert.equal(await nested.text(), '<h1>nested</h1>');

  const missing = await fetch(`${base}/no-such-page`);
  assert.equal(missing.status, 404);
  assert.match(missing.headers.get('content-type') ?? '', /^text\/html; charset=utf-8/);
  assert.equal(await missing.text(), '<h1>not found</h1>');

  const head = await fetch(`${base}/asset.json`, { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.match(head.headers.get('content-type') ?? '', /^application\/json; charset=utf-8/);
  assert.ok(Number(head.headers.get('content-length')) > 0);
  assert.equal(await head.text(), '');

  const unsupported = await fetch(`${base}/`, { method: 'POST' });
  assert.equal(unsupported.status, 405);
  assert.equal(unsupported.headers.get('allow'), 'GET, HEAD');

  const malformed = await fetch(`${base}/%E0%A4%A`);
  assert.equal(malformed.status, 400);
  const nullByte = await fetch(`${base}/bad%00path`);
  assert.equal(nullByte.status, 400);

  // Encoded separators keep this traversal intact through URL parsing; decoding
  // it produces a sibling path whose name shares the dist root prefix.
  const traversal = await fetch(`${base}/%2e%2e%2fdist-evil%2fsecret.txt`);
  assert.equal(traversal.status, 403);
  assert.doesNotMatch(await traversal.text(), /outside dist secret/);

  const stillAlive = await fetch(`${base}/`);
  assert.equal(stillAlive.status, 200, 'malformed requests must not crash the server');
  console.log('HTTP server checks passed (GET, HEAD, 404/MIME, method handling, malformed URL, path containment).');
} catch (error) {
  console.error(error);
  if (stderr) console.error(stderr);
  process.exitCode = 1;
} finally {
  if (child && child.exitCode === null) {
    child.kill();
    await new Promise((resolveExit) => child.once('exit', resolveExit));
  }
  await rm(fixtureRoot, { recursive: true, force: true });
}
