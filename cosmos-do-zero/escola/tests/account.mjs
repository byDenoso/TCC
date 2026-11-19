import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { chromium } from '@playwright/test';
import { Pool } from 'pg';
const dbUrl = process.env.COSMOS_TEST_DATABASE_URL;
const base = new URL(process.env.BASE_URL || 'http://127.0.0.1:4173');
if (!dbUrl || !['localhost', '127.0.0.1'].includes(base.hostname))
  throw Error('Use a instância local da escola e um banco exclusivo de teste.');
const pool = new Pool({ connectionString: dbUrl });
const name = 'browser_' + randomUUID().slice(0, 8),
  password = 'Cosmos-local-' + randomUUID();
const args = process.env.COSMOS_BROWSER_ARGS
  ? JSON.parse(await readFile(process.env.COSMOS_BROWSER_ARGS, 'utf8'))
  : [];
const b = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE || undefined, args });
const c = await b.newContext(),
  p = await c.newPage();
p.on('response', (r) => {
  if (r.url().includes('/api/school') && r.status() >= 400)
    console.log('HTTP acadêmico', r.status(), new URL(r.url()).searchParams.get('op'));
});
const open = async (path) => {
  await p.goto(new URL(path, base).href);
  await p.waitForFunction(() => document.documentElement.dataset.ready === 'true');
};
try {
  await open('/painel/');
  await p.getByRole('button', { name: 'Criar conta', exact: true }).click();
  await p.getByLabel('Nome de usuário').fill(name);
  await p.locator('input[name="password"]').fill(password);
  await p.getByRole('button', { name: 'Cadastrar', exact: true }).click();
  await p.getByRole('heading', { name: 'Conta de ' + name }).waitFor();
  const sess = (await c.cookies()).find((c) => c.name === 'cosmos_session');
  assert(sess.httpOnly && sess.sameSite === 'Lax');
  await open('/aulas/medir-com-a-luz/');
  await p.getByText('Minhas anotações', { exact: true }).click();
  await p.getByLabel('Anotação sobre a aula').fill('Registro de conta sincronizada');
  await p.getByRole('button', { name: 'Salvar anotação' }).click();
  await p.getByText('Anotação salva.', { exact: true }).waitFor();
  await open('/painel/');
  await p.getByRole('button', { name: 'Sair da conta' }).click();
  await p.getByRole('button', { name: 'Entrar', exact: true }).waitFor();
  await p.getByLabel('Nome de usuário').fill(name);
  await p.locator('input[name="password"]').fill(password);
  await p.getByRole('button', { name: 'Entrar', exact: true }).click();
  await p.getByRole('heading', { name: 'Conta de ' + name }).waitFor();
  await p.getByRole('button', { name: 'Anotações', exact: true }).click();
  await p.getByText('Registro de conta sincronizada', { exact: true }).waitFor();
  await open('/gestao/');
  await p.getByText(/O acesso exige uma conta editorial/).waitFor();
  await pool.query("UPDATE cosmos_school_users SET role='editor' WHERE name=$1", [name]);
  await open('/gestao/');
  await p.getByLabel('Identificador público').fill(name.replace('_', '-'));
  await p.getByLabel('Título', { exact: true }).fill('Medir uma distância');
  await p.getByLabel('Disciplina ou módulo').fill('Matemática básica');
  await p
    .getByLabel('Texto didático ou revisão científica')
    .fill('Uma medição de referência da sessão de teste.');
  await p.getByLabel('Referência bibliográfica (URL HTTPS)').fill('https://openstax.org/');
  for (const [label, n] of [
    ['Salvar rascunho', 1],
    ['Enviar para revisão', 2],
    ['Publicar revisão', 3],
  ]) {
    await p.getByRole('button', { name: label, exact: true }).click();
    await p
      .getByRole('status')
      .filter({ hasText: 'Versão ' + n + ' salva' })
      .waitFor();
  }
  await open('/leitura/?id=' + name.replace('_', '-'));
  await p.getByRole('heading', { name: 'Medir uma distância' }).waitFor();
  console.log(
    'Fluxo HTTP e navegador aprovado: cadastro, cookie HttpOnly, anotação, logout, nova sessão, gestão restrita, três versões e leitura pública.'
  );
} catch (e) {
  console.log(
    'Estado da página',
    await p
      .locator('main')
      .innerText()
      .catch(() => '')
  );
  throw e;
} finally {
  await b.close();
  await pool.query('DELETE FROM cosmos_school_revisions WHERE key=$1', [name.replace('_', '-')]);
  await pool.query('DELETE FROM cosmos_school_users WHERE name=$1', [name]);
  await pool.end();
}
