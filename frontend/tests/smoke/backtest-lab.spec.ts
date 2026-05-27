import { expect, test, type APIRequestContext } from "@playwright/test";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type MarketCoverage = {
  symbol: string;
  interval: string;
};

type MarketDataStats = {
  instrument_count: number;
  coverages: MarketCoverage[];
};

type StrategyTemplate = {
  id: number;
  strategy_kind: string;
  interval: string;
  is_active: boolean;
  is_default: boolean;
};

type LaunchPreset = {
  symbol: string;
  interval: string;
  strategyKind: string;
  templateId: number;
};

async function pickLaunchPreset(request: APIRequestContext): Promise<LaunchPreset> {
  const statsResponse = await request.get(`${apiBaseUrl}/api/market-data/stats`);
  expect(statsResponse.ok(), "后端 `/api/market-data/stats` 不可用，请先启动 API 并导入样例行情。").toBeTruthy();
  const stats = (await statsResponse.json()) as MarketDataStats;
  expect(stats.instrument_count, "当前数据库没有可回测标的，请先执行 `py -3.13 main.py import-csv --source-dir data/processed`。").toBeGreaterThan(0);

  const templatesResponse = await request.get(`${apiBaseUrl}/api/templates?active_only=true`);
  expect(templatesResponse.ok(), "后端 `/api/templates` 不可用，请先完成 `init-db`。").toBeTruthy();
  const templates = ((await templatesResponse.json()) as StrategyTemplate[]).filter((item) => item.is_active);

  const preferredPairs = [
    { strategyKind: "grid", interval: "15m" },
    { strategyKind: "dca", interval: "1d" },
    { strategyKind: "grid", interval: "1d" },
    { strategyKind: "grid", interval: "1m" },
  ];

  for (const pair of preferredPairs) {
    const template = templates.find((item) => item.strategy_kind === pair.strategyKind && item.interval === pair.interval && item.is_default)
      ?? templates.find((item) => item.strategy_kind === pair.strategyKind && item.interval === pair.interval);
    const coverage = stats.coverages.find((item) => item.interval === pair.interval);
    if (template && coverage) {
      return {
        symbol: coverage.symbol,
        interval: pair.interval,
        strategyKind: pair.strategyKind,
        templateId: template.id,
      };
    }
  }

  throw new Error("未找到同时具备样例行情和启用模板的回测组合，无法执行前端冒烟验证。");
}

test("首页到回测提交主路径可用", async ({ page, request }) => {
  const preset = await pickLaunchPreset(request);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "从一个标的开始，跑出第一份回测报告" })).toBeVisible();
  await expect(page.getByText("第一次使用建议按这条路走")).toBeVisible();
  await expect(page.getByText("数据准备 -> 创建回测 -> 查看报告")).toBeVisible();
  await expect(page.getByText("为什么现在推荐这一步")).toBeVisible();
  await expect(page.getByRole("link", { name: "开始一次回测" })).toHaveAttribute("href", "/backtests");

  const launchParams = new URLSearchParams({
    symbol: preset.symbol,
    interval: preset.interval,
    strategy_kind: preset.strategyKind,
    template_id: String(preset.templateId),
  });
  await page.goto(`/backtests?${launchParams.toString()}`);

  await expect(page.getByText("已带入首页示例")).toBeVisible();
  await expect(page.getByText("如果你只是想先跑通第一轮")).toBeVisible();
  await expect(page.getByText("先看最近几次任务，再决定要不要展开完整历史")).toBeVisible();
  await expect(page.locator('input[placeholder="例如 1810.HK"]')).toHaveValue(preset.symbol);

  await page.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByText("选择一个容易理解的策略模板")).toBeVisible();
  await page.getByRole("button", { name: /使用推荐模板：/ }).click();

  await page.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByText("确认后提交任务")).toBeVisible();
  await expect(page.getByText("提交后会发生什么")).toBeVisible();
  await expect(page.getByText("刚提交时，只看第一条就够了")).toBeVisible();
  await expect(page.getByText(preset.symbol).first()).toBeVisible();

  const submitResponsePromise = page.waitForResponse((response) => {
    return response.url() === `${apiBaseUrl}/api/backtests` && response.request().method() === "POST";
  });
  await page.getByRole("button", { name: "开始回测" }).click();

  const submitResponse = await submitResponsePromise;
  expect(submitResponse.ok(), "回测任务提交失败。").toBeTruthy();
  const payload = (await submitResponse.json()) as { job_id: number };
  expect(payload.job_id).toBeGreaterThan(0);

  await expect(page.getByText(`任务已提交，ID=${payload.job_id}`)).toBeVisible();
  const jobResponse = await request.get(`${apiBaseUrl}/api/backtests/${payload.job_id}`);
  expect(jobResponse.ok(), `无法读取新提交任务 ${payload.job_id} 的详情。`).toBeTruthy();
  const jobPayload = (await jobResponse.json()) as { id: number; request_payload: { symbol?: string } };
  expect(jobPayload.id).toBe(payload.job_id);
  expect(jobPayload.request_payload.symbol).toBe(preset.symbol);

  const cancelResponse = await request.post(`${apiBaseUrl}/api/backtests/${payload.job_id}/cancel`);
  expect(cancelResponse.ok(), `已提交的任务 ${payload.job_id} 无法取消。`).toBeTruthy();
});
