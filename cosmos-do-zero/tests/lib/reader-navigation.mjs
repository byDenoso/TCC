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
