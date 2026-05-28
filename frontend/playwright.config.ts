import { defineConfig } from "@playwright/test";

const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT ?? "3000";
const backendOrigin =
  process.env.STRATEGY_STUDIO_API_ORIGIN ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./tests/smoke",
  fullyParallel: false,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: `npm run start -- --hostname 127.0.0.1 --port ${frontendPort}`,
    url: `http://127.0.0.1:${frontendPort}`,
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      ...process.env,
      STRATEGY_STUDIO_API_ORIGIN: backendOrigin,
    },
  },
});
