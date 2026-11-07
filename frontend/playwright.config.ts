import { defineConfig, devices } from "@playwright/test";

const port = 8360;

/*
 * The built dashboard is served like FastAPI would serve it (tests/mock/serve.ts
 * with no session); every test routes /api/v1 to its own in-memory mock.
 * Run `pnpm build` first.
 */
export default defineConfig({
  testDir: "tests",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: true,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    locale: "de-DE",
    timezoneId: "Europe/Berlin",
    colorScheme: "light",
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
  webServer: {
    command: "node tests/mock/serve.ts",
    env: { MOCK_PORT: String(port), MOCK_ROLE: "none" },
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: !process.env.CI,
  },
});
