/* NCC service worker, served by the server at /sw.js with scope "/".
 * Precaches the app shell; never caches /api responses. The build replaces
 * the two placeholders below with the asset list and a content hash. */

const PRECACHE = ["/","/assets/AboutTab-C56aDZ_8.js","/assets/AlertPolicyTab-BxXkc_Ke.js","/assets/Artwork-BdKMuYBI.js","/assets/Artwork-B_JnqnBg.css","/assets/barlow-condensed-latin-600-normal-DepVgxBB.woff2","/assets/barlow-condensed-latin-700-normal-v1xN8_Wq.woff2","/assets/barlow-latin-400-normal-qiz4-Cze.woff2","/assets/barlow-latin-500-normal-BPAOfeC8.woff2","/assets/barlow-latin-600-normal-DILqtrty.woff2","/assets/barlow-latin-700-normal-A9pxMQ4z.woff2","/assets/charts-DITn2cUV.js","/assets/Chat-B-w-bLyX.css","/assets/Chat-CSQegEvO.js","/assets/Enrollment-DPlEWt__.css","/assets/Enrollment-fb8i27eG.js","/assets/Fleet-C0oi12Dm.css","/assets/Fleet-DAe1hguZ.js","/assets/Games-xXp1cGGY.js","/assets/GamesTab-cEVevPnd.js","/assets/Hardware-CUDIPq7E.js","/assets/HardwareSummary-CyE9ddjh.css","/assets/HardwareSummary-DEn18lgw.js","/assets/icons/icon-192.png","/assets/icons/icon-512.png","/assets/icons/icon.svg","/assets/icons/maskable-512.png","/assets/icons/maskable.svg","/assets/index-D6d1q30Q.css","/assets/index-DvYUXnCk.js","/assets/jsx-runtime-Wy9s6hX0.js","/assets/ManageTab-DoSf45Ub.js","/assets/manifest.webmanifest","/assets/Markdown-CPhJbV3R.js","/assets/NetworkTab-yScZnN61.js","/assets/NodeDetail-BpFTTDh3.js","/assets/NodeDetail-YZx3lZv6.css","/assets/Overview-BuezCA3x.js","/assets/Overview-Clr3IGbv.css","/assets/Releases-Bm4fHI_e.css","/assets/Releases-ByRK2_VD.js","/assets/SensorsTab-9dsjF4t9.js","/assets/Settings-BfhOGZyg.css","/assets/Settings-Bl1etX61.js","/assets/TelegramTab-F5lIrBXG.js","/assets/Trackboard-Fbyyftvk.js","/assets/UpdatesTab-njGOnl9P.js","/assets/UsersTab-BMIhOgW-.js"];
const VERSION = "6bf9061e160c";
const CACHE = `ncc-shell-${VERSION}`;
const SHELL = "/";

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
          // Only the dashboard page itself is the shell (query and hash vary).
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
