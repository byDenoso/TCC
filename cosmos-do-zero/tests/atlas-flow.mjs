import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = process.env.BASE_URL || 'http://127.0.0.1:4173';
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
});

try {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const mobile = viewport.width < 500;
    const context = await browser.newContext({ viewport, isMobile: mobile, hasTouch: mobile, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const errors = [];
    const models = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (r.url().includes('/models/parallax/')) models.push(r.url()); });
    await page.goto(base);
    const fits = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    assert(await fits(), 'Capa cabe na janela');
    await page.locator('[data-pick-plate="1"]').click();
    assert(await page.locator('[data-plate="1"]').isVisible(), 'Troca de prancha');
    await page.locator('.atlas-front [data-start-journey]').click();
    await page.locator('[data-step-select]').waitFor({ state: 'attached' });
    const firstUrl = page.url();
    await page.locator('.atlas-contents summary').click();
    await page.locator('.atlas-contents ol a').nth(1).click();
    const savedSection = new URL(page.url()).hash;
    assert(savedSection.includes('galaxias-e-nebulosas-'));
    await page.locator('.atlas-fieldnote a').click();
    assert(new URL(page.url()).pathname.endsWith('/laboratorio/'));
    const instrument = page.locator('#paralaxe');
    await instrument.waitFor();
    const slider = instrument.locator('input[type=range]').first();
    const before = await slider.inputValue();
    await slider.focus();
    await slider.press('ArrowRight');
    assert.notEqual(await slider.inputValue(), before, 'Regulagem pelo teclado');
    assert(await slider.evaluate(el => el.matches(':focus-visible')), 'Foco visível no instrumento');
    assert(!models.some(url => url.endsWith('.glb')), 'O percurso 2D não requisita o GLB');
    assert(await fits(), 'Bancada cabe na janela');
    const links = page.getByRole('navigation', { name: 'Após o experimento de Paralaxe estelar' });
    await links.getByRole('link', { name: 'Voltar à leitura' }).click();
    assert.equal(new URL(page.url()).hash, savedSection);
    await page.locator('.atlas-fieldnote a').click();
    await links.getByRole('link', { name: 'Próxima aula' }).click();
    assert(new URL(page.url()).pathname.includes('origem-do-universo'));
    await page.locator('[data-step-select]').waitFor({ state: 'attached' });
    await page.locator('.site-header .identity').click();
    const resume = page.locator('.atlas-front [data-start-journey]');
    await page.getByRole('link', { name: /Retomar aula/ }).first().waitFor({ state: 'attached' });
    assert.match(await resume.innerText(), /Retomar aula/);
    await resume.click();
    assert(new URL(page.url()).hash.startsWith('#origem-do-universo-'), 'Retomada no primeiro passo da segunda aula');
    await page.locator('[data-step-next]').click();
    const nextStep = new URL(page.url()).hash;
    await page.locator('.site-header .identity').click();
    await resume.click();
    assert.equal(new URL(page.url()).hash, nextStep, 'Retomada do passo avançado');
    await page.reload();
    assert(await page.locator(nextStep).isVisible());
    await page.locator('.atlas-inline-bench a[href="#checagem"]').click();
    const quiz = page.locator('#checagem');
    await quiz.locator('[data-answer]').first().click();
    await quiz.locator('[data-quiz-feedback]').waitFor();
    assert(await fits(), 'Leitura e checagem cabem na janela');
    assert.deepEqual(errors, [], 'Erros de execução');
    console.log(JSON.stringify({viewport, primeiraAula:firstUrl, retorno:savedSection, retomada:nextStep, erros:errors.length}));
    await context.close();
  }
} finally {
  await browser.close();
}
