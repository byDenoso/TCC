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
  if (await extra.count()) {
    await extra.locator('.school-extra-content').scrollIntoViewIfNeeded();
    await page.waitForFunction(() => {
      const content = document.querySelector('.school-extra-content');
      return content && content.getClientRects().length > 0 && content.innerText.trim().length > 0;
    });
  }
}

/** Abre o resumo complementar pelo mesmo caminho que o aluno. */
export async function openLessonStory(page) {
  await openExtraExperiments(page);
  const film = page.locator('.lesson-film');
  if (await film.count() && !await film.evaluate(node => node.open)) await film.locator(':scope > summary').click();
}

/** Progresso fica no painel de percurso, sem competir com a primeira descoberta. */
export async function openJourneyProgress(page) {
  const panel = page.locator('.journey-details');
  if (!await panel.evaluate(node => node.open)) await panel.locator(':scope > summary').click();
  const label = panel.locator('[data-progress-label]');
  await label.scrollIntoViewIfNeeded();
  // details-content remains hidden during its opening transition in Firefox/WebKit.
  await page.waitForFunction(() => {
    const label = document.querySelector('.journey-details [data-progress-label]');
    return label && label.getClientRects().length > 0 && label.innerText.trim().length > 0;
  });
}
