import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type MarketDataStats = {
  coverages: Array<{ symbol: string }>;
};

test("数据准备页先给出开始建议，再把完整覆盖放到高级明细", async ({ page, request }) => {
  const statsResponse = await request.get(`${apiBaseUrl}/api/market-data/stats`);
  expect(statsResponse.ok(), "后端 `/api/market-data/stats` 不可用，无法验证数据准备页。").toBeTruthy();
  const stats = (await statsResponse.json()) as MarketDataStats;
  expect(stats.coverages.length, "当前至少需要 1 条行情覆盖记录才能验证数据准备页。").toBeGreaterThan(0);

  const targetSymbol = stats.coverages[0].symbol;

  await page.goto("/market-data");

  await expect(page.getByRole("heading", { name: "数据准备" })).toBeVisible();
  await expect(page.getByText("先按准备程度选一个标的，不需要先翻完整覆盖表")).toBeVisible();
  await expect(page.getByText("什么时候才同步全部")).toBeVisible();
  await expect(page.getByText("高级补数：只有准备扩大量级时，再补全部标的某个周期")).toBeVisible();
  await expect(page.getByText("高级明细：全部标的覆盖、筛选和更新时间")).toBeVisible();

  await page.locator('input[placeholder="例如 1810.HK"]').fill(targetSymbol);
  await page.locator(".data-check-input").getByRole("button").click();

  await expect(page.getByText(`最近检查：${targetSymbol}`)).toBeVisible();
});
