/**
 * PWA glue. The service worker lives under /assets/ (FastAPI serves nothing
 * else at the root), so its scope is /assets/ and it controls the installed
 * app at /assets/app.html. See DECISIONS.md, P-01 – P-04.
 */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/assets/sw.js", { scope: "/assets/" }).catch(() => undefined);
  });
}

type BadgeNavigator = Navigator & { setAppBadge?: (count?: number) => Promise<void>; clearAppBadge?: () => Promise<void> };

/** Number of active alerts on the installed app icon, where supported. */
export function setBadge(count: number): void {
  const nav = navigator as BadgeNavigator;
  if (!nav.setAppBadge) return;
  const action = count > 0 ? nav.setAppBadge(count) : nav.clearAppBadge?.();
  action?.catch(() => undefined);
}
