/* NCC service worker. Scope: /assets/ (see DECISIONS.md, P-02).
 * Precaches the app shell; never caches /api responses. The build replaces
 * the two placeholders below with the asset list and a content hash. */

const PRECACHE = ["/assets/AboutTab--3JUieE5.js","/assets/AlertPolicyTab-BP6oh_BN.js","/assets/app.html","/assets/Artwork-BlczMYd7.css","/assets/Artwork-DniI0RUO.js","/assets/barlow-condensed-latin-600-normal-DepVgxBB.woff2","/assets/barlow-condensed-latin-700-normal-v1xN8_Wq.woff2","/assets/barlow-latin-400-normal-qiz4-Cze.woff2","/assets/barlow-latin-500-normal-BPAOfeC8.woff2","/assets/barlow-latin-600-normal-DILqtrty.woff2","/assets/barlow-latin-700-normal-A9pxMQ4z.woff2","/assets/charts-DITn2cUV.js","/assets/Chat-B-w-bLyX.css","/assets/Chat-DpdmIw5f.js","/assets/Enrollment-DPlEWt__.css","/assets/Enrollment-fEFjSSTW.js","/assets/Fleet-C0oi12Dm.css","/assets/Fleet-CjKbPAR9.js","/assets/Games-CqRcUDdn.js","/assets/GamesTab-CD78o6in.js","/assets/Hardware-Df_1Dt0x.js","/assets/HardwareSummary-B-YzVi4b.js","/assets/HardwareSummary-CyE9ddjh.css","/assets/icons/icon-192.png","/assets/icons/icon-512.png","/assets/icons/icon.svg","/assets/icons/maskable-512.png","/assets/icons/maskable.svg","/assets/index-D6d1q30Q.css","/assets/index-DFsTRoc_.js","/assets/jsx-runtime-Wy9s6hX0.js","/assets/ManageTab-NKUKk2Ez.js","/assets/manifest.webmanifest","/assets/Markdown-BVQLldzP.js","/assets/NetworkTab-Bcr9e_Ie.js","/assets/NodeDetail-CuAPZGVU.js","/assets/NodeDetail-YZx3lZv6.css","/assets/Overview-C2e0vMSz.js","/assets/Overview-Clr3IGbv.css","/assets/Releases-Bm4fHI_e.css","/assets/Releases-CJty2B5o.js","/assets/SensorsTab-Hn2ktYhI.js","/assets/Settings-BevbyvV3.js","/assets/Settings-BfhOGZyg.css","/assets/TelegramTab-BBrIU-6t.js","/assets/Trackboard-DfnnrxrB.js","/assets/UpdatesTab-CCAgML8P.js","/assets/UsersTab-1qYbDbBh.js"];
const VERSION = "13e6a070f8d7";
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
