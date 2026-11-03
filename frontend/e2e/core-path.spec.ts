import { expect, test } from "@playwright/test";
import path from "node:path";

const ASSETS = path.resolve(__dirname, "../../plans/reference/assets");

test("core pathway: create, upload, index, enroll, find, panel, console", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /findMe/ })).toBeVisible();

  await page.getByRole("button", { name: "Create an album" }).click();
  await page.waitForURL(/\/a\//);

  const upload = page.getByTestId("upload");
  await upload.locator("input[type=file]").setInputFiles([
    path.join(ASSETS, "s2_a.jpg"),
    path.join(ASSETS, "s2_b.jpg"),
  ]);
  await expect(page.getByTestId("progress")).toBeVisible({ timeout: 60_000 });
  await expect(upload).not.toBeVisible();
  await expect(page.getByTestId("progress").getByText("ready", { exact: true })).toBeVisible({ timeout: 60_000 });

  const enroll = page.getByTestId("enroll");
  await enroll.locator("input[type=file]").setInputFiles([path.join(ASSETS, "s2_a.jpg")]);
  await expect(enroll.getByText(/face \d+px/)).toBeVisible({ timeout: 60_000 });

  await page.getByRole("button", { name: "Find me" }).click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("results").getByText(/you appear in/)).toBeVisible();

  const firstCard = page.getByTestId("results").locator("button.card").first();
  await firstCard.click();
  const panel = page.getByTestId("panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByText("PLACE")).toBeVisible();
  await expect(panel.getByText("WEATHER")).toBeVisible();
  await expect(panel.getByText("CAMERA")).toBeVisible();

  await page.keyboard.press("`");
  await expect(page.getByTestId("debug-console")).toBeVisible();
  await expect(page.getByTestId("debug-console").getByText(/google:/)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("debug-console")).not.toBeVisible();
});

test("backtick guarded inside inputs and share disclosure present", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Create an album" }).click();
  await page.waitForURL(/\/a\//);

  await expect(page.getByText(/anyone with this link/)).toBeVisible();

  const input = page.getByTestId("venue-link").locator("input").first();
  const hasVenue = await input.isVisible().catch(() => false);
  if (hasVenue) {
    await input.focus();
    await page.keyboard.type("`");
    await expect(page.getByTestId("debug-console")).not.toBeVisible();
  } else {
    await page.keyboard.press("`");
    await expect(page.getByTestId("debug-console")).toBeVisible();
  }
});
