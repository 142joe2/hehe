(function () {
  "use strict";

  window.showToast = function (message, isError) {
    var host = document.getElementById("toastContainer");
    if (!host) {
      alert(message);
      return;
    }
    var toast = document.createElement("div");
    toast.className = "custom-toast" + (isError ? " toast-error" : "");
    toast.innerHTML = '<p style="margin:0;font-size:0.85rem;font-weight:500;">' + escapeHtml(message) + "</p>";

    host.appendChild(toast);
    setTimeout(function () {
      toast.classList.add("show");
    }, 10);
    setTimeout(function () {
      toast.classList.remove("show");
      setTimeout(function () {
        toast.remove();
      }, 300);
    }, 4000);
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
})();
