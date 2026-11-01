import { expect, type APIRequestContext, type Page } from '@playwright/test';

const BASE = new URL(process.env.E2E_BASE_URL ?? 'http://localhost:8000');

/** Collects what would make a reviewer frown: console errors, page errors (CSP violations land here) and third-party calls. */
export function watch(page: Page, { allowStatus = [] as number[] } = {}): string[] {
  const problems: string[] = [];
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() !== 'error' && m.type() !== 'warning') return;
    // Chromium logs every non-2xx fetch as an error. The lab provokes some 4xx on purpose; allow only the listed ones.
    const status = /status of (\d{3})/.exec(m.text());
    if (status && allowStatus.includes(Number(status[1]))) return;
    problems.push(`console ${m.type()}: ${m.text()}`);
  });
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (url.protocol !== 'data:' && url.protocol !== 'blob:' && url.host !== BASE.host) {
      problems.push(`third-party request: ${r.url()}`);
    }
  });
  return problems;
}

export async function leaveSplash(page: Page): Promise<void> {
  await expect(page.locator('#splash')).toHaveCount(0, { timeout: 10_000 });
}

export async function signIn(page: Page): Promise<void> {
  await page.goto('/lab.html');
  await leaveSplash(page);
  await page.getByRole('button', { name: 'Enter the lab' }).last().click();
  await expect(page.getByRole('tab', { name: 'Gateway' })).toBeVisible();
}

const KEY = { 'x-api-key': process.env.E2E_API_KEY ?? 'change-me' };

/** The lab keeps state on the server, so every test starts from the same place: the lab's own "start over". */
export async function resetLab(request: APIRequestContext): Promise<void> {
  expect((await request.post('/v1/lab/reset', { headers: KEY })).ok()).toBeTruthy();
}

/** An approved document made through the API, with text that is unique to this run (identical content is a 409 by design). */
export async function approvedHandbook(request: APIRequestContext): Promise<string> {
  const stamp = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
  // Same handbook the lab offers as "Clean handbook", so the retrieval threshold behaves as it does for a visitor.
  const text =
    `Revision ${stamp}. Refunds are issued to the original payment method within 14 days of the request. ` +
    'Digital goods can be refunded within 30 days if they were not downloaded. ' +
    'Support answers every ticket within one business day, and urgent billing problems are escalated to the ' +
    'finance team the same day. Customers who paid by bank transfer receive the refund by transfer, and the ' +
    'confirmation e-mail lists the amount and the reference. Partial refunds are possible when only part of an ' +
    'order is returned; the shipping fee is refunded only when the item arrived damaged.';
  const made = await request.post('/v1/rag/documents', { headers: KEY, data: { source: 'docs/e2e-handbook.md', text } });
  expect(made.ok()).toBeTruthy();
  const { id } = (await made.json()) as { id: string };
  expect((await request.post(`/v1/rag/documents/${id}/approve`, { headers: KEY })).ok()).toBeTruthy();
  return stamp;
}

/** Prefix the textarea content so the ingest does not collide with an earlier run. */
export async function makeUnique(page: Page): Promise<void> {
  const area = page.getByLabel('Document text');
  await area.fill(`Run ${Date.now()}${Math.floor(Math.random() * 1000)}. ${await area.inputValue()}`);
}
