(function () {
  "use strict";

  var chartInstance = null;

  function fmt(num) {
    return "₱" + Number(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtPeso(num) {
    return "₱" + Number(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function renderInflowOutflow(data) {
    var log = document.getElementById("io-log");
    var loading = document.getElementById("io-loading");
    if (!log) return;
    if (loading) loading.style.display = "none";

    var all = [];
    if (data.inflows) {
      data.inflows.forEach(function (item) {
        all.push({ description: item.description, source_type: item.source_type, amount: item.amount, date: item.recorded_at, is_inflow: true });
      });
    }
    if (data.outflows) {
      data.outflows.forEach(function (item) {
        all.push({ description: item.description, source_type: item.source_type, amount: item.amount, date: item.recorded_at, is_inflow: false });
      });
    }

    all.sort(function (a, b) { return a.date.localeCompare(b.date); });

    if (all.length === 0) {
      log.innerHTML = '<div class="io-empty">No entries yet</div>';
      return;
    }

    all.forEach(function (item, idx) {
      var div = document.createElement("div");
      var cls = item.is_inflow ? "io-inflow" : "io-outflow";
      div.className = "io-item " + cls;

      var sign = item.is_inflow ? "+" : "-";
      var desc = (item.description || "").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      var stype = (item.source_type || "").replace(/_/g, " ");

      div.innerHTML =
        '<span style="display:flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;font-size:0.65rem;font-weight:700;flex-shrink:0;line-height:18px;text-align:center;color:#fff;background:' + (item.is_inflow ? '#00e676' : '#ff1744') + ';">' + (idx + 1) + '</span>' +
        '<span class="io-sign">' + sign + '</span>' +
        '<span class="io-name"><span class="io-desc">' + desc + '</span><span class="io-stype">' + stype + '</span></span>' +
        '<span class="io-amount">' + fmt(item.amount) + '</span>' +
        '<span class="io-date">' + (item.date || "") + '</span>';

      log.appendChild(div);
    });
  }

  async function initIO() {
    try {
      var res = await fetch("/api/treasurer/dashboard/inflow-outflow/", { method: "GET", credentials: "same-origin" });
      var data = await res.json();
      if (data && data.ok) {
        renderInflowOutflow(data);
        var fundEl = document.getElementById("kpi-funds");
        if (fundEl && typeof data.fund_balance === "number") {
          fundEl.innerText = fmt(data.fund_balance);
          fundEl.dataset.liveLoaded = "true";
        }
        var moneyInEl = document.getElementById("kpi-money-in");
        var moneyOutEl = document.getElementById("kpi-money-out");
        if (moneyInEl && typeof data.money_in === "number") moneyInEl.innerText = fmt(data.money_in);
        if (moneyOutEl && typeof data.money_out === "number") moneyOutEl.innerText = fmt(data.money_out);
      }
    } catch (e) { console.error("Inflow/outflow init failed:", e); }
  }

  async function initMonthlyChart() {
    try {
      var res = await fetch("/api/treasurer/dashboard/monthly-flow/", { method: "GET", credentials: "same-origin" });
      var data = await res.json();
      if (!data || !data.ok || !data.months || data.months.length === 0) return;

      var ctx = document.getElementById("monthlyFlowChart");
      if (!ctx) return;

      var existingChart = Chart.getChart(ctx);
      if (existingChart) existingChart.destroy();
      else if (chartInstance) chartInstance.destroy();

      var config = {
        type: "bar",
        data: {
          labels: data.months,
          datasets: [
            { label: "Membership Fee", data: data.membership_fee, backgroundColor: "rgba(0,230,118,0.7)", borderColor: "#00e676", borderWidth: 1 },
            { label: "Monthly Dues", data: data.monthly_dues, backgroundColor: "rgba(0,188,212,0.7)", borderColor: "#00bcd4", borderWidth: 1 },
            { label: "Medical Aid", data: data.medical_aid, backgroundColor: "rgba(255,23,68,0.7)", borderColor: "#ff1744", borderWidth: 1 },
            { label: "Death Aid", data: data.death_aid, backgroundColor: "rgba(124,77,255,0.7)", borderColor: "#7c4dff", borderWidth: 1 },
            { label: "Fund Payment", data: data.fund_payment, backgroundColor: "rgba(124,77,255,0.7)", borderColor: "#7c4dff", borderWidth: 1 },
            { label: "Contribution", data: data.contribution, backgroundColor: "rgba(255,111,0,0.7)", borderColor: "#ff6f00", borderWidth: 1 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              mode: "index",
              intersect: false,
              callbacks: {
                label: function (ctx) { return ctx.dataset.label + ": " + fmtPeso(ctx.parsed.y); },
              },
            },
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 } } },
            y: {
              beginAtZero: true,
              ticks: {
                font: { size: 10 },
                callback: function (value) { return "₱" + value.toLocaleString(); },
              },
            },
          },
        },
      };

      chartInstance = new Chart(ctx, config);
      requestAnimationFrame(function () { chartInstance.resize(); });

      var dots = document.querySelectorAll("#chartLegendDots span");
      dots.forEach(function (dot) {
        dot.addEventListener("click", function () {
          var idx = parseInt(this.getAttribute("data-index"), 10);
          var meta = chartInstance.getDatasetMeta(idx);
          meta.hidden = meta.hidden === null ? !chartInstance.data.datasets[idx].hidden : !meta.hidden;
          chartInstance.update();
        });
      });
    } catch (e) { console.error("Monthly chart init failed:", e); }
  }

  document.addEventListener("turbo:load", function () {
    if (document.getElementById("io-log")) initIO();
    if (document.getElementById("monthlyFlowChart")) initMonthlyChart();
  });
})();
