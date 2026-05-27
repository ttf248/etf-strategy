import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type StrategyTemplate = {
  id: number;
  is_active: boolean;
};

test("模板页可以按目标筛选并加入对比", async ({ page, request }) => {
  const templatesResponse = await request.get(`${apiBaseUrl}/api/templates`);
  expect(templatesResponse.ok(), "后端 `/api/templates` 不可用，无法验证模板页路径。").toBeTruthy();
  const templates = (await templatesResponse.json()) as StrategyTemplate[];
  expect(templates.filter((item) => item.is_active).length, "当前至少需要 2 个启用模板才能验证对比区。").toBeGreaterThan(1);

  await page.goto("/templates");
  await expect(page.getByRole("heading", { name: "策略模板" })).toBeVisible();

  await page.locator(".template-persona-card").first().getByRole("button", { name: "只看这类模板" }).click();
  await expect(page.getByText("共")).toBeVisible();

  const recommendCards = page.locator(".template-recommend-card");
  await recommendCards.first().getByRole("button", { name: "加入对比" }).click();
  await recommendCards.nth(1).getByRole("button", { name: "加入对比" }).click();

  await expect(page.getByText("对比后怎么选")).toBeVisible();
  await expect(page.getByText("如果你是第一次跑回测")).toBeVisible();
  await expect(page.locator(".template-compare-item")).toHaveCount(2);
});
