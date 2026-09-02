const CACHE_NAME = 'caufa-static-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/static/manifest.json',
  '/static/img/isu_caufa_splash_192.png',
  '/static/img/isu_caufa_splash_180.png',
  '/static/img/isu_caufa_splash_512.png',
  '/static/img/isu_caufa_official_192.png',
  '/static/img/isu_caufa_official_badge.png',
  '/static/img/isu_caufa_official_512.png',
  '/static/img/isugym.jpg',
  '/static/img/halfdesignISU.png'
];

// ==================== PUSH NOTIFICATION HANDLING ====================
self.addEventListener("push", function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "CAUFA Portal", body: event.data ? event.data.text() : "New update available." };
  }

  var title = data.title || "CAUFA Portal Notification";
  var options = {
    body: data.body || "You have a new update.",
    icon: data.icon || "/static/img/isu_caufa_official_192.png",
    badge: data.badge || "/static/img/isu_caufa_official_badge.png",
    vibrate: [200, 100, 200],
    data: {
      url: data.url || "/",
    },
  };

  // Ensure the push event ALWAYS resolves. If showNotification fails for any
  // reason, the browser must not hold/queue the message and redeliver it on the
  // next push — that causes the "first notification only appears after a second
  // one is sent" bug. Catching here marks delivery as handled immediately.
  event.waitUntil(
    Promise.resolve(self.registration.showNotification(title, options)).catch(function (err) {
      console.warn("showNotification failed:", err);
    })
  );
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var url = event.notification.data && event.notification.data.url ? event.notification.data.url : "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (windowClients) {
      for (var i = 0; i < windowClients.length; i++) {
        var client = windowClients[i];
        if (client.url.indexOf(self.location.origin) === 0) {
          return client.focus().then(function (focused) {
            if (focused.navigate) focused.navigate(url);
            else focused.location.href = url;
          });
        }
      }
      return clients.openWindow(url);
    })
  );
});
// ==================== END PUSH NOTIFICATION HANDLING ====================

self.addEventListener('install', (event) => {
  // Never let a cache failure block activation. A service worker stuck in
  // "installing" cannot receive push events reliably, which makes the first
  // notification wait for a later push to appear.
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => Promise.all(
        ASSETS_TO_CACHE.map((url) => cache.add(url).catch(() => null))
      ))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// Simple cache-first strategy for same-origin static assets, network-first for others
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle GET
  if (request.method !== 'GET') return;

  // For same-origin static resources (under /static/), use cache-first
  if (url.origin === location.origin && url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fetched = fetch(request).then((resp) => {
          if (resp && resp.ok) {
            // clone + cache but guard against failures when body already used
            const respClone = resp.clone();
            caches.open(CACHE_NAME).then(cache => {
              try {
                cache.put(request, respClone);
              } catch (e) {
                // Defensive: some responses may not be cloneable or may error
                console.warn('ServiceWorker: cache.put failed for', request.url, e);
              }
            }).catch(e => console.warn('ServiceWorker: open cache failed', e));
          }
          return resp;
        }).catch(() => null);
        return cached || fetched;
      })
    );
    return;
  }

  // Network-first for navigation and API calls
  event.respondWith(
    fetch(request).then((resp) => {
      return resp;
    }).catch(() => caches.match(request))
  );
});
