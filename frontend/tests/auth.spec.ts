import { expect, test } from "@playwright/test";
import { CREDENTIALS } from "./mock/api.ts";
import { mockApi } from "./helpers.ts";

test.describe("Login", () => {
  test("Konto: Benutzername und Passwort", async ({ page }) => {
    const mock = await mockApi(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Anmelden" })).toBeVisible();
    await page.getByLabel("Benutzername").fill(CREDENTIALS.commander.username);
    await page.getByLabel("Passwort").fill("falsch-falsch-falsch");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Benutzername oder Passwort stimmt nicht" })).toBeVisible();

    await page.getByLabel("Passwort").fill(CREDENTIALS.commander.password);
    await page.getByRole("button", { name: "Anmelden" }).click();
    await expect(page.getByRole("heading", { level: 1, name: /Geräten online/ })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Bereiche" }).getByText("bruno")).toBeVisible();
    expect(mock.log.some((entry) => entry.path === "/users/login" && entry.status === 200)).toBe(true);
  });

  test("Admin-Code: 8 Zeichen", async ({ page }) => {
    const mock = await mockApi(page);
    await page.goto("/");
    await page.getByRole("radio", { name: "Admin-Code" }).check({ force: true });
    const input = page.getByRole("textbox", { name: /^Admin-Code/ });
    await input.fill("abcd23");
    await expect(page.getByRole("button", { name: "Code einlösen" })).toBeDisabled();
    await input.fill(CREDENTIALS.adminCode.toLowerCase());
    await expect(input).toHaveValue(CREDENTIALS.adminCode);
    await page.getByRole("button", { name: "Code einlösen" }).click();
    await expect(page.getByRole("heading", { level: 1, name: /Geräten online/ })).toBeVisible();
    expect(mock.log.find((entry) => entry.path === "/admin-codes/redeem")?.status).toBe(200);
  });

  test("Registrierung mit Einladungscode", async ({ page }) => {
    const mock = await mockApi(page);
    await page.goto("/");
    await page.getByRole("radio", { name: "Registrieren" }).check({ force: true });
    await expect(page.getByRole("heading", { name: "Konto anlegen" })).toBeVisible();
    await page.getByLabel("Einladungscode").fill(CREDENTIALS.invite);
    await page.getByRole("textbox", { name: /^Benutzername/ }).fill("jonas");
    await page.locator('input[name="new-password"]').fill("jonas-hat-ein-langes-pw");
    await page.getByLabel("Passwort wiederholen").fill("jonas-hat-ein-anderes");
    await expect(page.getByText("Die Passwörter sind nicht gleich.")).toBeVisible();
    await page.getByLabel("Passwort wiederholen").fill("jonas-hat-ein-langes-pw");
    await page.getByRole("button", { name: "Konto anlegen und anmelden" }).click();
    await expect(page.getByRole("navigation", { name: "Bereiche" }).getByText("jonas")).toBeVisible();
    // A friend sees no team areas.
    await expect(page.getByRole("navigation", { name: "Bereiche" }).getByRole("link", { name: "Aufnahme" })).toHaveCount(0);
    expect(mock.log.find((entry) => entry.path === "/users/register")?.status).toBe(201);
  });

  test("Abmelden führt zurück zum Login", async ({ page }) => {
    const mock = await mockApi(page, { session: "commander" });
    await page.goto("/");
    await page.getByRole("navigation", { name: "Bereiche" }).getByRole("button", { name: "Abmelden" }).click();
    await expect(page.getByRole("heading", { name: "Anmelden" })).toBeVisible();
    expect(mock.log.some((entry) => entry.path === "/admin-codes/logout")).toBe(true);
  });
});

test("Pairing-Link: Login im Konto-Modus, danach Freigabe und URL ohne ?pair", async ({ page }) => {
  const mock = await mockApi(page);
  await page.goto("/?pair=pair-waiting-123456");
  await expect(page.getByRole("heading", { name: "Gerät koppeln" })).toBeVisible();
  await expect(page.getByText("Ein Gerät möchte sich mit NCC verbinden")).toBeVisible();
  await expect(page.getByRole("radio", { name: "Konto" })).toBeChecked();
  await page.getByLabel("Benutzername").fill(CREDENTIALS.beta.username);
  await page.getByLabel("Passwort").fill(CREDENTIALS.beta.password);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await expect(page.getByText("„Jonas-PC“ ist gekoppelt")).toBeVisible();
  await expect(page).not.toHaveURL(/pair=/);
  const approvals = mock.log.filter((entry) => entry.path === "/agent-pairings/pair-waiting-123456/approve");
  expect(approvals).toHaveLength(1);
  expect(approvals[0]!.status).toBe(200);
});

test("Pairing-Link: abgelaufene Anfrage zeigt eine Fehlermeldung", async ({ page }) => {
  const mock = await mockApi(page, { session: "commander" });
  mock.data.pairings[0]!.status = "expired";
  await page.goto("/?pair=pair-waiting-123456");
  await expect(page.getByText(/Kopplung fehlgeschlagen: Die Kopplungsanfrage ist abgelaufen/)).toBeVisible();
  await expect(page).not.toHaveURL(/pair=/);
});

test("401 auf einem laufenden Request führt ohne Schleife zum Login", async ({ page }) => {
  const mock = await mockApi(page, { session: "commander" });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: /Geräten online/ })).toBeVisible();
  mock.expireSession();
  await expect(page.getByText("Deine Sitzung ist abgelaufen")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Anmelden" })).toBeVisible();
  const after = mock.log.length;
  await page.waitForTimeout(6_000);
  // On the login screen nothing polls protected endpoints any more.
  const protectedCalls = mock.log.slice(after).filter((entry) => entry.status === 401);
  expect(protectedCalls.length).toBeLessThanOrEqual(2);
});

test("Server nicht erreichbar", async ({ page }) => {
  await page.route("**/api/v1/**", (route) => route.abort("connectionrefused"));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Server nicht erreichbar" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Erneut verbinden" })).toBeVisible();
});

test("Alter Dashboard-Token wird nur als Header gesendet, nicht gespeichert", async ({ page }) => {
  let header: string | undefined;
  const mock = await mockApi(page, {}, { before: async (route) => { header ??= (await route.request().allHeaders())["x-ncc-dashboard-token"]; return false; } });
  await page.goto("/");
  await page.getByText("Alte Installation mit Dashboard-Token?").click();
  await page.getByLabel("Dashboard-Token").fill("legacy-token");
  await page.getByRole("button", { name: "Mit Token verbinden" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Geräten online/ })).toBeVisible();
  expect(mock.session?.role).toBe("commander");
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }));
  expect(stored).not.toContain("legacy-token");
  expect(header === undefined || header === "legacy-token").toBe(true);
});
