import { expect, test } from "@playwright/test";
import { backendApiUrl } from "./support";

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
  const statusResponse = await request.get(backendApiUrl("/api/platform/status"));
  expect(statusResponse.ok(), "后端 `/api/platform/status` 不可用，无法验证维护页。").toBeTruthy();
  const status = (await statusResponse.json()) as PlatformStatus;

  const queuedJobs = Number(status.queue.queued ?? 0);
  const runningJobs = Number(status.queue.running ?? 0);
  const cancelRequestedJobs = Number(status.queue.cancel_requested ?? 0);
  const activeTaskCount = queuedJobs + runningJobs + cancelRequestedJobs;
  const platformReady = serviceOk(status.api.status) && serviceOk(status.frontend.status) && serviceOk(status.database.status);

  let expectedBanner = "当前无需继续停留在此页面";
  if (!platformReady) {
    expectedBanner = "优先确认是否存在服务异常，而不是直接翻日志";
  } else if (activeTaskCount > 0) {
    expectedBanner = "平台本身正常，先确认任务是否仍在处理中";
  }

  await page.goto("/platform");

  await expect(page.getByRole("heading", { name: "系统状态" })).toBeVisible();
  await expect(page.getByText(expectedBanner)).toBeVisible();
  await expect(page.getByText("先确认当前是否需要进入该页")).toBeVisible();
  await expect(page.getByText("服务不可用时，再看服务心跳与定时同步")).toBeVisible();
  await expect(page.getByText("怀疑执行服务未运行时，再看本机服务")).toBeVisible();
});
