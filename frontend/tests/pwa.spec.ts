import { expect, test } from "@playwright/test";
import { mockApi } from "./helpers.ts";

test.use({ serviceWorkers: "allow" });

test("PWA: Manifest, Service Worker und App-Shell offline", async ({ page, context }) => {
  const manifest = await (await page.request.get("/assets/manifest.webmanifest")).json();
  expect(manifest.start_url).toBe("/assets/app.html");
  expect(manifest.display).toBe("standalone");
  expect(manifest.icons.some((icon: { sizes: string }) => icon.sizes === "512x512")).toBe(true);
  for (const icon of manifest.icons as Array<{ src: string }>) expect((await page.request.get(icon.src)).ok()).toBe(true);

  await mockApi(page, { session: "commander" });
  await page.goto("/assets/app.html");
  await expect(page.getByRole("heading", { level: 1, name: /Geräten online/ })).toBeVisible();
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  // Reload once so the page is controlled, then cut the network.
  await page.reload();
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  await context.setOffline(true);
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await page.route("**/api/v1/**", (route) => route.abort("internetdisconnected"));
  await page.reload();
  await expect(page.getByRole("heading", { name: "Server nicht erreichbar" })).toBeVisible();
  await context.setOffline(false);
});

test("Tastatur: Sprunglink zuerst, sichtbarer Fokus", async ({ page }) => {
  await mockApi(page, { session: "commander" });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: /Geräten online/ })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Zum Inhalt springen" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Tab");
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement!).outlineStyle);
  expect(outline).not.toBe("none");
});
