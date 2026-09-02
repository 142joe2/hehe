(function () {
  "use strict";

  async function fetchJSON(url) {
    const res = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
    });
    return res.json();
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

  let fundMovementChart = null;
  let membershipOverviewChart = null;
  let duesComplianceChart = null;
  let aidOverviewChart = null;

  async function initFundMovementChart() {
    try {
      const data = await fetchJSON("/api/president/dashboard/fund-movement/");
      if (!data || !data.ok || !data.months) return;

      const ctx = document.getElementById("fundMovementChart");
      if (!ctx) return;

      destroyChart(ctx);

      fundMovementChart = new Chart(ctx, {
        type: "line",
        data: {
          labels: data.months,
          datasets: [
            {
              label: "Inflow",
              data: data.inflow,
              borderColor: "#00e676",
              backgroundColor: "rgba(0,230,118,0.1)",
              fill: true,
              tension: 0.3,
              pointRadius: 4,
            },
            {
              label: "Outflow",
              data: data.outflow,
              borderColor: "#ff1744",
              backgroundColor: "rgba(255,23,68,0.1)",
              fill: true,
              tension: 0.3,
              pointRadius: 4,
            },
            {
              label: "Net",
              data: data.net,
              borderColor: "#fbc02d",
              backgroundColor: "rgba(251,192,45,0.1)",
              fill: false,
              tension: 0.3,
              borderDash: [5, 5],
              pointRadius: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: true, position: "top", labels: { font: { size: 10 } } },
            tooltip: {
              callbacks: {
                label: function(context) {
                  return context.dataset.label + ": " + fmtPeso(context.parsed.y);
                }
              }
            }
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 9 } } },
            y: {
              beginAtZero: true,
              ticks: {
                font: { size: 9 },
                callback: function(value) { return "₱" + value.toLocaleString(); }
              }
            }
          },
        },
      });
      ctx.chart = fundMovementChart;
    } catch (e) { console.error("Fund movement chart failed:", e); }
  }

  async function initMembershipOverviewChart() {
    try {
      const data = await fetchJSON("/api/president/dashboard/membership-overview/");
      if (!data || !data.ok || !data.departments) return;

      const ctx = document.getElementById("membershipOverviewChart");
      if (!ctx) return;

      destroyChart(ctx);

      const sortedDepts = [...data.departments].sort((a, b) => b.count - a.count).slice(0, 10);
      const labels = sortedDepts.map(d => d.department);
      const values = sortedDepts.map(d => d.count);

      membershipOverviewChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [{
            label: "Members",
            data: values,
            backgroundColor: "rgba(27, 94, 32, 0.8)",
            borderColor: "#1b5e20",
            borderWidth: 2,
            borderRadius: 6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function(context) {
                  return `${context.label}: ${context.parsed.x} members`;
                }
              }
            }
          },
          scales: {
            x: { beginAtZero: true, ticks: { font: { size: 10 } } },
            y: { ticks: { font: { size: 10 } } }
          },
        },
      });
      ctx.chart = membershipOverviewChart;
    } catch (e) { console.error("Membership overview chart failed:", e); }
  }

  async function initDuesComplianceChart() {
    try {
      const data = await fetchJSON("/api/president/dashboard/dues-compliance/");
      if (!data || !data.ok) return;

      const ctx = document.getElementById("duesComplianceChart");
      if (!ctx) return;

      destroyChart(ctx);

      const labels = ["Paid", "Pending", "Unpaid"];
      const values = [data.paid, data.pending, data.unpaid];
      const percentages = [data.paid_percentage, data.pending_percentage, data.unpaid_percentage];

      duesComplianceChart = new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: labels,
          datasets: [{
            data: values,
            backgroundColor: [
              "rgba(27, 94, 32, 0.8)",
              "rgba(251, 192, 45, 0.8)",
              "rgba(229, 57, 53, 0.8)",
            ],
            borderColor: [
              "#1b5e20",
              "#fbc02d",
              "#e53935",
            ],
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "bottom",
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
      ctx.chart = duesComplianceChart;
    } catch (e) { console.error("Dues compliance chart failed:", e); }
  }

  async function initAidOverviewChart() {
    try {
      const data = await fetchJSON("/api/president/dashboard/aid-overview/");
      if (!data || !data.ok) return;

      const ctx = document.getElementById("aidOverviewChart");
      if (!ctx) return;

      destroyChart(ctx);

      const labels = ["Medical Aid", "Death Aid"];
      const requests = [data.medical_aid.requests, data.death_aid.requests];
      const approved = [data.medical_aid.approved, data.death_aid.approved];
      const released = [data.medical_aid.released, data.death_aid.released];

      aidOverviewChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Requests",
              data: requests,
              backgroundColor: "rgba(45, 212, 191, 0.8)",
              borderColor: "#2dd4bf",
              borderWidth: 2,
            },
            {
              label: "Approved",
              data: approved,
              backgroundColor: "rgba(165, 180, 252, 0.8)",
              borderColor: "#a5b4fc",
              borderWidth: 2,
            },
            {
              label: "Released",
              data: released,
              backgroundColor: "rgba(27, 94, 32, 0.8)",
              borderColor: "#1b5e20",
              borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "top", labels: { font: { size: 10 } } },
            tooltip: {
              callbacks: {
                label: function(context) {
                  return context.dataset.label + ": " + context.parsed.y;
                }
              }
            }
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 } } },
            y: { beginAtZero: true, ticks: { font: { size: 10 }, stepSize: 1 } }
          },
        },
      });
      ctx.chart = aidOverviewChart;
    } catch (e) { console.error("Aid overview chart failed:", e); }
  }

  async function initContributionProgress() {
    try {
      const data = await fetchJSON("/api/president/dashboard/contribution-progress/");
      if (!data || !data.ok || !data.posts) return;

      const container = document.getElementById("contributionProgressContainer");
      if (!container) return;

      if (data.posts.length === 0) {
        container.innerHTML = '<p class="overview-card-placeholder">No active aid posts</p>';
        return;
      }

      container.innerHTML = data.posts.map(post => `
        <div style="margin-bottom: 16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong style="color:#1b5e20;">${post.aid_type === "medical_aid" ? "Medical Aid" : "Death Aid"} #${post.post_id}</strong>
            <span style="font-size:0.75rem; color:#757575;">${post.target_month}</span>
          </div>
          <div style="height:10px; background:#eef3ee; border-radius:6px; overflow:hidden; margin-bottom:6px;">
            <div style="width:${post.percentage}%; height:100%; background:#1b5e20; border-radius:6px; transition:width 0.6s ease;"></div>
          </div>
          <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:8px; font-size:0.75rem;">
            <div style="text-align:center;">
              <div style="font-weight:700; color:#1b5e20;">${fmtPeso(post.expected)}</div>
              <div style="color:#757575;">Expected</div>
            </div>
            <div style="text-align:center;">
              <div style="font-weight:700; color:#00e676;">${fmtPeso(post.collected)}</div>
              <div style="color:#757575;">Collected</div>
            </div>
            <div style="text-align:center;">
              <div style="font-weight:700; color:#1b5e20;">${post.percentage}%</div>
              <div style="color:#757575;">Progress</div>
            </div>
          </div>
        </div>
      `).join("");
    } catch (e) { console.error("Contribution progress failed:", e); }
  }

  async function initApprovalPipeline() {
    try {
      const data = await fetchJSON("/api/president/dashboard/approval-pipeline/");
      if (!data || !data.ok) return;

      const container = document.getElementById("approvalPipelineContainer");
      if (!container) return;

      const color = "#1b5e20";
      const bg = "#e8f5e9";

      const pipelines = [
        { key: "registration", title: "Registration", icon: "user-plus" },
        { key: "medical_aid", title: "Medical Aid", icon: "hand-holding-heart" },
        { key: "death_aid", title: "Death Aid", icon: "heart-broken" },
      ];

      const stages = [
        { key: "submitted", label: "Submitted", icon: "file-lines" },
        { key: "treasurer", label: "Treasurer", icon: "cash-register" },
        { key: "auditor", label: "Auditor", icon: "magnifying-glass-chart" },
        { key: "president", label: "President", icon: "user-tie" },
        { key: "approved", label: "Approved", icon: "circle-check" },
      ];

      container.innerHTML = pipelines.map(pipe => {
        const d = data[pipe.key];
        if (!d) return "";

        const submitted = d.submitted || 0;
        const approved = d.approved || 0;

        const stageHtml = stages.map((stage, i) => {
          const count = d[stage.key] || 0;
          const isLast = i === stages.length - 1;
          const stageBg = isLast ? color : "#ffffff";
          const stageBorder = isLast ? color : "#e0e0e0";
          const countColor = isLast ? "#ffffff" : color;
          const labelColor = isLast ? "rgba(255,255,255,0.9)" : "#757575";

          const box = `
            <div style="display:flex; flex-direction:column; align-items:center; flex:1; min-width:86px;">
              <div style="
                width:100%; max-width:110px;
                background:${stageBg};
                border:1.5px solid ${stageBorder};
                border-radius:12px;
                padding:12px 8px 10px;
                text-align:center;
                box-shadow:0 1px 3px rgba(0,0,0,0.06);
              ">
                <i class="fa-solid fa-${stage.icon}" style="font-size:0.85rem; color:${isLast ? "rgba(255,255,255,0.85)" : "#bdbdbd"};"></i>
                <div style="font-size:1.35rem; font-weight:800; color:${countColor}; line-height:1.2; margin-top:4px;">${count}</div>
                <div style="font-size:0.62rem; font-weight:600; color:${labelColor}; text-transform:uppercase; letter-spacing:0.4px; margin-top:2px;">${stage.label}</div>
              </div>
            </div>
          `;

          if (isLast) return box;

          const prev = i === 0 ? submitted : (d[stages[i - 1].key] || 0);
          const drop = prev > 0 && count < prev
            ? `<span style="font-size:0.6rem; color:#90a4ae; font-weight:700;">&#9660;${prev - count}</span>`
            : `<span style="font-size:0.6rem; color:#cfd8dc;">&#8212;</span>`;

          return box + `
            <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-width:34px; gap:2px;">
              <i class="fa-solid fa-angles-right" style="color:#cfd8dc; font-size:0.85rem;"></i>
              ${drop}
            </div>
          `;
        }).join("");

        return `
          <div style="
            border:1px solid #eceff1;
            border-radius:14px;
            padding:16px 18px;
            margin-bottom:16px;
            background:#ffffff;
          ">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px;">
              <span style="
                display:inline-flex; align-items:center; justify-content:center;
                width:34px; height:34px; border-radius:10px;
                background:${bg}; color:${color}; font-size:1rem;
              "><i class="fa-solid fa-${pipe.icon}"></i></span>
              <strong style="color:#424242; font-size:0.95rem;">${pipe.title} Pipeline</strong>
            </div>
            <div style="display:flex; align-items:stretch; gap:4px; flex-wrap:wrap;">
              ${stageHtml}
            </div>
          </div>
        `;
      }).join("");
    } catch (e) { console.error("Approval pipeline failed:", e); }
  }

  function initPresidentVisualizations() {
    initFundMovementChart();
    initMembershipOverviewChart();
    initDuesComplianceChart();
    initAidOverviewChart();
    initContributionProgress();
    initApprovalPipeline();
  }

  document.addEventListener("turbo:load", initPresidentVisualizations);
})();