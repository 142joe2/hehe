(function () {
  "use strict";

  function fmt(num) {
    return new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" }).format(num);
  }

  async function init() {
    try {
      var res = await fetch("/api/cash-flow-summary/", { method: "GET", credentials: "same-origin" });
      var data = await res.json();
      if (!data || !data.ok) return;

      var fundsIn = document.getElementById("cf-funds-in");
      var fundsOut = document.getElementById("cf-funds-out");
      var pending = document.getElementById("cf-pending-contributions");
      if (fundsIn) fundsIn.innerText = fmt(data.funds_in);
      if (fundsOut) fundsOut.innerText = fmt(data.funds_out);
      if (pending) pending.innerText = fmt(data.pending_contributions);
    } catch (e) {
      console.error("Cash flow init failed:", e);
    }
  }

  document.addEventListener("turbo:load", init);
})();
