import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { approvedHandbook, leaveSplash, makeUnique, resetLab, signIn, watch } from './helpers';

const tab = (page: Page, name: string) => page.getByRole('tab', { name });
const provider = (page: Page, name: string) =>
  page.locator('.box').filter({ has: page.getByRole('heading', { name: 'Providers', exact: true }) }).locator('li', { hasText: name });

test.describe('lab', () => {
  test.beforeEach(async ({ request }) => {
    await resetLab(request);
  });

  test('refuses a wrong key and says so', async ({ page }) => {
    await page.goto('/lab.html');
    await leaveSplash(page);
    await page.getByLabel('API key').fill('definitely-not-the-key');
    await page.getByRole('button', { name: 'Enter the lab' }).last().click();
    await expect(page.getByText('That key was not accepted.')).toBeVisible();
    await expect(tab(page, 'Gateway')).toHaveCount(0);
  });

  test('start over wipes the demo: documents, inbox, outages', async ({ page, request }) => {
    await approvedHandbook(request);
    await signIn(page);
    await provider(page, 'demo-local').getByRole('button', { name: 'Switch off' }).click();
    await page.getByRole('button', { name: 'Start over' }).click();
    await expect(page.getByText('Back to a clean slate.')).toBeVisible();
    await expect(provider(page, 'demo-local')).toContainText('running');
    await tab(page, 'Knowledge').click();
    await expect(page.getByText('No documents yet. Ingest one on the left.')).toBeVisible();
  });

  test('make it leak: with the local model down, personal data is refused and the cloud inbox stays empty', async ({ page }) => {
    const problems = watch(page, { allowStatus: [503] });
    await signIn(page);
    await page.getByRole('button', { name: 'Contains an e-mail' }).click();

    // 1. the local model is healthy: it answers and the cloud is skipped
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Answered' })).toBeVisible();
    await expect(page.getByText('demo-local (local)')).toBeVisible();
    await expect(page.getByText('skipped_sensitive')).toBeVisible();

    // 2. the local model is switched off: the answer is a refusal, not a leak
    await provider(page, 'demo-local').getByRole('button', { name: 'Switch off' }).click();
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await expect(page.getByRole('heading', { name: /Refused · 503/ })).toBeVisible();
    await page.getByRole('button', { name: 'Refresh' }).click();
    await expect(page.getByText('Empty: the simulated third-party API has received nothing.')).toBeVisible();

    // 3. only content the owner marked as internal may leave, and only as a placeholder
    await page.getByLabel('Sensitivity').selectOption('internal');
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Answered' })).toBeVisible();
    await page.getByRole('button', { name: 'Refresh' }).click();
    const inbox = page.locator('.box', { hasText: 'Cloud inbox' });
    await expect(inbox).toContainText('<EMAIL_1>');
    await expect(inbox).not.toContainText('ana.souza@example.com');

    await provider(page, 'demo-local').getByRole('button', { name: 'Switch on' }).click();
    expect(problems).toEqual([]);
  });

  test('break the breaker: repeated failures open it, and the operator can close it', async ({ page }) => {
    await signIn(page);
    await page.getByRole('button', { name: 'Plain question' }).click();
    await provider(page, 'demo-local').getByRole('button', { name: 'Switch off' }).click();
    await provider(page, 'demo-cloud').getByRole('button', { name: 'Switch off' }).click();
    for (let i = 0; i < 3; i += 1) {
      await page.getByRole('button', { name: 'Send', exact: true }).click();
      await expect(page.getByRole('heading', { name: /Refused/ })).toBeVisible();
    }
    await expect(provider(page, 'demo-local')).toContainText('breaker open');
    await provider(page, 'demo-local').getByRole('button', { name: 'Switch on' }).click();
    await provider(page, 'demo-cloud').getByRole('button', { name: 'Switch on' }).click();
    await page.getByRole('button', { name: 'Reset breakers' }).click();
    await expect(provider(page, 'demo-local')).toContainText('breaker closed');
  });

  test('poison the index: the hostile chunk is excluded, the rest answers with a citation, off-topic gets no model call', async ({ page }) => {
    await signIn(page);
    await tab(page, 'Knowledge').click();
    await page.getByRole('button', { name: 'Poisoned handbook' }).click();
    await makeUnique(page);
    await page.getByRole('button', { name: 'Ingest', exact: true }).click();
    await expect(page.getByText(/1 chunk\(s\) excluded/)).toBeVisible();
    await expect(page.getByText('Only the offsets of an excluded chunk are kept, never its text.')).toBeVisible();

    // nothing is retrievable before a person approves
    await page.getByRole('button', { name: 'How long do refunds take?' }).click();
    await page.getByRole('button', { name: 'Ask', exact: true }).click();
    await expect(page.locator('.box', { hasText: 'Answer' }).getByText(/answered/)).toHaveCount(0);

    await page.getByRole('button', { name: 'Approve' }).first().click();
    await page.getByRole('button', { name: 'Ask', exact: true }).click();
    const answer = page.locator('.box.arrive', { hasText: 'Answer' });
    await expect(answer).toContainText('answered');
    await expect(answer).toContainText('docs/refunds-poisoned.md');
    await expect(answer).not.toContainText(/ignore all previous instructions/i);

    await page.getByRole('button', { name: 'What is the capital of France?' }).click();
    await page.getByRole('button', { name: 'Ask', exact: true }).click();
    await expect(page.locator('.box.arrive', { hasText: 'No citations' })).toBeVisible();
  });

  test('a secret in a document is redacted before it is embedded', async ({ page }) => {
    await signIn(page);
    await tab(page, 'Knowledge').click();
    await page.getByRole('button', { name: 'Contains a secret' }).click();
    await makeUnique(page);
    await page.getByRole('button', { name: 'Ingest', exact: true }).click();
    await expect(page.getByText(/1 secret\(s\) redacted before embedding/)).toBeVisible();
  });

  test('replay a webhook: signed once, counted once; tampered, back-dated, wrong-secret and unsigned are all refused', async ({ page }) => {
    const problems = watch(page, { allowStatus: [401] });
    await signIn(page);
    await tab(page, 'Webhooks').click();
    const responses = page.locator('.box', { hasText: 'Responses' });

    await page.getByRole('button', { name: 'Send valid' }).click();
    await expect(responses.getByText('valid signature')).toBeVisible();
    await expect(responses.locator('li').first()).toContainText('202');

    await page.getByRole('button', { name: /Send again/ }).click();
    await expect(responses.locator('li').first()).toContainText('200');
    await expect(responses.locator('li').first()).toContainText('duplicate');

    const refused = [
      ['Tamper with the body', 'body edited after signing'],
      ['Back-date the timestamp', 'timestamp from an hour ago'],
      ['Wrong secret', 'signed with another secret'],
      ['No signature', 'no signature header'],
    ] as const;
    const reasons = new Set<string>();
    for (const [button, label] of refused) {
      await page.getByRole('button', { name: button }).click();
      const first = responses.locator('li').first();
      await expect(first).toContainText(label);
      await expect(first).toContainText('401');
      reasons.add((await first.innerText()).split('\n').pop() ?? '');
    }
    expect(reasons.size).toBe(1); // one generic message: the response is not an oracle
    expect(problems).toEqual([]);
  });

  test('pause for a human: personal data is masked, the draft waits, and a person releases it', async ({ page, request }) => {
    await approvedHandbook(request); // the curation click itself is covered by the poisoned-document test
    await signIn(page);
    await tab(page, 'Review').click();
    await page.getByRole('button', { name: 'Start the review' }).click();
    const run = page.locator('.box.arrive', { hasText: 'Run' });
    await expect(run).toContainText('awaiting_review');
    await expect(run).toContainText('<EMAIL_1>');
    await expect(run).not.toContainText('ana.souza@example.com');
    await page.getByRole('button', { name: 'Approve' }).click();
    await expect(page.locator('.box.arrive', { hasText: 'Run' })).toContainText('approved');
    await expect(page.getByRole('heading', { name: 'Released text' })).toBeVisible();
  });
});

for (const scheme of ['light', 'dark'] as const) {
  test(`accessibility: sign-in and every lab tab have no WCAG A/AA violations (${scheme})`, async ({ browser }) => {
    const context = await browser.newContext({ colorScheme: scheme, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const scan = async (where: string) => {
      const r = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      expect(r.violations.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
    };
    await page.goto('/lab.html');
    await leaveSplash(page);
    await scan('sign-in');
    await page.getByRole('button', { name: 'Enter the lab' }).last().click();
    for (const name of ['Gateway', 'Knowledge', 'Webhooks', 'Review']) {
      await tab(page, name).click();
      await scan(name);
    }
    await context.close();
  });
}
