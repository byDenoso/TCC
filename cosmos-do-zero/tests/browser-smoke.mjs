import assert from 'node:assert/strict';
import { firefox, webkit } from 'playwright';

const base = process.env.BASE_URL ?? 'http://127.0.0.1:4321';
const first = '/capitulos/galaxias-e-nebulosas/';
const second = '/capitulos/origem-do-universo/';
const third = '/capitulos/misterios-do-cosmos/';
let checks = 0;
const failures = [];
const check = (name, condition) => { assert.ok(condition, name); checks++; };

for (const [name, engine] of Object.entries({ firefox, webkit })) {
  let browser;
  try {
    browser = await engine.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(base, { waitUntil: 'networkidle' });
    check(`${name}: primeira etapa`, (await page.locator('[data-start-journey]').getAttribute('href')).includes(first));
    check(`${name}: três etapas principais`, await page.locator('#capitulos [data-journey]').count() === 3);
    check(`${name}: sem rolagem horizontal no celular`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.locator('[data-start-journey]').click();
    await page.locator('[data-scene="scale"]').waitFor();
    await page.locator('[data-scale-step="3"]').click();
    check(`${name}: contexto da escala selecionada`, /2,5 milhões/.test(await page.locator('[data-scale-panel="3"]').innerText()));
    const light = page.locator('[data-light-play]');
    await light.click();
    check(`${name}: viagem da luz iniciada`, await light.getAttribute('aria-pressed') === 'true');
    await light.click();
    check(`${name}: viagem da luz pausada`, await light.getAttribute('aria-pressed') === 'false');
    const quiz = page.locator('.chapter-check [data-quiz]');
    for (let i = 0; i < 3; i++) {
      await quiz.locator('[data-answer]').first().click();
      check(`${name}: feedback da pergunta ${i + 1}`, (await quiz.locator('[data-quiz-feedback]').innerText()).length > 20);
      const next = quiz.locator('[data-quiz-next]');
      if (await next.isVisible()) await next.click();
    }
    check(`${name}: resultado das três perguntas`, /\d+\s*(de|\/)\s*3/.test(await quiz.innerText()));
    await page.locator('[data-complete]').click();
    await page.goto(base, { waitUntil: 'networkidle' });
    check(`${name}: progresso após navegar`, /1 de 3/.test(await page.locator('[data-progress-label]').first().innerText()));
    await page.reload({ waitUntil: 'networkidle' });
    check(`${name}: progresso após recarregar`, /1 de 3/.test(await page.locator('[data-progress-label]').first().innerText()));
    await page.goto(base + second, { waitUntil: 'networkidle' });
    const exp = page.locator('[data-station="expansao"]');
    const snapshot = () => exp.locator('.e-galaxy').evaluateAll((n) => n.map((x) => x.getAttribute('transform')).join('|'));
    const before = await snapshot();
    await exp.locator('.e-galaxy[role=button]').nth(3).click({ force: true });
    check(`${name}: trocar observador muda o referencial`, await snapshot() !== before);
    check(`${name}: observador fica no centro`, await exp.locator('.e-galaxy.is-observer').getAttribute('transform') === 'translate(320.00 200.00)');
    await exp.locator('[data-e-range]').evaluate((input) => { input.value = '1.4'; input.dispatchEvent(new Event('input', { bubbles: true })); });
    check(`${name}: expansão altera a escala`, /1,40/.test(await exp.locator('[data-e-scale]').innerText()));
    await page.getByRole('link', { name: /Próximo:/ }).click();
    check(`${name}: ordem da viagem preservada`, page.url().includes(third));
    await page.locator('[data-evidence-select="2"]').click();
    check(`${name}: limite da interpretação disponível`, /desconhecida|desconhecemos|não houve/i.test(await page.locator('[data-evidence-panel="2"]').innerText()));
    await page.setViewportSize({ width: 1280, height: 900 });
    check(`${name}: sem rolagem horizontal no desktop`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    check(`${name}: ausência de erros JavaScript`, errors.length === 0);
    await context.close();

    const failedStorage = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const blocked = await failedStorage.newPage();
    await blocked.addInitScript(() => {
      localStorage.setItem('cosmos-v3-progress', '[]');
      Object.defineProperty(Storage.prototype, 'setItem', { value() { throw new DOMException('quota', 'QuotaExceededError'); } });
    });
    await blocked.goto(base + first, { waitUntil: 'networkidle' });
    await blocked.locator('[data-complete]').click();
    check(`${name}: leitura antiga não apaga gravação que falhou`, await blocked.locator('[data-complete]').getAttribute('aria-pressed') === 'true');
    check(`${name}: aviso de progresso da sessão`, /sessão/.test(await blocked.locator('[data-complete-status]').innerText()));
    await blocked.locator('[data-complete]').click();
    check(`${name}: desmarcação com gravação falhando`, await blocked.locator('[data-complete]').getAttribute('aria-pressed') === 'false');
    await blocked.locator('[data-light-play]').click();
    check(`${name}: alternativa sem animação`, /Movimento reduzido/.test(await blocked.locator('[data-light-status]').innerText()));
    await failedStorage.close();
    console.log(`${name}: fluxo principal, cenas, quiz, progresso e falha de gravação passaram.`);
  } catch (error) {
    failures.push(`${name}: ${error.message}`);
    console.error(`${name}: verificações interrompidas: ${error.message}`);
  } finally { if (browser) await browser.close(); }
}
if (failures.length) {
  console.error(`${checks} verificações concluídas; ${failures.length} navegador(es) com falha ou bloqueio.`);
  process.exitCode = 1;
} else console.log(`${checks} verificações de Firefox/WebKit passaram.`);
