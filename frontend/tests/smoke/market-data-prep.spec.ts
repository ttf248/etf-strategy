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
  await expect(page.locator(".provider-panel-card").getByText("A 股统一补数链路", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("通达信原始行情", { exact: true })).toBeVisible();
  await expect(page.getByText("最近导入任务", { exact: true })).toBeVisible();
  await expect(page.getByText("高级补数：这里只处理当前回测样本的 Yahoo 全量同步")).toBeVisible();
  await expect(page.getByText("高级明细：当前回测样本覆盖、筛选与更新时间")).toBeVisible();
  await expect(page.getByText("支持 all / 1d / 1m / 5m")).toBeVisible();
  await expect(page.locator(".provider-panel-card").getByText("支持 all / 1d").first()).toBeVisible();
  await expect(page.getByText("连续批跑轮数（仅批量模式）")).toBeVisible();

  await page.locator('input[placeholder="例如 1810.HK、SH600000、600000.SH、10#AUDUSD"]').fill(targetSymbol);
  await page.locator(".data-check-input").getByRole("button").click();

  await expect(page.getByText(`最近检查：${targetSymbol}`)).toBeVisible();
  await expect(page.getByRole("button", { name: "检查统一序列" })).toBeVisible();
});

test("通达信批量入口会把连续批跑轮数透传给同步接口", async ({ page, request }) => {
  const statsResponse = await request.get(backendApiUrl("/api/market-data/stats"));
  expect(statsResponse.ok(), "后端 `/api/market-data/stats` 不可用，无法验证数据准备页。").toBeTruthy();

  let syncPayload: Record<string, unknown> | null = null;
  await page.route(frontendApiUrl("/api/market-data/sync"), async (route) => {
    syncPayload = (route.request().postDataJSON() as Record<string, unknown> | null) ?? null;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        provider: "tdx",
        ingestion_job_id: 999999,
        status: "queued",
        target_symbol: "",
        interval: "1d",
        requested_via: "api",
      }),
    });
  });

  await Promise.all([
    page.waitForResponse((response) => response.url() === frontendApiUrl("/api/market-data/stats") && response.ok()),
    page.goto("/market-data"),
  ]);

  const tdxCard = page.locator(".provider-panel-card").filter({ has: page.getByText("通达信原始行情", { exact: true }) }).first();
  await expect(tdxCard.getByText("连续批跑轮数（仅批量模式）")).toBeVisible();
  await tdxCard.getByRole("button", { name: "批量导入 1d 20 项 / 1 轮" }).click();

  await expect.poll(() => (syncPayload ? String(syncPayload.provider ?? "") : "")).toBe("tdx");
  await expect.poll(() => (syncPayload ? String(syncPayload.interval ?? "") : "")).toBe("1d");
  await expect.poll(() => (syncPayload ? Number(syncPayload.limit ?? 0) : 0)).toBe(20);
  await expect.poll(() => (syncPayload ? Number(syncPayload.batch_rounds ?? 0) : 0)).toBe(1);
});
