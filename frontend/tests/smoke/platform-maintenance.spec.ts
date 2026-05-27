import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type PlatformStatus = {
  api: { status: string };
  frontend: { status: string };
  database: { status: string };
  queue: Record<string, number>;
};

function serviceOk(status: string): boolean {
  return status === "ok" || status === "completed" || status === "succeeded";
}

test("维护页首屏先给出是否需要排障的判断", async ({ page, request }) => {
  const statusResponse = await request.get(`${apiBaseUrl}/api/platform/status`);
  expect(statusResponse.ok(), "后端 `/api/platform/status` 不可用，无法验证维护页。").toBeTruthy();
  const status = (await statusResponse.json()) as PlatformStatus;

  const queuedJobs = Number(status.queue.queued ?? 0);
  const runningJobs = Number(status.queue.running ?? 0);
  const cancelRequestedJobs = Number(status.queue.cancel_requested ?? 0);
  const activeTaskCount = queuedJobs + runningJobs + cancelRequestedJobs;
  const platformReady = serviceOk(status.api.status) && serviceOk(status.frontend.status) && serviceOk(status.database.status);

  let expectedBanner = "现在不需要继续停留在这里";
  if (!platformReady) {
    expectedBanner = "先确认是不是服务异常，而不是先翻日志";
  } else if (activeTaskCount > 0) {
    expectedBanner = "平台本身正常，先看任务是否只是还在处理";
  }

  await page.goto("/platform");

  await expect(page.getByRole("heading", { name: "系统状态" })).toBeVisible();
  await expect(page.getByText(expectedBanner)).toBeVisible();
  await expect(page.getByText("如果页面打不开，再看心跳与同步调度")).toBeVisible();
});
