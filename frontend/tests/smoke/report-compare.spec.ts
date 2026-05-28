import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ReportSummary = {
  id: number;
  symbol: string;
  interval: string;
};

test("报告详情可以带着当前报告进入对比区", async ({ page, request }) => {
  const reportsResponse = await request.get(`${apiBaseUrl}/api/reports?limit=20`);
  expect(reportsResponse.ok(), "后端 `/api/reports` 不可用，无法验证报告详情路径。").toBeTruthy();
  const reports = (await reportsResponse.json()) as ReportSummary[];
  expect(reports.length, "当前数据库没有可用报告，请先生成至少一份回测报告。").toBeGreaterThan(0);

  const report = reports[0];
  await page.goto(`/reports/${report.id}`);

  await expect(page.getByRole("heading", { name: `回测报告 编号 ${report.id}` })).toBeVisible();
  await expect(page.getByText("图上三条线分别代表什么")).toBeVisible();
  await expect(page.getByText("这套配置大概是什么意思")).toBeVisible();
  await expect(page.getByText("先看模板定位、交易节奏和风险假设，不必先读完全部参数名")).toBeVisible();
  await page.getByRole("link", { name: "去对比同标的报告" }).first().click();

  await expect(page).toHaveURL(new RegExp(`/reports\\?compare=${report.id}.*keyword=${report.symbol}.*interval=${report.interval}`));
  await expect(page.getByText("已从详情页带入报告")).toBeVisible();
  await expect(page.getByText("结果快筛")).toBeVisible();
  await expect(page.getByText("先按判断目标收窄结果，再决定要不要通读全部卡片")).toBeVisible();
  await expect(page.getByText("报告默认按复盘优先级排序，而非简单按时间堆叠")).toBeVisible();
  await expect(page.getByText("1. 收藏报告")).toBeVisible();
  await expect(page.locator(".report-compare-item").first().getByText(`编号 ${report.id} ${report.symbol}`)).toBeVisible();
});
