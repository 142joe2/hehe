(function () {
  "use strict";

  var VAPID_PUBLIC_KEY = window.VAPID_PUBLIC_KEY || null;
  if (!VAPID_PUBLIC_KEY) return;

  // Never register Web Push under an ngrok tunnel (or similar transient host).
  // Subscriptions registered under a random tunnel origin make Chrome brand the
  // notification with the tunnel name and flag it as "possible spam". The real
  // domain (isucaufa-fms.online) and localhost are always allowed.
  var currentHost = (window.location.hostname || "").toLowerCase();
  if (currentHost.indexOf("ngrok") !== -1) return;

  var state = { swRegistration: null, subscribed: false, denied: false };

  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var rawData = atob(base64);
    var output = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      output[i] = rawData.charCodeAt(i);
    }
    return output;
  }

  function getCsrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  var WELCOME_COOLDOWN_MS = 24 * 60 * 60 * 1000; // 24 hours

  function getOfficerFirstName() {
    var el = document.querySelector(".user-name");
    if (el && el.textContent.trim()) {
      return el.textContent.trim().split(" ")[0];
    }
    return "User";
  }

  function getOfficerDashboardUrl() {
    var el = document.querySelector(".user-role");
    if (!el) return "/";
    var role = (el.textContent || "").trim().toLowerCase();
    if (role.indexOf("treasurer") !== -1) return "/treasurer/";
    if (role.indexOf("auditor") !== -1) return "/auditor/";
    if (role.indexOf("president") !== -1) return "/president/";
    return "/";
  }

  function showWelcomeNotification() {
    if (Notification.permission !== "granted") return;
    try {
      var last = localStorage.getItem("caufa_welcomed_ts");
      if (last && Date.now() - parseInt(last, 10) < WELCOME_COOLDOWN_MS) return;
      localStorage.setItem("caufa_welcomed_ts", String(Date.now()));
    } catch (e) {}
    var name = getOfficerFirstName();
    var url = getOfficerDashboardUrl();
    var notif = new Notification("Hello " + name + "!", {
      body: "Welcome to the CAUFA Dashboard",
      icon: "/static/img/isu_caufa_official.png",
      vibrate: [200, 100, 200],
    });
    notif.onclick = function () {
      window.focus();
      this.close();
      if (url) window.location.href = url;
    };
  }

  function updateBellIcon() {
    var bell = document.getElementById("notifBellBtn");
    if (bell) {
      var icon = bell.querySelector("i");
      if (state.subscribed) {
        bell.className = "header-btn toolbar-bell subscribed";
        icon.className = "fa-solid fa-bell";
        bell.title = "Push notifications enabled";
      } else if (state.denied) {
        bell.className = "header-btn toolbar-bell denied";
        icon.className = "fa-solid fa-bell-slash";
        bell.title = "Notifications blocked — update browser settings";
      } else {
        bell.className = "header-btn toolbar-bell";
        icon.className = "fa-regular fa-bell";
        bell.title = "Enable push notifications";
      }
    }
    if (window.PUSH_CONFIG && typeof window.PUSH_CONFIG.onStateChange === "function") {
      try {
        window.PUSH_CONFIG.onStateChange(state);
      } catch (e) {}
    }
  }

  function subscribeUser(registration) {
    registration.pushManager
      .subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      })
      .then(function (subscription) {
        var subJson = subscription.toJSON();
        fetch("/api/push/subscribe/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            endpoint: subJson.endpoint,
            keys: subJson.keys,
            recipient_type: window.PUSH_RECIPIENT_TYPE || "officer",
          }),
        }).catch(function () {});
        state.subscribed = true;
        state.denied = false;
        updateBellIcon();
        showWelcomeNotification();
      })
      .catch(function (error) {
        console.error("Push subscription failed:", error);
        state.subscribed = false;
        state.denied = Notification.permission === "denied";
        updateBellIcon();
      });
  }

  function checkAndRefreshSubscription(registration) {
    registration.pushManager.getSubscription().then(function (subscription) {
      if (!subscription) {
        // No subscription exists, subscribe
        subscribeUser(registration);
      } else {
        // Check if subscription is still valid by making a test request
        var subJson = subscription.toJSON();
        fetch("/api/push/validate-subscription/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            endpoint: subJson.endpoint,
            recipient_type: window.PUSH_RECIPIENT_TYPE || "officer",
          }),
        })
        .then(function (response) {
          return response.json().catch(function () {
            return { valid: false };
          }).then(function (data) {
            if (!response.ok || !data.valid) {
              // Subscription is invalid or stale — resubscribe so the DB
              // gets a fresh, live endpoint instead of the dead one.
              state.subscribed = false;
              state.denied = false;
              updateBellIcon();
              subscription.unsubscribe().then(function () {
                subscribeUser(registration);
              }).catch(function () {
                subscribeUser(registration);
              });
            } else {
              // Subscription is valid, update state
              state.subscribed = true;
              state.denied = false;
              updateBellIcon();
            }
          });
        })
        .catch(function () {
          // If validation fails, assume subscription is valid and update state
          state.subscribed = true;
          state.denied = false;
          updateBellIcon();
        });
      }
    });
  }

  function requestPermission() {
    if (!state.swRegistration) {
      navigator.serviceWorker
        .register("/sw.js")
        .then(function (reg) {
          state.swRegistration = reg;
          doRequest();
        })
        .catch(function () {});
    } else {
      doRequest();
    }

    function doRequest() {
      if (Notification.permission === "granted") {
        subscribeUser(state.swRegistration);
        return;
      }
      Notification.requestPermission().then(function (permission) {
        if (permission === "granted") {
          subscribeUser(state.swRegistration);
        } else {
          state.denied = true;
          state.subscribed = false;
          updateBellIcon();
        }
      });
    }
  }

  window.requestPushPermission = requestPermission;

  if ("serviceWorker" in navigator && "PushManager" in window) {
    navigator.serviceWorker
      .register("/sw.js")
      .then(function (registration) {
        state.swRegistration = registration;
        // Check and refresh subscription on load
        checkAndRefreshSubscription(registration);
      })
      .catch(function (error) {
        console.error("Service Worker registration failed:", error);
      });
  }
})();
