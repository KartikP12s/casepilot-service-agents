import { test, expect } from "@playwright/test";
test("requester submits and independent approver resumes a protected REST action", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Development bearer credential")
    .fill("local-user-only");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("button", { name: "New request" }).click();
  const resource = `analytics demo ${Date.now()}`;
  await page
    .getByLabel("What do you need?")
    .fill(`Request access to ${resource}`);
  await page.getByRole("button", { name: "Submit request" }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText("awaiting approval", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Approve action" }),
  ).toHaveCount(0);
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page
    .getByLabel("Development bearer credential")
    .fill("local-approver-only");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("button", { name: /Approval queue/ }).click();
  await page
    .getByRole("button", { name: `Request access to ${resource}`, exact: true })
    .click();
  await page
    .getByLabel("Decision reason")
    .fill("Synthetic demo reviewed by independent approver");
  await page
    .getByRole("button", { name: "Approve action", exact: true })
    .click();
  await expect(dialog.getByText("completed", { exact: true })).toBeVisible();
  await expect(
    dialog.getByText("tool completed", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: /All requests/ }).click();
  await page.screenshot({ path: "../docs/dashboard.png", fullPage: true });
});
