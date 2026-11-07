import { devices, expect, test } from "@playwright/test";
import { mockApi } from "./helpers.ts";

test.use({ ...devices["Pixel 7"], colorScheme: "light" });

test("Mobil: Warnungen, Gaming Mode und Chat", async ({ page }) => {
  const mock = await mockApi(page, { session: "commander" });
  await page.goto("/");
  const tabbar = page.getByRole("navigation", { name: "Bereiche (mobil)" });
  await expect(tabbar).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Bereiche", exact: true })).toBeHidden();
  // No horizontal scrolling on a phone.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

  // Alerts from the status bar
  await page.getByRole("button", { name: /aktive Warnungen anzeigen/ }).click();
  const popover = page.locator("#alerts-popover");
  await expect(popover).toBeVisible();
  await expect(popover).toContainText("Tower");
  await popover.getByRole("link", { name: /Kalle-PC/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Kalle-PC" })).toBeVisible();

  // Gaming Mode toggle
  await page.getByRole("button", { name: /^Gaming/ }).click();
  await page.getByRole("menuitem", { name: "2 Stunden" }).click();
  await expect(page.getByText(/Gaming Mode für Kalle-PC bis/)).toBeVisible();
  expect(mock.data.nodes.find((node) => node.node_id === "n-kalle")?.gaming_mode_until).toBeTruthy();

  // Chat
  await tabbar.getByRole("link", { name: "Chat" }).click();
  await expect(page.getByRole("log", { name: "Nachrichten" })).toContainText("Deep Rock");
  await page.getByRole("textbox", { name: "Nachricht" }).fill("Bin dabei!");
  await page.getByRole("button", { name: "Senden" }).click();
  await expect(page.getByRole("log", { name: "Nachrichten" })).toContainText("Bin dabei!");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test("Mobil: Mehr-Menü erreicht die übrigen Bereiche", async ({ page }) => {
  await mockApi(page, { session: "commander" });
  await page.goto("/");
  await page.getByRole("button", { name: "Mehr" }).click();
  await page.locator("#more-popover").getByRole("link", { name: "Einstellungen" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Einstellungen" })).toBeVisible();
});
