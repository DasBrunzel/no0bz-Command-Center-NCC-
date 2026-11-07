/* NCC service worker. Scope: /assets/ (see DECISIONS.md, P-02).
 * Precaches the app shell; never caches /api responses. The build replaces
 * the two placeholders below with the asset list and a content hash. */

const PRECACHE = ["/assets/app.html","/assets/barlow-condensed-latin-600-normal-DepVgxBB.woff2","/assets/barlow-condensed-latin-700-normal-v1xN8_Wq.woff2","/assets/barlow-latin-400-normal-qiz4-Cze.woff2","/assets/barlow-latin-500-normal-BPAOfeC8.woff2","/assets/barlow-latin-600-normal-DILqtrty.woff2","/assets/barlow-latin-700-normal-A9pxMQ4z.woff2","/assets/charts-Dy7fWeOL.js","/assets/Chat-DDvqWOvm.js","/assets/Enrollment-DDvqWOvm.js","/assets/Fleet-BSOlONYU.js","/assets/Fleet-DXjgkpSG.css","/assets/Games-DDvqWOvm.js","/assets/GamesTab-DILiZbfD.js","/assets/GamesTab-DPdOpT-9.css","/assets/Hardware-DRhyTf17.js","/assets/HardwareSummary-CyE9ddjh.css","/assets/HardwareSummary-DLuNLy0C.js","/assets/icons/icon.svg","/assets/icons/maskable.svg","/assets/index-CkokeUaB.js","/assets/index-jx5DnAC4.css","/assets/jsx-runtime-LKYXHABd.js","/assets/ManageTab-BiZrEIdo.js","/assets/manifest.webmanifest","/assets/NetworkTab-CBIWLNC_.js","/assets/NodeDetail-CKtTS2Zn.css","/assets/NodeDetail-Dce0hgxP.js","/assets/Overview-BdYaBHaH.js","/assets/Overview-Bntvq0vO.css","/assets/react-DlmbjZJV.js","/assets/Releases-DDvqWOvm.js","/assets/rolldown-runtime-XKyaHtl9.js","/assets/SensorsTab-CV0lgqo1.js","/assets/Settings-DDvqWOvm.js","/assets/Trackboard-BFyZXtgK.js","/assets/UpdatesTab-Cp4bUZuo.js"];
const VERSION = "eb6c003fe8c7";
const CACHE = `ncc-shell-${VERSION}`;
const SHELL = "/assets/app.html";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(Array.isArray(PRECACHE) ? PRECACHE : [SHELL])).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("ncc-shell-") && key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  // The installed app shell: network first, cached copy when offline.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok && url.pathname === SHELL) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(SHELL, copy));
          }
          return response;
        })
        .catch(() => caches.match(SHELL).then((cached) => cached || Response.error())),
    );
    return;
  }

  // Hashed build assets never change: cache first.
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })),
    );
  }
});
