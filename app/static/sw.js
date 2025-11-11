importScripts("/static/js/idb-helper.js");

const CACHE_NAME = "vocarater-cache-v1";
// List of files that make up the "app shell"
const urlsToCache = [
  "/",
  "/options",
  "/playlists",
  // Add other key pages you want to work offline
  "/static/css/app.css",
  "/static/js/global.min.js",
  "/static/js/main.min.js",
  "/static/js/options.min.js",
  "/static/js/playlist_editor.min.js",
  // Add your manifest and key icons
  "/static/site.webmanifest",
  "/static/android-chrome-192x192.png",
];

// 1. Install Event: Cache the app shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(urlsToCache);
      })
      .then(() => {
        // Force the waiting service worker to become the active service worker.
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error("[SW] Failed to cache app shell:", error);
      }),
  );
});

// Add an 'activate' event listener
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== CACHE_NAME) {
              return caches.delete(cacheName);
            }
          }),
        );
      })
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // If the request is for a YouTube thumbnail, ALWAYS go to the network.
  // Do not attempt to cache it or serve it from the cache.
  if (request.url.includes("i.ytimg.com")) {
    event.respondWith(fetch(request));
    return;
  }

  // Strategy 1: For API mutations (POST, etc.), try network, then queue for sync.
  const isApiMutation =
    request.url.includes("/api/") || request.url.includes("/rate/");
  if (request.method !== "GET" && isApiMutation) {
    event.respondWith(
      fetch(request.clone()).catch(() => saveRequestAndSync(request)),
    );
    return;
  }

  // Strategy 2: For page navigation (HTML), use Network-First.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // If network is successful, cache the new response and return it.
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
          return response;
        })
        .catch(() => {
          // If network fails, serve the page from the cache.
          return caches.match(request);
        }),
    );
    return;
  }

  // Strategy 3: For everything else (CSS, JS, images), use Cache-First.
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      return cachedResponse || fetch(request);
    }),
  );
});

async function saveRequestAndSync(request) {
  const serializedRequest = {
    url: request.url,
    method: request.method,
    headers: Object.fromEntries(request.headers.entries()),
    body: await request.text(), // Or .json() if you always send JSON
  };

  await saveRequest(serializedRequest);

  // Register the background sync
  if ("sync" in self.registration) {
    await self.registration.sync.register("sync-ratings-and-playlists");
  }

  // Return a synthetic "OK" response to the app so the UI can update
  return new Response(JSON.stringify({ message: "Request queued for sync" }), {
    status: 202, // 202 Accepted
    headers: { "Content-Type": "application/json" },
  });
}

self.addEventListener("sync", (event) => {
  if (event.tag === "sync-ratings-and-playlists") {
    event.waitUntil(syncData());
  }
});

async function syncData() {
  const requests = await getAllRequests();
  if (requests.length === 0) {
    return;
  }

  for (const req of requests) {
    try {
      const response = await fetch(req.url, {
        method: req.method,
        headers: req.headers,
        body: req.body,
      });

      if (!response.ok) {
        // If a request fails, you might want to handle it (e.g., keep it for later retry)
        // For now, we assume it succeeds and will be removed.
        console.error("Sync failed for request:", req.url, response.status);
      }
    } catch (error) {
      console.error("Network error during sync:", error);
      // If one request fails, stop and try again next time.
      // The queue will remain intact.
      return;
    }
  }

  // If all requests were successful, clear the queue.
  console.log("Sync complete, clearing request queue.");
  await clearRequests();
}
