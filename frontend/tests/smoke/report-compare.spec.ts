import { expect, test } from "@playwright/test";
import { backendApiUrl } from "./support";

type ReportSummary = {
  id: number;
  symbol: string;
  interval: string;
};

test("报告详情可以带着当前报告进入对比区", async ({ page, request }) => {
  const reportsResponse = await request.get(backendApiUrl("/api/reports?limit=20"));
  expect(reportsResponse.ok(), "后端 `/api/reports` 不可用，无法验证报告详情路径。").toBeTruthy();
  const reports = (await reportsResponse.json()) as ReportSummary[];
  expect(reports.length, "当前数据库没有可用报告，请先生成至少一份回测报告。").toBeGreaterThan(0);

  const report = reports[0];
  await page.goto(`/reports/${report.id}`);

  await expect(page.getByRole("heading", { name: `回测报告 编号 ${report.id}` })).toBeVisible();
  await expect(page.getByText("图例说明：")).toBeVisible();
  await expect(page.getByText("配置解读")).toBeVisible();
  await expect(page.getByText("优先理解模板定位、交易节奏与风险假设，无需先通读全部参数名")).toBeVisible();
  await page.getByRole("link", { name: /带上最该比的结果继续判断|带入对比区继续判断/ }).first().click();

  await expect(page).toHaveURL(/\/reports\?/);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("compare")).toContain(String(report.id));
  await expect.poll(() => new URL(page.url()).searchParams.get("keyword")).toBe(report.symbol);
  await expect.poll(() => new URL(page.url()).searchParams.get("interval")).toBe(report.interval);
  await expect(page.getByText("已从详情页带入报告")).toBeVisible();
  await expect(page.getByText("当前这批结果，最该先做什么")).toBeVisible();
  await expect(page.getByText("结果快筛")).toBeVisible();
  await expect(page.getByText("同标的研究焦点")).toBeVisible();
  await expect(page.getByText("先按判断目标收窄结果，再决定要不要通读全部卡片")).toBeVisible();
  await expect(page.getByText("报告默认按复盘优先级排序，而非简单按时间堆叠")).toBeVisible();
  await expect(page.getByText("1. 收藏报告")).toBeVisible();
  await expect(page.locator(".report-compare-item").getByText(`编号 ${report.id} ${report.symbol}`).first()).toBeVisible();
});
