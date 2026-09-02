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

  event.waitUntil(self.registration.showNotification(title, options));
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

self.addEventListener("install", function (event) {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(clients.claim());
});
