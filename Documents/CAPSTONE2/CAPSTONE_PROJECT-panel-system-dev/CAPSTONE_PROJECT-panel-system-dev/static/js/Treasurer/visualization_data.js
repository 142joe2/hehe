(function () {
  "use strict";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  async function fetchJSON(url) {
    const res = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
    });
    return res.json();
  }

  function waitVisible(fn, maxTries = 30) {
    // Chart.js needs a non-zero-size canvas; wait until the canvas is laid out.
    let tries = 0;
    (function check() {
      if (fn() === true) return;
      tries += 1;
      if (tries < maxTries) setTimeout(check, 60);
    })();
  }

  function fmtPeso(num) {
    const n = typeof num === "number" ? num : parseFloat(num || "0");
    return new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" }).format(n);
  }

  function destroyChart(ctx) {
    if (ctx && ctx.chart) {
      ctx.chart.destroy();
      ctx.chart = null;
    }
  }

  let paymentMethodsChart = null;
  let duesStatusChart = null;
  let monthlyCollectionChart = null;

  async function initMonthlyCollectionChart() {
    try {
      const data = await fetchJSON("/api/treasurer/dashboard/monthly-collection/");
      if (!data || !data.ok || !data.months) return;

      waitVisible(() => {
        const ctx = document.getElementById("monthlyCollectionChart");
        if (!ctx || ctx.offsetParent === null) return false;
        if (typeof Chart === "undefined") return false;

        destroyChart(ctx);

        monthlyCollectionChart = new Chart(ctx, {
        type: "line",
        data: {
          labels: data.months,
          datasets: [
            {
              label: "Collected",
              data: data.collected,
              borderColor: "#1b5e20",
              backgroundColor: "rgba(27, 94, 32, 0.12)",
              fill: true,
              tension: 0.35,
              pointRadius: 3,
              pointBackgroundColor: "#1b5e20",
              yAxisID: "y",
            },
            {
              label: "Paying Members",
              data: data.paying_members,
              borderColor: "#fbc02d",
              backgroundColor: "rgba(251, 192, 45, 0.10)",
              fill: false,
              tension: 0.35,
              pointRadius: 3,
              pointBackgroundColor: "#fbc02d",
              yAxisID: "y1",
            },
          ],
        },
        options: {
      animation: false,
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: {
              position: "top",
              labels: { font: { size: 10 }, padding: 12, usePointStyle: true },
            },
            tooltip: {
              callbacks: {
                label: function(context) {
                  if (context.datasetIndex === 0) return `Collected: ${fmtPeso(context.parsed.y)}`;
                  return `Paying Members: ${context.parsed.y}`;
                }
              }
            }
          },
          scales: {
            x: { ticks: { font: { size: 9 }, maxRotation: 45 } },
            y: {
              beginAtZero: true,
              ticks: {
                font: { size: 9 },
                callback: function(value) { return "₱" + value.toLocaleString(); }
              },
            },
            y1: {
              beginAtZero: true,
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: { font: { size: 9 } },
            },
          },
        },
      });
      ctx.chart = monthlyCollectionChart;
      return true;
    });
  } catch (e) { console.error("Monthly collection chart failed:", e); }
  }

  async function initPaymentMethodsChart() {
    try {
      const data = await fetchJSON("/api/treasurer/dashboard/payment-methods/");
      if (!data || !data.ok || !data.distribution) return;

      const labels = data.distribution.map(d => d.method);
      const values = data.distribution.map(d => d.count);
      const percentages = data.distribution.map(d => d.percentage);

      waitVisible(() => {
      const ctx = document.getElementById("paymentMethodsChart");
      if (!ctx || ctx.offsetParent === null) return false;
      if (typeof Chart === "undefined") return false;

      destroyChart(ctx);

      const colors = [
        "rgba(27, 94, 32, 0.8)",
        "rgba(251, 192, 45, 0.8)",
        "rgba(33, 150, 243, 0.8)",
        "rgba(255, 23, 68, 0.8)",
        "rgba(124, 77, 255, 0.8)",
        "rgba(255, 111, 0, 0.8)",
      ];
      const borderColors = [
        "#1b5e20",
        "#fbc02d",
        "#2196f3",
        "#ff1744",
        "#7c4dff",
        "#ff6f00",
      ];

      paymentMethodsChart = new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: labels,
          datasets: [{
            data: values,
            backgroundColor: colors.slice(0, values.length),
            borderColor: borderColors.slice(0, values.length),
            borderWidth: 2,
          }],
        },
        options: {
      animation: false,
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "right",
              labels: { font: { size: 10 }, padding: 12, usePointStyle: true },
            },
            tooltip: {
              callbacks: {
                label: function(context) {
                  const idx = context.dataIndex;
                  return `${labels[idx]}: ${values[idx]} (${percentages[idx]}%)`;
                }
              }
            }
          },
        },
      });
      ctx.chart = paymentMethodsChart;
      return true;
      });
    } catch (e) { console.error("Payment methods chart failed:", e); }
  }

  async function initDuesStatusChart() {
    try {
      const data = await fetchJSON("/api/treasurer/dashboard/dues-status/");
      if (!data || !data.ok) return;

      const total = Number(data.total || 0);
      const percentages = [data.paid_percentage, data.pending_percentage, data.unpaid_percentage];

      // Update the center overlay + status breakdown (matches the GUI mockup)
      const centerN = document.getElementById("duesStatusCenterN");
      if (centerN) centerN.textContent = total;
      const bd = document.getElementById("nxDuesBreakdown");
      if (bd) {
        bd.innerHTML =
          `<div class="status-item"><span class="status-dot green"></span><span class="status-label">Paid</span><span class="status-count">${data.paid}</span><span class="status-percent">${percentages[0]}%</span></div>` +
          `<div class="status-item"><span class="status-dot amber"></span><span class="status-label">Pending</span><span class="status-count">${data.pending}</span><span class="status-percent">${percentages[1]}%</span></div>` +
          `<div class="status-item"><span class="status-dot red"></span><span class="status-label">Unpaid</span><span class="status-count">${data.unpaid}</span><span class="status-percent">${percentages[2]}%</span></div>` +
          `<div class="status-total">Total Members: ${total}</div>`;
      }

      waitVisible(() => {
      const ctx = document.getElementById("duesStatusChart");
      if (!ctx || ctx.offsetParent === null) return false;
      if (typeof Chart === "undefined") return false;

      destroyChart(ctx);

      duesStatusChart = new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: ["Paid", "Pending", "Unpaid"],
          datasets: [
            {
              data: [Number(data.paid) || 0, Number(data.pending) || 0, Number(data.unpaid) || 0],
              backgroundColor: ["rgba(27, 94, 32, 0.85)", "rgba(251, 192, 45, 0.85)", "rgba(229, 57, 53, 0.85)"],
              borderColor: ["#1b5e20", "#fbc02d", "#e53935"],
              borderWidth: 2,
              hoverOffset: 6,
            },
          ],
        },
        options: {
      animation: false,
          responsive: true,
          maintainAspectRatio: false,
          cutout: "68%",
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (context) {
                  const idx = context.dataIndex;
                  return `${context.label}: ${context.parsed} (${percentages[idx]}%)`;
                },
              },
            },
          },
        },
      });
      ctx.chart = duesStatusChart;
      return true;
      });
    } catch (e) { console.error("Dues status chart failed:", e); }
  }

  async function initAidProgress() {
    try {
      const data = await fetchJSON("/api/treasurer/dashboard/aid-progress/");
      if (!data || !data.ok || !data.posts) return;

      const container = document.getElementById("aidProgressContainer");
      if (!container) return;

      container.innerHTML = "";
      container.style.display = "flex";
      container.style.flexDirection = "column";
      container.style.gap = "14px";
      container.style.alignItems = "stretch";

      if (data.posts.length === 0) {
        container.innerHTML = '<p class="overview-card-placeholder">No active aid posts</p>';
        return;
      }

      data.posts.forEach(post => {
        const isMedical = post.aid_type === "medical_aid";
        const accent = "#1b5e20";
        const accentBg = "#e8f5e9";
        const pct = Math.min(post.percentage ?? 0, 100);
        const statusLabel = post.status === "closed" ? "Closed" : "Tracking";

        const div = document.createElement("div");
        div.style.cssText = "border:1px solid #eceff1; border-radius:12px; padding:16px 18px; background:#ffffff;";
        div.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
            <div style="display:flex; align-items:center; gap:10px;">
              <span style="display:inline-flex; align-items:center; justify-content:center; width:32px; height:32px; border-radius:9px; background:${accentBg}; color:${accent}; font-size:0.9rem;">
                <i class="fa-solid fa-${isMedical ? "hand-holding-heart" : "heart-broken"}"></i>
              </span>
              <div>
                <div style="font-weight:700; color:#37474f; font-size:0.9rem; line-height:1.2;">${isMedical ? "Medical Aid" : "Death Aid"} #${post.post_id}</div>
                <div style="font-size:0.7rem; color:#90a4ae;">Target: ${post.target_month}</div>
              </div>
            </div>
            <span style="font-size:0.65rem; font-weight:700; text-transform:uppercase; letter-spacing:0.4px; background:${accentBg}; color:${accent}; padding:3px 10px; border-radius:20px;">${statusLabel}</span>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:14px; margin-bottom:6px;">
            <span style="font-size:0.68rem; font-weight:600; color:#90a4ae; text-transform:uppercase; letter-spacing:0.5px;">Collection Progress</span>
            <span style="font-size:0.8rem; font-weight:800; color:${accent};">${post.percentage}%</span>
          </div>
          <div style="height:10px; background:#f1f3f4; border-radius:6px; overflow:hidden;">
            <div style="width:${pct}%; height:100%; background:linear-gradient(90deg, ${accent}, #4caf50); border-radius:6px; transition:width 0.6s ease;"></div>
          </div>

          <div style="display:grid; grid-template-columns:repeat(4, 1fr); margin-top:14px; border:1px solid #f0f2f4; border-radius:10px; overflow:hidden;">
            <div style="padding:10px 6px; text-align:center; border-right:1px solid #f0f2f4;">
              <div style="font-size:0.62rem; font-weight:600; color:#90a4ae; text-transform:uppercase; letter-spacing:0.4px;">Expected</div>
              <div style="font-weight:800; color:#37474f; font-size:0.82rem; margin-top:3px;">${fmtPeso(post.expected)}</div>
            </div>
            <div style="padding:10px 6px; text-align:center; border-right:1px solid #f0f2f4;">
              <div style="font-size:0.62rem; font-weight:600; color:#90a4ae; text-transform:uppercase; letter-spacing:0.4px;">Collected</div>
              <div style="font-weight:800; color:${accent}; font-size:0.82rem; margin-top:3px;">${fmtPeso(post.collected)}</div>
            </div>
            <div style="padding:10px 6px; text-align:center; border-right:1px solid #f0f2f4;">
              <div style="font-size:0.62rem; font-weight:600; color:#90a4ae; text-transform:uppercase; letter-spacing:0.4px;">Remaining</div>
              <div style="font-weight:800; color:#37474f; font-size:0.82rem; margin-top:3px;">${fmtPeso(post.remaining)}</div>
            </div>
            <div style="padding:10px 6px; text-align:center; background:#fafafa;">
              <div style="font-size:0.62rem; font-weight:600; color:#90a4ae; text-transform:uppercase; letter-spacing:0.4px;">Members</div>
              <div style="font-weight:800; font-size:0.82rem; margin-top:3px; color:${accent};">
                <i class="fa-solid fa-circle-check" style="font-size:0.65rem;"></i> ${post.members_paid ?? 0}
                <span style="color:#cfd8dc; font-weight:400; margin:0 2px;">/</span>
                <i class="fa-solid fa-clock" style="font-size:0.65rem;"></i> ${post.members_pending ?? 0}
              </div>
            </div>
          </div>
        `;
        container.appendChild(div);
      });
    } catch (e) { console.error("Aid progress failed:", e); }
  }

  async function initActionQueue() {
    try {
      const data = await fetchJSON("/api/treasurer/dashboard/action-queue/");
      if (!data || !data.ok) return;

      const container = document.getElementById("actionQueueContainer");
      if (!container) return;

      container.style.display = "grid";
      container.style.gridTemplateColumns = "repeat(auto-fit, minmax(150px, 1fr))";
      container.style.gap = "12px";

      const items = [
        { key: "pending_aid_requests", label: "Medical/Death Aid Requests", icon: "exclamation-triangle" },
        { key: "pending_dues", label: "Pending Dues", icon: "clock" },
        { key: "pending_registrations", label: "Registration Requests", icon: "user-plus" },
        { key: "returned_entries", label: "Returned Entries", icon: "rotate-left" },
        { key: "ready_for_release", label: "Aid Ready for Release", icon: "circle-check" },
      ];

      const color = "#1b5e20";

      container.innerHTML = items.map(item => {
        const count = data[item.key] || 0;
        return `
          <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; background:#1b5e2015; border-radius:10px; padding:14px 10px;">
            <span style="display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; border-radius:50%; background:#ffffff; color:${color};">
              <i class="fa-solid fa-${item.icon}" style="font-size:0.9rem;"></i>
            </span>
            <span style="font-size:1.3rem; font-weight:800; color:${color}; line-height:1; font-variant-numeric:tabular-nums;">${count}</span>
            <span style="font-size:0.68rem; font-weight:600; color:#607d8b; text-align:center; line-height:1.3;">${item.label}</span>
          </div>
        `;
      }).join("");
    } catch (e) { console.error("Action queue failed:", e); }
  }

  function initTreasurerVisualizations() {
    initMonthlyCollectionChart();
    initPaymentMethodsChart();
    initDuesStatusChart();
    initAidProgress();
    initActionQueue();
  }

  // Expose for the template's module-init hooks (re-render when the
  // dashboard overview tab becomes active after being hidden).
  window.initTreasurerVisualizations = initTreasurerVisualizations;

  // Charts inside a display:none module get zero-height canvases in Chart.js.
  // Defer rendering until the dashboard overview is actually visible, and
  // listen on BOTH turbo:load and DOMContentLoaded (Turbo may not be active).
  let __vizStarted = false;
  function startVisualizations() {
    if (__vizStarted) return;
    const overview = document.getElementById("dashboard-overview");
    if (overview && !overview.classList.contains("active")) {
      // Overview hidden — the module-init hook will start us when it opens
      return;
    }
    __vizStarted = true;
    initTreasurerVisualizations();
  }

  document.addEventListener("turbo:load", startVisualizations);
  document.addEventListener("DOMContentLoaded", startVisualizations);
  // Last resort: if the page is already loaded when this script runs
  if (document.readyState !== "loading") {
    setTimeout(startVisualizations, 50);
  }
})();