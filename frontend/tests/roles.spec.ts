import { expect, test, type Page } from "@playwright/test";
import { mockApi } from "./helpers.ts";

/* Every page a beta tester can reach, and actions the server would reject. */
const PAGES = [
  "/#/", "/#/geraete", "/#/geraete/n-rig-win", "/#/geraete/n-rig-win?tab=sensoren", "/#/geraete/n-rig-win?tab=netzwerk",
  "/#/geraete/n-rig-win?tab=spiele", "/#/geraete/n-rig-win?tab=updates", "/#/geraete/n-rig-win?tab=verwaltung",
  "/#/hardware", "/#/spiele", "/#/chat", "/#/aufnahme", "/#/releases",
  "/#/einstellungen/konto", "/#/einstellungen/warnregeln", "/#/einstellungen/telegram", "/#/einstellungen/ueber",
];
const COMMANDER_ACTIONS = [
  /Alle quittieren/, /^Anordnen$/, /Code erstellen/, /Einladung erstellen/, /Widerrufen/, /Entfernen/, /Freigeben/,
  /Manifest registrieren/, /Warnregeln speichern/, /Testnachricht senden/, /Gerät entfernen/, /Netzwerkzähler zurücksetzen/,
  /Umbenennen/, /Konto anlegen/, /Banner hochladen/, /Zuordnung speichern/, /^Festlegen$/, /Neues physisches Gerät/,
  /Ablehnen/, /^Suchen$/, /Banner übernehmen/,
];

async function enabledActions(page: Page): Promise<string[]> {
  const found: string[] = [];
  for (const pattern of COMMANDER_ACTIONS) {
    const buttons = page.getByRole("button", { name: pattern });
    const count = await buttons.count();
    for (let index = 0; index < count; index += 1) {
      const button = buttons.nth(index);
      if ((await button.isVisible()) && (await button.isEnabled())) found.push(`${pattern} (${await button.textContent()})`);
    }
  }
  return found;
}

test("Beta-Tester: Badge sichtbar, keine aktive Aktion, die der Server ablehnt", async ({ page }) => {
  test.setTimeout(90_000);
  const mock = await mockApi(page, { session: "beta_tester" });
  await page.goto("/");
  await expect(page.locator(".bar").getByText("Beta-Tester")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Bereiche" }).getByText("Beta-Tester · nur lesen")).toBeVisible();
  for (const path of PAGES) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("main")).not.toContainText("Lädt …");
    expect(await enabledActions(page), `auf ${path}`).toEqual([]);
  }
  // Gaming Mode is the one switch beta testers may use (access.gaming_mode_node).
  await page.goto("/#/geraete/n-kalle");
  await page.getByRole("button", { name: /^Gaming/ }).click();
  await page.getByRole("menuitem", { name: "1 Stunde" }).click();
  await expect(page.getByText(/Gaming Mode für Kalle-PC bis/)).toBeVisible();
  // Rejecting pairings stays with commanders.
  await page.goto("/#/aufnahme");
  await expect(page.getByRole("button", { name: "Ablehnen" })).toHaveCount(0);
  // The commander-only settings tab does not exist for beta testers.
  await page.goto("/#/einstellungen/konten");
  await expect(page.getByRole("link", { name: "Konten & Einladungen" })).toHaveCount(0);
  // The whole crawl never triggered a 403.
  expect(mock.log.filter((entry) => entry.status === 403)).toEqual([]);
});

test("Commander sieht die Verwaltungsaktionen", async ({ page }) => {
  await mockApi(page, { session: "commander" });
  await page.goto("/#/aufnahme");
  await expect(page.getByRole("button", { name: "Code erstellen" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Freigeben" })).toBeEnabled();
  await page.goto("/#/");
  await expect(page.getByRole("button", { name: "Alle quittieren" })).toBeVisible();
});

test("Admin-Code wird genau einmal angezeigt", async ({ page }) => {
  await mockApi(page, { session: "commander" });
  await page.goto("/#/aufnahme");
  await page.getByLabel("Wofür?").fill("Kalles Laptop");
  await page.getByRole("button", { name: "Code erstellen" }).click();
  const secret = page.getByRole("group", { name: /Code für Kalles Laptop/ });
  await expect(secret).toContainText("Q7W2KX9P");
  await expect(secret).toContainText("wird nur jetzt angezeigt");
  await expect(secret.getByRole("button", { name: "Kopieren" })).toBeVisible();
  await page.getByRole("button", { name: "Weitergegeben, ausblenden" }).click();
  await expect(page.getByText("Q7W2KX9P")).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "Kalles Laptop" })).toBeVisible();
});

test("Freund sieht nur eigene Geräte und keine Team-Bereiche", async ({ page }) => {
  const mock = await mockApi(page, { session: "friend" });
  await page.goto("/#/geraete");
  await expect(page.getByRole("link", { name: "Mia-Box" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Kalle-PC" })).toHaveCount(0);
  for (const name of ["Aufnahme", "Releases"]) await expect(page.getByRole("navigation", { name: "Bereiche" }).getByRole("link", { name })).toHaveCount(0);
  // Friends manage their own device.
  await page.goto("/#/geraete/n-mia");
  await expect(page.getByRole("button", { name: /Gaming/ })).toBeEnabled();
  expect(mock.log.filter((entry) => entry.status === 403)).toEqual([]);
});

test("Commander lehnt eine Kopplung ab und wählt einen SteamGridDB-Banner", async ({ page }) => {
  const mock = await mockApi(page, { session: "commander" });
  await page.goto("/#/aufnahme");
  const waiting = page.getByRole("listitem").filter({ hasText: "Jonas-PC" });
  await waiting.getByRole("button", { name: "Ablehnen" }).click();
  await expect(page.getByText(/Anfrage von Jonas-PC abgelehnt/)).toBeVisible();
  expect(mock.data.pairings.find((item) => item.display_name === "Jonas-PC")?.status).toBe("cancelled");

  await page.goto("/#/spiele");
  await page.locator(".library").getByRole("button", { name: /World of Warcraft/ }).click();
  const dialog = page.getByRole("dialog", { name: "World of Warcraft" });
  await dialog.getByRole("button", { name: "Suchen" }).click();
  await dialog.getByRole("radio", { name: /Banner 2/ }).check({ force: true });
  await dialog.getByRole("button", { name: "Diesen Banner übernehmen" }).click();
  await expect(page.getByText("Banner von SteamGridDB übernommen.")).toBeVisible();
  expect(mock.log.some((entry) => entry.method === "POST" && entry.path.endsWith("/artwork/candidates/1"))).toBe(true);
});
