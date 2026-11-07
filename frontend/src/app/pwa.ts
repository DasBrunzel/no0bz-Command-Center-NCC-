/**
 * PWA glue. The server serves the worker at /sw.js, so it controls the whole
 * dashboard. Workers from the 0.7 preview builds lived under /assets/ and are
 * removed. See DECISIONS.md, section 3.
 */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    void navigator.serviceWorker.getRegistrations().then((registrations) => {
      for (const registration of registrations) if (new URL(registration.scope).pathname.startsWith("/assets/")) void registration.unregister();
    });
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
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
