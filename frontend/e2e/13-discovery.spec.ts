import { test, expect } from "@playwright/test";

test.describe("Discovery Flow — /start", () => {
  test("Landing-Screen: zeigt Entdecker- und Kenner-Button", async ({ page }) => {
    await page.goto("/start");

    await expect(page.getByTestId("btn-entdecker")).toBeVisible();
    await expect(page.getByTestId("btn-kenner")).toBeVisible();
  });

  test("Geführte Entdeckung: alle 4 Schritte durchlaufen und Profil-Karte sehen", async ({ page }) => {
    await page.goto("/start");

    // Landing: Entdecker-Pfad wählen
    await page.getByTestId("btn-entdecker").click();

    // Schritt 1/4: Beruf eingeben
    await expect(page.getByTestId("input-beruf")).toBeVisible();
    await page.getByTestId("input-beruf").fill("Softwareentwickler");
    await page.getByRole("button", { name: /Weiter/i }).click();

    // Schritt 2/4: Ziel wählen
    await expect(page.getByTestId("ziel-retirement")).toBeVisible();
    await page.getByTestId("ziel-retirement").click();
    await page.getByRole("button", { name: /Weiter/i }).click();

    // Schritt 3/4: Risikoprofil wählen
    await expect(page.getByTestId("risiko-moderate")).toBeVisible();
    await page.getByTestId("risiko-moderate").click();
    await page.getByRole("button", { name: /Weiter/i }).click();

    // Schritt 4/7: Brands anklicken (mindestens eine)
    await expect(page.getByTestId("brand-NESN")).toBeVisible();
    await page.getByTestId("brand-NESN").click();
    await page.getByTestId("brand-ROG").click();
    await page.getByRole("button", { name: /Profil fertigstellen|Überspringen/i }).click();

    // Schritt 5/7: Betrag wählen
    await expect(page.getByTestId("betrag-under_10k")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("betrag-under_10k").click();
    await page.getByRole("button", { name: /Weiter/i }).click();

    // Schritt 6/7: Nachhaltigkeit wählen
    await expect(page.getByTestId("nachhaltigkeit-yes")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("nachhaltigkeit-yes").click();
    await page.getByRole("button", { name: /Weiter/i }).click();

    // Schritt 7/7: Ertrag wählen
    await expect(page.getByTestId("ertrag-dividends")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("ertrag-dividends").click();
    await page.getByRole("button", { name: /Profil fertigstellen/i }).click();

    // Reveal: Kristall-Animation erscheint zuerst
    await expect(page.getByTestId("crystal")).toBeVisible();

    // Profil-Karte erscheint nach Kristall-Phase
    await expect(page.getByTestId("profile-card")).toBeVisible({ timeout: 5_000 });

    // Continue-Button erscheint
    await expect(page.getByTestId("btn-continue")).toBeVisible({ timeout: 5_000 });
  });

  test("Continue-Button leitet zu /discover weiter", async ({ page }) => {
    await page.goto("/start");

    // Schnell durch alle Schritte
    await page.getByTestId("btn-entdecker").click();
    await page.getByTestId("input-beruf").fill("Arzt");
    await page.getByRole("button", { name: /Weiter/i }).click();
    await page.getByTestId("ziel-housing").click();
    await page.getByRole("button", { name: /Weiter/i }).click();
    await page.getByTestId("risiko-conservative").click();
    await page.getByRole("button", { name: /Weiter/i }).click();
    // Schritt 4 überspringen
    await page.getByRole("button", { name: /Überspringen/i }).click();

    // Schritt 5/7: Betrag wählen
    await expect(page.getByTestId("betrag-under_10k")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("betrag-under_10k").click();
    await page.getByRole("button", { name: /Weiter/i }).click();

    // Schritt 6/7: Nachhaltigkeit wählen
    await expect(page.getByTestId("nachhaltigkeit-yes")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("nachhaltigkeit-yes").click();
    await page.getByRole("button", { name: /Weiter/i }).click();

    // Schritt 7/7: Ertrag wählen
    await expect(page.getByTestId("ertrag-dividends")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("ertrag-dividends").click();
    await page.getByRole("button", { name: /Profil fertigstellen/i }).click();

    // Warten bis Continue-Button sichtbar
    await expect(page.getByTestId("btn-continue")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("btn-continue").click();

    // Sollte zu /discover navigieren
    await expect(page).toHaveURL(/\/discover/, { timeout: 10_000 });
  });

  test("Kenner-Pfad: Direkt-Suche erscheint nach Klick auf btn-kenner", async ({ page }) => {
    await page.goto("/start");

    await page.getByTestId("btn-kenner").click();

    // Kenner-Suchfeld erscheint
    await expect(page.getByTestId("kenner-search-input")).toBeVisible();
  });
});
