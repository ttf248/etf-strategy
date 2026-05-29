import { expect, test } from "@playwright/test";
import { backendApiUrl } from "./support";

type StrategyTemplate = {
  id: number;
  is_active: boolean;
};

test("模板页可以按目标筛选并加入对比", async ({ page, request }) => {
  const templatesResponse = await request.get(backendApiUrl("/api/templates"));
  expect(templatesResponse.ok(), "后端 `/api/templates` 不可用，无法验证模板页路径。").toBeTruthy();
  const templates = (await templatesResponse.json()) as StrategyTemplate[];
  expect(templates.filter((item) => item.is_active).length, "当前至少需要 2 个启用模板才能验证对比区。").toBeGreaterThan(1);

  await page.goto("/templates");
  await expect(page.getByRole("heading", { name: "策略模板" })).toBeVisible();
  await expect(page.getByText("建议先从推荐模板中选择基线配置，而不是立即新建自定义模板")).toBeVisible();
  await expect(page.getByText("按研究目标筛选模板")).toBeVisible();
  await expect(page.getByText("推荐模板", { exact: true })).toBeVisible();
  await expect(page.getByText("维护区：启用模板、新建模板和查看完整列表")).toBeVisible();

  await page.locator(".template-persona-card").first().getByRole("button", { name: "筛选该类模板" }).click();

  const recommendCards = page.locator(".template-recommend-card");
  await expect(recommendCards.first()).toBeVisible();
  await recommendCards.first().getByRole("button", { name: "加入对比" }).click();
  await recommendCards.nth(1).getByRole("button", { name: "加入对比" }).click();

  await expect(page.getByText("对比结论")).toBeVisible();
  await expect(page.getByText("若当前目标是建立基线结果，可优先采用")).toBeVisible();
  await expect(page.locator(".template-compare-item")).toHaveCount(2);
});
