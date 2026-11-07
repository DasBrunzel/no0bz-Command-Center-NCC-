import { expect, test } from "@playwright/test";
import { mockApi } from "./helpers.ts";

/* Features that were open after 0.7.0: delete accounts, invite agents with a
 * role, rename groups and the fleet-wide traffic endpoint. */

test("Konto löschen: nur deaktivierte Konten, mit Rückfrage", async ({ page }) => {
  const mock = await mockApi(page, { session: "commander" });
  await page.goto("/#/einstellungen/konten");
  const old = page.getByRole("row", { name: /altkonto/ });
  await old.getByRole("button", { name: "Löschen" }).click();
  const dialog = page.getByRole("dialog", { name: /altkonto endgültig löschen/ });
  await expect(dialog).toContainText("nicht rückgängig");
  await dialog.getByRole("button", { name: "Endgültig löschen" }).click();
  await expect(page.getByText("altkonto ist gelöscht.")).toBeVisible();
  await expect(page.getByRole("row", { name: /altkonto/ })).toHaveCount(0);
  expect(mock.log.some((entry) => entry.method === "DELETE" && entry.path === "/users/u-old" && entry.status === 204)).toBe(true);
  // Active accounts offer no delete button.
  await expect(page.getByRole("row", { name: /kalle/ }).getByRole("button", { name: "Löschen" })).toHaveCount(0);
});

test("Agent-Einladung mit Rolle", async ({ page }) => {
  const mock = await mockApi(page, { session: "commander" });
  await page.goto("/#/aufnahme");
  await page.getByLabel("Für welches Gerät?").fill("Jonas-PC");
  await page.getByLabel("Rolle des Geräts").selectOption("beta_tester");
  await page.getByRole("button", { name: "Einladung erstellen" }).click();
  await expect(page.getByRole("row", { name: /Jonas-PC/ })).toContainText("Beta-Tester");
  const created = mock.log.find((entry) => entry.method === "POST" && entry.path === "/agent-invitations");
  expect(created?.status).toBe(201);
  expect(mock.data.agentInvitations[0]?.access_role).toBe("beta_tester");
});

test("Gruppe umbenennen im Anordnen-Dialog", async ({ page }) => {
  const mock = await mockApi(page, { session: "commander" });
  await page.goto("/#/geraete");
  await page.getByRole("button", { name: "Anordnen" }).click();
  const dialog = page.getByRole("dialog", { name: "Geräte anordnen" });
  await dialog.getByRole("button", { name: "Gruppe Server umbenennen" }).click();
  const input = dialog.getByLabel("Neuer Name für Server");
  await expect(input).toHaveValue("Server");
  await input.fill("Rechenzentrum");
  await dialog.getByRole("button", { name: "Übernehmen" }).click();
  await expect(page.getByText("Gruppe heißt jetzt „Rechenzentrum“.")).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "Rechenzentrum" })).toBeVisible();
  expect(mock.data.groups.find((group) => group.group_id === "default-servers")?.name).toBe("Rechenzentrum");
});

test("Live-Verkehr zeigt den Verlauf sofort", async ({ page }) => {
  const mock = await mockApi(page, { session: "commander" });
  await page.goto("/");
  const panel = page.getByRole("region", { name: "Live-Verkehr" });
  await expect(panel.getByRole("img", { name: /Verkehr der Fleet/ })).toBeVisible();
  await expect(panel).not.toContainText("zu wenige Messpunkte");
  expect(mock.log.some((entry) => entry.path === "/fleet/network" && entry.status === 200)).toBe(true);
});
