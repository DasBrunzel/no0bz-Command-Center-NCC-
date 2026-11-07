import { devices, expect, test } from "@playwright/test";
import { mockApi } from "./helpers.ts";

/*
 * Visual review run, not part of the default suite:
 *   SCREENS=1 pnpm exec playwright test screens
 * Writes PNGs to test-results/screens/.
 */
test.skip(!process.env.SCREENS, "only with SCREENS=1");

const VIEWS: Array<[string, string]> = [
  ["lage", "/#/"], ["geraete", "/#/geraete"], ["detail", "/#/geraete/n-rig-win"], ["detail-sensoren", "/#/geraete/n-rig-win?tab=sensoren"],
  ["detail-netzwerk", "/#/geraete/n-rig-win?tab=netzwerk"], ["detail-spiele", "/#/geraete/n-rig-win?tab=spiele"], ["detail-updates", "/#/geraete/n-rig-win?tab=updates"],
  ["detail-verwaltung", "/#/geraete/n-rig-win?tab=verwaltung"], ["unraid", "/#/geraete/n-tower"], ["offline-node", "/#/geraete/n-lappi"], ["hardware", "/#/hardware"],
  ["spiele", "/#/spiele"], ["chat", "/#/chat"], ["aufnahme", "/#/aufnahme"], ["releases", "/#/releases"],
  ["konto", "/#/einstellungen/konto"], ["konten", "/#/einstellungen/konten"], ["warnregeln", "/#/einstellungen/warnregeln"], ["telegram", "/#/einstellungen/telegram"],
];

for (const scheme of ["light", "dark"] as const) {
  test(`Ansichten ${scheme}`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await mockApi(page, { session: "commander" });
    for (const [name, path] of VIEWS) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1200);
      await page.screenshot({ path: `test-results/screens/${scheme}-${name}.png`, fullPage: true });
    }
  });
}

test("Login und Zustände", async ({ page }) => {
  test.setTimeout(60_000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockApi(page);
  await page.goto("/");
  await page.screenshot({ path: "test-results/screens/state-login.png" });
  await page.goto("/?pair=pair-waiting-123456");
  await page.screenshot({ path: "test-results/screens/state-login-pair.png" });
});

test("Leer", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockApi(page, { session: "commander", empty: true });
  for (const [name, path] of [["lage", "/#/"], ["spiele", "/#/spiele"], ["chat", "/#/chat"], ["aufnahme", "/#/aufnahme"], ["releases", "/#/releases"], ["hardware", "/#/hardware"]]) {
    await page.goto(path!);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `test-results/screens/empty-${name}.png`, fullPage: true });
  }
});

test("Fehler und Laden", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockApi(page, { session: "commander", failing: /^\/fleet\/(nodes|games|chat)/ });
  for (const [name, path] of [["lage", "/#/"], ["spiele", "/#/spiele"], ["chat", "/#/chat"]]) {
    await page.goto(path!);
    await expect(page.getByRole("alert").first()).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: `test-results/screens/error-${name}.png` });
  }
});

test("Laden", async ({ page }) => {
  await mockApi(page, { session: "commander" }, { delay: 2500 });
  await page.goto("/#/spiele");
  await page.waitForTimeout(3200);
  await page.screenshot({ path: "test-results/screens/loading-spiele.png" });
});

const { defaultBrowserType: _browser, ...phone } = devices["Pixel 7"];
test.describe("mobil", () => {
  test.use(phone);
  test("Ansichten mobil", async ({ page }) => {
    test.setTimeout(90_000);
    await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
    await mockApi(page, { session: "commander" });
    for (const [name, path] of [["lage", "/#/"], ["geraete", "/#/geraete"], ["detail", "/#/geraete/n-kalle"], ["spiele", "/#/spiele"], ["chat", "/#/chat"], ["aufnahme", "/#/aufnahme"]]) {
      await page.goto(path!);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1200);
      await page.screenshot({ path: `test-results/screens/mobile-${name}.png`, fullPage: name !== "chat" });
    }
  });
});
