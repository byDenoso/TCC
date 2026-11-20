import { expect } from '@playwright/test';

export async function verifyExpansion(browser, base) {
  const context = await browser.newContext({ reducedMotion: 'no-preference' });
  try {
    const page = await context.newPage();
    await page.goto(base + '/');
    await page.getByRole('link', { name: 'Testar a expansão', exact: true }).click();
    await page.waitForURL('**/laboratorios/expansao/');
    await page.waitForFunction(() => document.documentElement.dataset.ready === 'true');

    const distance = page.getByRole('slider', { name: 'Distância da galáxia' });
    const hubble = page.getByRole('slider', { name: 'Constante de Hubble' });
    const plot = page.locator('.laboratory .plot');
    const point = plot.locator('.cursorpoint');
    const galaxy = page.locator('.expansion-diagram .expansion-galaxy circle').first();
    const metric = page.locator('.laboratory .metric');
    await expect(metric).toContainText('7.000');
    await expect(metric).toContainText('0,02335');
    await expect(point).toBeVisible();
    await expect(plot.locator('svg').getByText('20.000', { exact: true })).toBeVisible();
    const initialX = await point.getAttribute('cx');
    const initialY = await point.getAttribute('cy');
    const initialGalaxyX = await galaxy.getAttribute('cx');
    await distance.press('ArrowRight');
    await expect(distance).toHaveValue('101');
    await expect(metric).toContainText('7.070');
    await expect(point).not.toHaveAttribute('cx', initialX);
    await expect(point).not.toHaveAttribute('cy', initialY);
    await expect(galaxy).not.toHaveAttribute('cx', initialGalaxyX);
    const movedX = await point.getAttribute('cx');
    const movedY = await point.getAttribute('cy');
    await hubble.press('ArrowRight');
    await expect(metric).toContainText('7.171');
    await expect(point).toHaveAttribute('cx', movedX);
    await expect(point).not.toHaveAttribute('cy', movedY);
    await expect(plot.locator('svg').getByText('20.000', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Fixar referência' }).click();
    await distance.press('ArrowRight');
    const comparison = page.getByRole('slider', { name: 'Comparar referência e cenário atual' });
    const divider = page.locator('.lab-svg .expansion-divider');
    const split = await divider.getAttribute('x1');
    await comparison.press('ArrowRight');
    await expect(divider).not.toHaveAttribute('x1', split);
    const track = await comparison.boundingBox();
    const centerY = track.y + track.height / 2;
    await page.mouse.move(track.x + 0.65 * track.width, centerY);
    await page.mouse.down();
    await page.mouse.move(track.x + 0.25 * track.width, centerY, { steps: 5 });
    await page.mouse.up();
    await expect.poll(async () => Number(await comparison.inputValue())).toBeLessThan(35);
    await expect(plot.locator('.reference-point')).toBeVisible();

    const animate = page.getByRole('button', { name: 'Animar', exact: true });
    const pause = page.getByRole('button', { name: 'Pausar', exact: true });
    await animate.click();
    await expect(distance).not.toHaveValue('102');
    await pause.click();
    const pausedDistance = await distance.inputValue();
    await page.waitForTimeout(180);
    await expect(distance).toHaveValue(pausedDistance);
    await animate.click();
    await expect(pause).toBeVisible();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(animate).toBeDisabled();
    await page.getByRole('button', { name: 'Reiniciar', exact: true }).click();
    await expect(distance).toHaveValue('100');
    await expect(hubble).toHaveValue('70');
    await expect(metric).toContainText('7.000');
    await expect(comparison).toHaveCount(0);

    await page.setViewportSize({ width: 320, height: 800 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
    await expect.poll(async () => (await distance.boundingBox())?.height).toBeGreaterThanOrEqual(44);
    await distance.press('End');
    await expect(distance).toHaveValue('200');
    await expect(metric).toContainText('14.000');
  } finally {
    await context.close();
  }
}
