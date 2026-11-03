// Follow the same visible control as a learner; never force-click hidden mobile dots.
export async function selectLessonStep(page, index) {
  const selector = page.locator('[data-step-select]');
  if (await selector.isVisible()) await selector.selectOption(String(index));
  else await page.locator(`[data-step-dot="${index}"]`).click();
  await page.locator('.lesson-section').nth(index).waitFor({ state: 'visible' });
}
export async function lastLessonStep(page) {
  const count = await page.locator('[data-step-dot]').count();
  if (count) await selectLessonStep(page, count - 1);
}

/** Abre o instrumento pelo mesmo disclosure nativo que o aluno usa. */
export async function openExtraExperiments(page) {
  const extra = page.locator('.school-extra');
  if (await extra.count() && !await extra.evaluate(node => node.open)) await extra.locator(':scope > summary').click();
}
