import { expect, test } from "@playwright/test";
import { backendApiUrl, frontendApiUrl } from "./support";

type MarketDataStats = {
  coverages: Array<{ symbol: string }>;
};

test("数据准备页先给出开始建议，再把完整覆盖放到高级明细", async ({ page, request }) => {
  const statsResponse = await request.get(backendApiUrl("/api/market-data/stats"));
  expect(statsResponse.ok(), "后端 `/api/market-data/stats` 不可用，无法验证数据准备页。").toBeTruthy();
  const stats = (await statsResponse.json()) as MarketDataStats;
  expect(stats.coverages.length, "当前至少需要 1 条行情覆盖记录才能验证数据准备页。").toBeGreaterThan(0);

  const targetSymbol = stats.coverages[0].symbol;

  await Promise.all([
    page.waitForResponse((response) => response.url() === frontendApiUrl("/api/market-data/stats") && response.ok()),
    page.goto("/market-data"),
  ]);

  await expect(page.getByRole("heading", { name: "多渠道数据准备" })).toBeVisible();
  await expect(page.getByText("多渠道任务面板", { exact: true })).toBeVisible();
  await expect(page.getByText("Yahoo 回测样本", { exact: true })).toBeVisible();
  await expect(page.getByText("通达信原始日线", { exact: true })).toBeVisible();
  await expect(page.getByText("最近导入任务", { exact: true })).toBeVisible();
  await expect(page.getByText("高级补数：这里只处理当前回测样本的 Yahoo 全量同步")).toBeVisible();
  await expect(page.getByText("高级明细：当前回测样本覆盖、筛选与更新时间")).toBeVisible();

  await page.locator('input[placeholder="例如 1810.HK、SH600000、600000.SH"]').fill(targetSymbol);
  await page.locator(".data-check-input").getByRole("button").click();

  await expect(page.getByText(`最近检查：${targetSymbol}`)).toBeVisible();
});
