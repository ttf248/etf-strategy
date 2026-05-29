import { expect, test, type APIRequestContext } from "@playwright/test";
import { backendApiUrl, frontendApiUrl } from "./support";

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
  const statsResponse = await request.get(backendApiUrl("/api/market-data/stats"));
  expect(statsResponse.ok(), "后端 `/api/market-data/stats` 不可用，请先启动 API 并准备数据库行情。").toBeTruthy();
  const stats = (await statsResponse.json()) as MarketDataStats;
  expect(stats.instrument_count, "当前数据库没有可回测标的，请先执行 `py -3.13 main.py sync-now --symbol 1810.HK --interval 1d`，或在数据覆盖页同步首批行情。").toBeGreaterThan(0);

  const templatesResponse = await request.get(backendApiUrl("/api/templates?active_only=true"));
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

  throw new Error("未找到同时具备数据库行情和启用模板的回测组合，无法执行前端冒烟验证。");
}

test("首页到回测提交主路径可用", async ({ page, request }) => {
  const preset = await pickLaunchPreset(request);

  await Promise.all([
    page.waitForResponse((response) => response.url() === frontendApiUrl("/api/market-data/stats") && response.ok()),
    page.waitForResponse((response) => response.url().startsWith(frontendApiUrl("/api/backtests?limit=")) && response.ok()),
    page.waitForResponse((response) => response.url().startsWith(frontendApiUrl("/api/reports?limit=")) && response.ok()),
    page.goto("/"),
  ]);
  await expect(page.getByRole("heading", { name: "从数据覆盖到结果复盘的策略研究工作台" })).toBeVisible();
  await expect(page.getByText("当前研究状态")).toBeVisible();
  await expect(page.getByText("只有服务异常、任务停滞或连续失败时，再进入系统状态")).toBeVisible();
  await expect(page.getByRole("link", { name: "发起回测", exact: true })).toHaveAttribute("href", "/backtests");

  const launchParams = new URLSearchParams({
    symbol: preset.symbol,
    interval: preset.interval,
    strategy_kind: preset.strategyKind,
    template_id: String(preset.templateId),
  });
  await page.goto(`/backtests?${launchParams.toString()}`);

  await expect(page.getByText("已载入推荐研究样本")).toBeVisible();
  await expect(page.getByText("标准研究起点")).toBeVisible();
  await expect(page.getByText("先看最近几次任务，再决定要不要展开完整历史")).toBeVisible();
  await expect(page.locator('input[placeholder="例如 1810.HK、SH600000、10#AUDUSD"]')).toHaveValue(preset.symbol);
  await expect(page.getByText("行情来源")).toBeVisible();
  await expect(page.getByText("复权口径")).toBeVisible();

  await page.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByText("选择策略与模板")).toBeVisible();
  const recommendTemplateButton = page.getByRole("button", { name: /使用推荐模板：/ });
  if (await recommendTemplateButton.count()) {
    await recommendTemplateButton.click();
  }

  await page.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByText("确认执行配置并提交")).toBeVisible();
  await expect(page.getByText("当前将按这套配置创建任务")).toBeVisible();
  await expect(page.getByText("先盯最近任务，再去结果页")).toBeVisible();
  await expect(page.getByText(preset.symbol).first()).toBeVisible();

  const submitResponsePromise = page.waitForResponse((response) => {
    return response.url() === frontendApiUrl("/api/backtests") && response.request().method() === "POST";
  });
  await page.getByRole("button", { name: "开始回测" }).click();

  const submitResponse = await submitResponsePromise;
  expect(submitResponse.ok(), "回测任务提交失败。").toBeTruthy();
  const payload = (await submitResponse.json()) as { job_id: number };
  expect(payload.job_id).toBeGreaterThan(0);

  await expect(page.getByText(`任务已提交，编号 ${payload.job_id}`)).toBeVisible();
  const jobResponse = await request.get(backendApiUrl(`/api/backtests/${payload.job_id}`));
  expect(jobResponse.ok(), `无法读取新提交任务 ${payload.job_id} 的详情。`).toBeTruthy();
  const jobPayload = (await jobResponse.json()) as { id: number; request_payload: { symbol?: string } };
  expect(jobPayload.id).toBe(payload.job_id);
  expect(jobPayload.request_payload.symbol).toBe(preset.symbol);

  const cancelResponse = await request.post(backendApiUrl(`/api/backtests/${payload.job_id}/cancel`));
  expect(cancelResponse.ok(), `已提交的任务 ${payload.job_id} 无法取消。`).toBeTruthy();
});
