/* NCC service worker, served by the server at /sw.js with scope "/".
 * Precaches the app shell; never caches /api responses. The build replaces
 * the two placeholders below with the asset list and a content hash. */

const PRECACHE = ["/","/assets/AboutTab-BWgDkol-.js","/assets/AlertPolicyTab-D5IR0MHU.js","/assets/Artwork-BO-O2SVO.js","/assets/Artwork-B_JnqnBg.css","/assets/barlow-condensed-latin-600-normal-DepVgxBB.woff2","/assets/barlow-condensed-latin-700-normal-v1xN8_Wq.woff2","/assets/barlow-latin-400-normal-qiz4-Cze.woff2","/assets/barlow-latin-500-normal-BPAOfeC8.woff2","/assets/barlow-latin-600-normal-DILqtrty.woff2","/assets/barlow-latin-700-normal-A9pxMQ4z.woff2","/assets/charts-DITn2cUV.js","/assets/Chat-B-w-bLyX.css","/assets/Chat-CDtENNFf.js","/assets/Enrollment-CE3wqkEb.js","/assets/Enrollment-DPlEWt__.css","/assets/Fleet-B_NHil4T.css","/assets/Fleet-Ckqz15FF.js","/assets/Games-BBrZK9od.js","/assets/GamesTab-D6-EyW4g.js","/assets/Hardware-BgDrJMm7.js","/assets/HardwareSummary-BrApJbuv.js","/assets/HardwareSummary-CyE9ddjh.css","/assets/icons/icon-192.png","/assets/icons/icon-512.png","/assets/icons/icon.svg","/assets/icons/maskable-512.png","/assets/icons/maskable.svg","/assets/index-D6d1q30Q.css","/assets/index-iDPrnxPw.js","/assets/jsx-runtime-Wy9s6hX0.js","/assets/LocationTab-qvfISuaA.js","/assets/LocationTab-vh-t_kPv.css","/assets/ManageTab-DuGW6TBB.js","/assets/manifest.webmanifest","/assets/Markdown-CPhJbV3R.js","/assets/NetworkTab-ZrJ1lahl.js","/assets/NodeDetail-DaYe7h-C.css","/assets/NodeDetail-dED9eTB4.js","/assets/Overview-Clr3IGbv.css","/assets/Overview-DnKDvgZw.js","/assets/Releases-B6rZU_uz.js","/assets/Releases-BEdcWQRx.css","/assets/SensorsTab-Bc1F9RYy.js","/assets/Settings-B-ThVxCB.js","/assets/Settings-BfhOGZyg.css","/assets/TelegramTab-B9H59dgU.js","/assets/Trackboard-BFTHXdAL.js","/assets/UpdatesTab-B_SNqDjk.js","/assets/UsersTab-CKc4jpN-.js"];
const VERSION = "155ec4f210b7";
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
