import { expect, test } from "@playwright/test";

/*
 * Smoke run against a real NCC server (not the mock), e.g. before going live:
 *   LIVE_URL=http://127.0.0.1:8370 pnpm exec playwright test live
 * Needs a session the server accepts without login (loopback commander) or
 * LIVE_TOKEN for the legacy dashboard token. Fails on CSP violations, console
 * errors and any 5xx response.
 */
const base = process.env.LIVE_URL;
test.skip(!base, "only with LIVE_URL");
test.use({ baseURL: base, serviceWorkers: "allow" });

const ROUTES = ["/#/", "/#/geraete", "/#/hardware", "/#/spiele", "/#/chat", "/#/aufnahme", "/#/releases",
  "/#/einstellungen/konto", "/#/einstellungen/konten", "/#/einstellungen/warnregeln", "/#/einstellungen/telegram", "/#/einstellungen/ueber"];

test("Echter Server: alle Bereiche ohne CSP-Verstoß, Konsolenfehler oder 5xx", async ({ page }) => {
  test.setTimeout(120_000);
  const problems: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") problems.push(`console: ${message.text()}`); });
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  page.on("response", (response) => { if (response.status() >= 500) problems.push(`HTTP ${response.status()} ${response.url()}`); });

  if (process.env.LIVE_TOKEN) {
    await page.goto("/");
    await page.getByText("Alte Installation mit Dashboard-Token?").click();
    await page.getByLabel("Dashboard-Token").fill(process.env.LIVE_TOKEN);
    await page.getByRole("button", { name: "Mit Token verbinden" }).click();
  }
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const routes = [...ROUTES];
  const nodeLink = page.locator("a.block-link").first();
  if (await nodeLink.count()) {
    const href = (await nodeLink.getAttribute("href"))!;
    routes.push(`/${href}`, ...["sensoren", "netzwerk", "spiele", "updates", "verwaltung"].map((tab) => `/${href}?tab=${tab}`));
  }
  for (const route of routes) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("main")).toBeVisible();
  }
  await page.goto("/");
  await expect.poll(() => page.evaluate(async () => (await navigator.serviceWorker.getRegistration("/"))?.active?.scriptURL ?? null), { timeout: 15_000 }).toContain("/sw.js");
  expect(problems).toEqual([]);
});
