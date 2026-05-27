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

  await expect(page.getByRole("heading", { name: `回测报告 #${report.id}` })).toBeVisible();
  await expect(page.getByText("图上三条线分别代表什么")).toBeVisible();
  await page.getByRole("link", { name: "去对比同标的报告" }).first().click();

  await expect(page).toHaveURL(new RegExp(`/reports\\?compare=${report.id}.*keyword=${report.symbol}.*interval=${report.interval}`));
  await expect(page.getByText("已从详情页带入报告")).toBeVisible();
  await expect(page.getByText("报告默认不是按时间堆叠，而是按更适合先看的顺序排好")).toBeVisible();
  await expect(page.getByText("1. 先看收藏")).toBeVisible();
  await expect(page.locator(".report-compare-item").first().getByText(`#${report.id} ${report.symbol}`)).toBeVisible();
});
