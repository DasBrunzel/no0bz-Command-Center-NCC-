import type { Page, Route } from "@playwright/test";
import { createMockApi, type MockApi, type MockOptions } from "./mock/api.ts";

/** Route every /api/v1 request of the page to a fresh in-memory mock. */
export async function mockApi(page: Page, options: MockOptions = {}, hooks: { delay?: number; before?: (route: Route, path: string) => boolean | Promise<boolean> } = {}): Promise<MockApi> {
  const mock = createMockApi(options);
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (hooks.before && (await hooks.before(route, url.pathname))) return;
    if (hooks.delay) await new Promise((resolve) => setTimeout(resolve, hooks.delay));
    const headers = await request.allHeaders();
    const isJson = (headers["content-type"] ?? "").includes("json");
    const result = mock.handle({ method: request.method(), url: url.pathname + url.search, headers, body: isJson ? request.postData() : null });
    await route.fulfill({
      status: result.status,
      contentType: result.contentType ?? "application/json",
      body: result.body ?? (result.json === undefined ? "" : JSON.stringify(result.json)),
    });
  });
  return mock;
}
