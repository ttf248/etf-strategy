import { expect, test, type APIRequestContext } from "@playwright/test";
import { backendApiUrl } from "./support";

type MarketDataStats = {
  coverages: Array<{ symbol: string }>;
  provider_summaries: Array<{ provider_key: string }>;
};

type StrategyTemplate = {
  id: number;
  is_active: boolean;
};

type ReportSummary = {
  id: number;
};

async function expectApiOk<T>(
  request: APIRequestContext,
  label: string,
  path: string,
): Promise<T> {
  const response = await request.get(backendApiUrl(path));
  expect(response.ok(), `${label} 接口不可用：${path}`).toBeTruthy();
  return (await response.json()) as T;
}

test("逐页主路径依赖的核心接口都可正常返回", async ({ request }) => {
  const stats = await expectApiOk<MarketDataStats>(request, "行情统计", "/api/market-data/stats");
  expect(Array.isArray(stats.coverages), "行情统计必须返回覆盖列表。").toBeTruthy();
  expect(Array.isArray(stats.provider_summaries), "行情统计必须返回渠道摘要。").toBeTruthy();

  const templates = await expectApiOk<StrategyTemplate[]>(request, "模板列表", "/api/templates");
  expect(Array.isArray(templates), "模板列表必须返回数组。").toBeTruthy();
  expect(templates.filter((item) => item.is_active).length, "当前至少需要 1 个启用模板供页面主路径使用。").toBeGreaterThan(0);

  const activeTemplates = await expectApiOk<StrategyTemplate[]>(request, "启用模板列表", "/api/templates?active_only=true");
  expect(Array.isArray(activeTemplates), "启用模板接口必须返回数组。").toBeTruthy();

  const backtests = await expectApiOk<Record<string, unknown>[]>(request, "回测任务列表", "/api/backtests?limit=100");
  expect(Array.isArray(backtests), "回测任务列表必须返回数组。").toBeTruthy();

  const reports = await expectApiOk<ReportSummary[]>(request, "报告列表", "/api/reports?limit=200");
  expect(Array.isArray(reports), "报告列表必须返回数组。").toBeTruthy();

  const platformStatus = await expectApiOk<Record<string, unknown>>(request, "平台状态", "/api/platform/status");
  expect(platformStatus).toHaveProperty("api");
  expect(platformStatus).toHaveProperty("frontend");
  expect(platformStatus).toHaveProperty("database");

  const processes = await expectApiOk<Record<string, unknown>[]>(request, "本机服务列表", "/api/platform/processes");
  expect(Array.isArray(processes), "本机服务列表必须返回数组。").toBeTruthy();

  const logs = await expectApiOk<{ service: string; lines: string[] }>(request, "平台日志", "/api/platform/logs?service=api&limit=20");
  expect(logs.service, "平台日志必须返回服务名。").toBe("api");
  expect(Array.isArray(logs.lines), "平台日志必须返回日志行数组。").toBeTruthy();

  const focusSymbol = stats.coverages[0]?.symbol;
  if (focusSymbol) {
    const encodedSymbol = encodeURIComponent(focusSymbol);

    const providerSeries = await expectApiOk<Record<string, unknown>[]>(
      request,
      "统一行情序列",
      `/api/market-data/provider-series?provider=all&symbol=${encodedSymbol}&limit=20`,
    );
    expect(Array.isArray(providerSeries), "统一行情序列必须返回数组。").toBeTruthy();

    const symbolDiagnostics = await expectApiOk<Record<string, unknown>>(
      request,
      "标的诊断",
      `/api/market-data/symbol-diagnostics?symbol=${encodedSymbol}&limit=12`,
    );
    expect(symbolDiagnostics).toHaveProperty("symbol");
    expect(symbolDiagnostics).toHaveProperty("summary");

    const manifests = await expectApiOk<Record<string, unknown>[]>(
      request,
      "源文件清单",
      `/api/market-data/source-file-manifests?provider=tdx&symbol=${encodedSymbol}&limit=20`,
    );
    expect(Array.isArray(manifests), "源文件清单必须返回数组。").toBeTruthy();
  }

  await expectApiOk<Record<string, unknown>[]>(
    request,
    "公司行动列表",
    "/api/market-data/corporate-actions?provider=tushare&limit=20",
  );
  await expectApiOk<Record<string, unknown>[]>(
    request,
    "前复权区间列表",
    "/api/market-data/adjustment-segments?provider=tdx_qfq&limit=20",
  );

  if (reports.length > 0) {
    const reportDetail = await expectApiOk<Record<string, unknown>>(request, "报告详情", `/api/reports/${reports[0].id}`);
    expect(reportDetail).toHaveProperty("id");
    expect(reportDetail).toHaveProperty("equity_curve");
  }
});
