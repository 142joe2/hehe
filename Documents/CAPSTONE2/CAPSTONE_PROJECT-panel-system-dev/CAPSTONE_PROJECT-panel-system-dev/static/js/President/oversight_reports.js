// Oversight Reports JavaScript for President Dashboard

// ==========================================================================
// OVERSIGHT SUMMARY - EXECUTIVE DASHBOARD
// ==========================================================================

// Chart instances for cleanup
let oversightCharts = {};
window.__oversightFilterState = {
  period: 'current_month',
  college: '',
  custom_start: '',
  custom_end: ''
};

function getOversightFilterState() {
  const period = document.getElementById("oversight-period-filter")?.value || window.__oversightFilterState.period || "current_month";
  const college = document.getElementById("oversight-college-filter")?.value || window.__oversightFilterState.college || "";
  const customStart = document.getElementById("oversight-custom-start")?.value || window.__oversightFilterState.custom_start || "";
  const customEnd = document.getElementById("oversight-custom-end")?.value || window.__oversightFilterState.custom_end || "";

  return { period, college, custom_start: customStart, custom_end: customEnd };
}

function syncOversightFilterInputs(state = window.__oversightFilterState) {
  const periodEl = document.getElementById('oversight-period-filter');
  const collegeEl = document.getElementById('oversight-college-filter');
  const customStartEl = document.getElementById('oversight-custom-start');
  const customEndEl = document.getElementById('oversight-custom-end');

  if (periodEl) periodEl.value = state.period || 'current_month';
  if (collegeEl) collegeEl.value = state.college || '';
  if (customStartEl) customStartEl.value = state.custom_start || '';
  if (customEndEl) customEndEl.value = state.custom_end || '';

  const customDateRange = document.getElementById('custom-date-range');
  if (customDateRange) {
    customDateRange.style.display = (state.period === 'custom') ? 'grid' : 'none';
  }
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function safeNumber(value, fallback = 0) {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

async function loadOversightSummary() {
  const contentDiv = document.getElementById("oversight-summary-content");
  if (!contentDiv) return;

  if (window.__oversightSummaryInFlight) return;
  window.__oversightSummaryInFlight = true;

  const state = getOversightFilterState();
  window.__oversightFilterState = { ...state };
  syncOversightFilterInputs(window.__oversightFilterState);

  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Loading oversight summary...</p></div>';

  try {
    const { period, college, custom_start: customStart, custom_end: customEnd } = state;

    console.log("Filter values:", { period, college, customStart, customEnd });

    const params = new URLSearchParams({
      period: period,
      college: college,
      custom_start: customStart,
      custom_end: customEnd
    });

    console.log("Fetching:", `/api/president/oversight/summary/?${params}`);

    const response = await fetch(`/api/president/oversight/summary/?${params}`, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "X-CSRFToken": getCSRFToken(),
      },
    });

    console.log("Response status:", response.status);

    if (response.redirected || response.status === 302 || response.type === "opaqueredirect") {
      throw new Error("Session expired or access denied");
    }

    const contentType = response.headers.get("content-type") || "";
    console.log("Content type:", contentType);

    if (!contentType.includes("application/json")) {
      throw new Error("The server returned a non-JSON response. Please refresh or log in again.");
    }

    const data = await response.json();
    console.log("Response data:", data);

    if (!response.ok || !data || data.ok === false) {
      const message = (data && data.error) ? data.error : "Failed to load summary";
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${message}</p></div>`;
      return;
    }

    renderOversightSummary(data);
  } catch (error) {
    console.error("Failed to load oversight summary:", error);
    const message = error && error.message && error.message.includes("Session expired")
      ? "Your session has expired. Please refresh the page and log in again."
      : "Failed to load summary. Please try again.";
    contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${message}</p></div>`;
  } finally {
    window.__oversightSummaryInFlight = false;
  }
}

function renderOversightSummary(data) {
  const contentDiv = document.getElementById("oversight-summary-content");
  const summary = data.summary;
  const selectedPeriod = window.__oversightFilterState?.period || summary.period.type || 'current_month';
  const selectedCollege = window.__oversightFilterState?.college || '';
  const selectedCustomStart = window.__oversightFilterState?.custom_start || summary.period.start_date || '';
  const selectedCustomEnd = window.__oversightFilterState?.custom_end || summary.period.end_date || '';

  syncOversightFilterInputs({
    period: selectedPeriod,
    college: selectedCollege,
    custom_start: selectedCustomStart,
    custom_end: selectedCustomEnd
  });

  // Valid departments list
  const VALID_DEPARTMENTS = [
    "CCSICT",  // College of Computing Studies, Information and Communication Technology
    "IAT",     // Institute of Agricultural Technology
    "PS",      // Polytechnic School
    "CED",     // COLLEGE OF EDUCATION
    "SAS",     // School of Arts and Sciences
    "CBM",     // (Don't touch - already good)
    "CCJE"     // College of Criminal Justice Education
  ];

  // Filter members_by_college to only include valid departments
  const filteredColleges = summary.members.by_college.filter(c => VALID_DEPARTMENTS.includes(c.college));

  // Filter compliance_by_college to only include valid departments
  const filteredCompliance = summary.payments.compliance_by_college.filter(c => VALID_DEPARTMENTS.includes(c.college));

  // Store summary data globally for chart switching
  window.currentSummaryData = summary;

  // Clean up existing charts
  Object.values(oversightCharts).forEach(chart => {
    if (chart && typeof chart.destroy === 'function') {
      chart.destroy();
    }
  });
  oversightCharts = {};

  // Show the content div and remove loading state styling
  contentDiv.style.display = 'block';
  contentDiv.style.removeProperty('height');
  contentDiv.style.removeProperty('max-height');
  contentDiv.style.removeProperty('overflow-y');
  contentDiv.style.removeProperty('overflow-x');

  let html = `
    <!-- TOP FILTER BAR -->
    <div class="oversight-filter-bar no-print" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <div>
          <h3 style="margin: 0 0 4px; color: #1b5e20; font-size: 18px; font-weight: 700;">OVERSIGHT SUMMARY</h3>
          <p style="margin: 0; color: #666; font-size: 13px;">Executive overview of ISU CAUFA activities</p>
        </div>
        <button onclick="loadOversightSummary()" style="padding: 8px 16px; background: #1b5e20; border: none; border-radius: 6px; color: white; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px;">
          <i class="fas fa-sync-alt"></i> Refresh
        </button>
      </div>
      
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; align-items: end;">
        <div>
          <label style="display: block; font-size: 12px; font-weight: 600; color: #1b5e20; margin-bottom: 6px;">Period</label>
          <select id="oversight-period-filter" onchange="handlePeriodChange()" style="width: 100%; padding: 10px 14px; border-radius: 8px; border: 1px solid #cfdccc; font: inherit; background: #fbfdfb; color: #263238;">
            <option value="current_month" ${selectedPeriod === 'current_month' ? 'selected' : ''}>Current Month</option>
            <option value="previous_month" ${selectedPeriod === 'previous_month' ? 'selected' : ''}>Previous Month</option>
            <option value="current_year" ${selectedPeriod === 'current_year' ? 'selected' : ''}>Current Year</option>
            <option value="custom" ${selectedPeriod === 'custom' ? 'selected' : ''}>Custom Range</option>
          </select>
        </div>

        <div id="custom-date-range" style="display: ${selectedPeriod === 'custom' ? 'grid' : 'none'}; grid-template-columns: 1fr 1fr; gap: 8px;">
          <div>
            <label style="display: block; font-size: 12px; font-weight: 600; color: #1b5e20; margin-bottom: 6px;">Start Date</label>
            <input type="date" id="oversight-custom-start" value="${selectedCustomStart}" style="width: 100%; padding: 10px 14px; border-radius: 8px; border: 1px solid #cfdccc; font: inherit; background: #fbfdfb; color: #263238;">
          </div>
          <div>
            <label style="display: block; font-size: 12px; font-weight: 600; color: #1b5e20; margin-bottom: 6px;">End Date</label>
            <input type="date" id="oversight-custom-end" value="${selectedCustomEnd}" style="width: 100%; padding: 10px 14px; border-radius: 8px; border: 1px solid #cfdccc; font: inherit; background: #fbfdfb; color: #263238;">
          </div>
        </div>

        <div>
          <label style="display: block; font-size: 12px; font-weight: 600; color: #1b5e20; margin-bottom: 6px;">Department</label>
          <select id="oversight-college-filter" onchange="handleDepartmentChange()" style="width: 100%; padding: 10px 14px; border-radius: 8px; border: 1px solid #cfdccc; font: inherit; background: #fbfdfb; color: #263238;">
            <option value="">All Departments</option>
            ${VALID_DEPARTMENTS.map(dept => `<option value="${dept}" ${selectedCollege === dept ? 'selected' : ''}>${dept}</option>`).join('')}
          </select>
        </div>
        
        <div>
          <button onclick="applyOversightFilters()" style="width: 100%; padding: 10px 16px; background: #fbc02d; border: none; border-radius: 8px; color: #1b1b1b; font-size: 14px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px;">
            <i class="fas fa-filter"></i> Apply Filters
          </button>
        </div>
      </div>
    </div>

    <!-- KPI CARDS ROW 1 -->
    <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; margin-bottom: 20px;">
      <!-- Total Members -->
      <div class="stat-card clickable-card" onclick="navigateToReport('members-college')" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; box-shadow: 0 4px 15px rgba(0,0,0,0.02); cursor: pointer; transition: all 0.2s; position: relative;">
        <div style="position: absolute; top: 8px; right: 8px; color: #1b5e20; opacity: 0.3; font-size: 14px;">
          <i class="fas fa-arrow-right"></i>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stat-icon" style="width: 40px; height: 40px; border-radius: 10px; background: rgba(27, 94, 32, 0.1); color: #1b5e20; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-users"></i>
          </div>
          <div>
            <div style="font-size: 13px; color: #757575; font-weight: 500;">TOTAL MEMBERS</div>
            <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${summary.members.total}</div>
            <div style="font-size: 11px; color: #757575; margin-top: 2px;">${summary.members.active} active</div>
          </div>
        </div>
      </div>

      <!-- Paid This Month -->
      <div class="stat-card clickable-card" onclick="navigateToReport('paid-unpaid')" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; box-shadow: 0 4px 15px rgba(0,0,0,0.02); cursor: pointer; transition: all 0.2s; position: relative;">
        <div style="position: absolute; top: 8px; right: 8px; color: #4caf50; opacity: 0.3; font-size: 14px;">
          <i class="fas fa-arrow-right"></i>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stat-icon accent-green" style="width: 40px; height: 40px; border-radius: 10px; background: rgba(76, 175, 80, 0.1); color: #4caf50; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-check-circle"></i>
          </div>
          <div>
            <div style="font-size: 13px; color: #757575; font-weight: 500;">PAID THIS MONTH</div>
            <div style="font-size: 28px; font-weight: bold; color: #4caf50;">${summary.payments.paid}</div>
            <div style="font-size: 11px; color: #757575; margin-top: 2px;">${summary.payments.compliance_rate}% of total</div>
          </div>
        </div>
      </div>

      <!-- Pending Claims -->
      <div class="stat-card clickable-card" onclick="navigateToReport('pending-claims')" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; box-shadow: 0 4px 15px rgba(0,0,0,0.02); cursor: pointer; transition: all 0.2s; position: relative;">
        <div style="position: absolute; top: 8px; right: 8px; color: #fbc02d; opacity: 0.3; font-size: 14px;">
          <i class="fas fa-arrow-right"></i>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stat-icon accent-yellow" style="width: 40px; height: 40px; border-radius: 10px; background: rgba(251, 192, 45, 0.15); color: #fbc02d; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-clock"></i>
          </div>
          <div>
            <div style="font-size: 13px; color: #757575; font-weight: 500;">PENDING CLAIMS</div>
            <div style="font-size: 28px; font-weight: bold; color: #fbc02d;">${summary.claims.total_pending}</div>
            <div style="font-size: 11px; color: #757575; margin-top: 2px;">${summary.claims.total_pending === 0 ? 'No pending' : 'Action needed'}</div>
          </div>
        </div>
      </div>

      <!-- Fund Balance -->
      <div class="stat-card clickable-card" onclick="navigateToReport('fund')" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; box-shadow: 0 4px 15px rgba(0,0,0,0.02); cursor: pointer; transition: all 0.2s; position: relative;">
        <div style="position: absolute; top: 8px; right: 8px; color: #2196f3; opacity: 0.3; font-size: 14px;">
          <i class="fas fa-arrow-right"></i>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stat-icon accent-blue" style="width: 40px; height: 40px; border-radius: 10px; background: rgba(33, 150, 243, 0.1); color: #2196f3; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-wallet"></i>
          </div>
          <div>
            <div style="font-size: 13px; color: #757575; font-weight: 500;">FUND BALANCE</div>
            <div style="font-size: 24px; font-weight: bold; color: #2196f3;">₱${summary.funds.current_balance.toLocaleString()}</div>
            <div style="font-size: 11px; color: #757575; margin-top: 2px;">Current balance</div>
          </div>
        </div>
      </div>
    </div>

    <!-- KPI CARDS ROW 2 -->
    <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; margin-bottom: 24px;">
      <!-- Contributions -->
      <div class="stat-card clickable-card" onclick="navigateToReport('contributions')" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; box-shadow: 0 4px 15px rgba(0,0,0,0.02); cursor: pointer; transition: all 0.2s; position: relative;">
        <div style="position: absolute; top: 8px; right: 8px; color: #9c27b0; opacity: 0.3; font-size: 14px;">
          <i class="fas fa-arrow-right"></i>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stat-icon" style="width: 40px; height: 40px; border-radius: 10px; background: rgba(156, 39, 176, 0.1); color: #9c27b0; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-hand-holding-usd"></i>
          </div>
          <div>
            <div style="font-size: 13px; color: #757575; font-weight: 500;">CONTRIBUTIONS</div>
            <div style="font-size: 24px; font-weight: bold; color: #9c27b0;">₱${summary.contributions.progress.collected.toLocaleString()}</div>
            <div style="font-size: 11px; color: #757575; margin-top: 2px;">${summary.contributions.paid} paid</div>
          </div>
        </div>
      </div>

      <!-- Medical Aid -->
      <div class="stat-card clickable-card" onclick="navigateToReport('medical-aid')" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; box-shadow: 0 4px 15px rgba(0,0,0,0.02); cursor: pointer; transition: all 0.2s; position: relative;">
        <div style="position: absolute; top: 8px; right: 8px; color: #00bcd4; opacity: 0.3; font-size: 14px;">
          <i class="fas fa-arrow-right"></i>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stat-icon" style="width: 40px; height: 40px; border-radius: 10px; background: rgba(0, 188, 212, 0.1); color: #00bcd4; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-medkit"></i>
          </div>
          <div>
            <div style="font-size: 13px; color: #757575; font-weight: 500;">MEDICAL AID</div>
            <div style="font-size: 24px; font-weight: bold; color: #00bcd4;">${summary.claims.pending_medical}</div>
            <div style="font-size: 11px; color: #757575; margin-top: 2px;">${summary.claims.pending_medical} pending</div>
          </div>
        </div>
      </div>

      <!-- Death Aid -->
      <div class="stat-card clickable-card" onclick="navigateToReport('death-aid')" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; box-shadow: 0 4px 15px rgba(0,0,0,0.02); cursor: pointer; transition: all 0.2s; position: relative;">
        <div style="position: absolute; top: 8px; right: 8px; color: #607d8b; opacity: 0.3; font-size: 14px;">
          <i class="fas fa-arrow-right"></i>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stat-icon" style="width: 40px; height: 40px; border-radius: 10px; background: rgba(96, 125, 139, 0.1); color: #607d8b; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-heart"></i>
          </div>
          <div>
            <div style="font-size: 13px; color: #757575; font-weight: 500;">DEATH AID</div>
            <div style="font-size: 24px; font-weight: bold; color: #607d8b;">${summary.claims.pending_death}</div>
            <div style="font-size: 11px; color: #757575; margin-top: 2px;">${summary.claims.pending_death} pending</div>
          </div>
        </div>
      </div>

      <!-- Released This Month -->
      <div class="stat-card" style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #dfe9df; box-shadow: 0 4px 15px rgba(0,0,0,0.02);">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stat-icon" style="width: 40px; height: 40px; border-radius: 10px; background: rgba(255, 87, 34, 0.1); color: #ff5722; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-paper-plane"></i>
          </div>
          <div>
            <div style="font-size: 13px; color: #757575; font-weight: 500;">RELEASED</div>
            <div style="font-size: 24px; font-weight: bold; color: #ff5722;">${summary.claims.total_released}</div>
            <div style="font-size: 11px; color: #757575; margin-top: 2px;">This period</div>
          </div>
        </div>
      </div>
    </div>
  `;

  // ATTENTION REQUIRED SECTION
  if (summary.attention_required && summary.attention_required.length > 0) {
    html += `
      <!-- ATTENTION REQUIRED -->
      <div style="background: #fff3e0; padding: 20px; border-radius: 12px; border: 1px solid #ffb74d; margin-bottom: 24px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
          <i class="fas fa-exclamation-triangle" style="color: #f57c00; font-size: 20px;"></i>
          <h4 style="margin: 0; color: #e65100; font-size: 16px; font-weight: 700;">ATTENTION REQUIRED</h4>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px;">
    `;
    
    summary.attention_required.forEach(item => {
      const levelColors = {
        high: '#d32f2f',
        medium: '#f57c00', 
        low: '#fbc02d'
      };
      const color = levelColors[item.level] || '#757575';
      
      html += `
        <div style="background: white; padding: 12px 16px; border-radius: 8px; border-left: 4px solid ${color}; display: flex; align-items: center; gap: 12px; cursor: pointer;" onclick="handleAttentionAction('${item.action}')">
          <i class="fas fa-${item.icon}" style="color: ${color}; font-size: 18px;"></i>
          <span style="font-size: 13px; color: #333; font-weight: 500;">${item.message}</span>
        </div>
      `;
    });
    
    html += `
        </div>
      </div>
    `;
  }

  // CHARTS GRID
  html += `
    <!-- CHARTS ROW 1 -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 20px;">
      <!-- Monthly Dues Payment Status -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-chart-pie"></i> Monthly Dues Payment Status</h4>
          <span class="panel-subtitle">${summary.period.display}</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="duesStatusChart"></canvas>
        </div>
        <div style="display: flex; justify-content: space-around; margin-top: 16px; font-size: 12px;">
          <div style="text-align: center;">
            <div style="font-weight: 600; color: #4caf50;">${summary.payments.status_breakdown.paid}</div>
            <div style="color: #757575;">Paid</div>
          </div>
          <div style="text-align: center;">
            <div style="font-weight: 600; color: #ffc107;">${summary.payments.status_breakdown.pending}</div>
            <div style="color: #757575;">Pending</div>
          </div>
          <div style="text-align: center;">
            <div style="font-weight: 600; color: #f44336;">${summary.payments.status_breakdown.unpaid}</div>
            <div style="color: #757575;">Unpaid</div>
          </div>
        </div>
      </div>

      <!-- Monthly Dues Trend -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-chart-line"></i> Monthly Dues Collection Trend</h4>
          <span class="panel-subtitle">Last 6 months</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="duesTrendChart"></canvas>
        </div>
        <div style="display: flex; gap: 16px; margin-top: 16px; font-size: 12px;">
          <button onclick="switchDuesTrendView('members')" style="background: #1b5e20; color: white; padding: 6px 16px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; border: none; cursor: pointer; transition: all 0.25s ease; box-shadow: 0 2px 8px rgba(27, 94, 32, 0.35);" id="dues-trend-members">Paid Members</button>
          <button onclick="switchDuesTrendView('amount')" style="background: transparent; color: #333; padding: 6px 16px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; border: none; cursor: pointer; transition: all 0.25s ease;" id="dues-trend-amount">Collection Amount</button>
        </div>
      </div>
    </div>

    <!-- CHARTS ROW 2 -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 20px;">
      <!-- Members by College -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-users"></i> Members by College</h4>
          <span class="panel-subtitle">Distribution</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="membersByCollegeChart"></canvas>
        </div>
      </div>

      <!-- Payment Compliance by College -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-chart-bar"></i> Payment Compliance by College</h4>
          <span class="panel-subtitle">${summary.period.display}</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="complianceByCollegeChart"></canvas>
        </div>
      </div>
    </div>

    <!-- CHARTS ROW 3 -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 20px;">
      <!-- Financial Movement -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-money-bill-wave"></i> Financial Movement</h4>
          <span class="panel-subtitle">${summary.period.display}</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="financialMovementChart"></canvas>
        </div>
      </div>

      <!-- Fund Balance Trend -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-piggy-bank"></i> Fund Balance Trend</h4>
          <span class="panel-subtitle">Last 6 months</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="fundBalanceTrendChart"></canvas>
        </div>
      </div>
    </div>

    <!-- CHARTS ROW 4 -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 20px;">
      <!-- Aid Activity -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-hand-holding-heart"></i> Medical Aid vs Death Aid</h4>
          <span class="panel-subtitle">Activity comparison</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="aidActivityChart"></canvas>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; font-size: 12px;">
          <div style="background: #e3f2fd; padding: 12px; border-radius: 8px;">
            <div style="font-weight: 600; color: #1976d2;">Medical Aid</div>
            <div>Pending: ${summary.claims.pending_medical}</div>
            <div>Approved: ${summary.claims.approved_medical}</div>
            <div>Released: ${summary.claims.released_medical}</div>
          </div>
          <div style="background: #f3e5f5; padding: 12px; border-radius: 8px;">
            <div style="font-weight: 600; color: #7b1fa2;">Death Aid</div>
            <div>Pending: ${summary.claims.pending_death}</div>
            <div>Approved: ${summary.claims.approved_death}</div>
            <div>Released: ${summary.claims.released_death}</div>
          </div>
        </div>
      </div>

      <!-- Claim Approval Pipeline -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-sitemap"></i> Claim Approval Pipeline</h4>
          <span class="panel-subtitle">Workflow stages</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="pipelineChart"></canvas>
        </div>
      </div>
    </div>

    <!-- CHARTS ROW 5 -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 20px;">
      <!-- Contribution Collection -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-coins"></i> Contribution Collection</h4>
          <span class="panel-subtitle">Progress tracking</span>
        </div>
        <div style="margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px;">
            <span>Expected: ₱${summary.contributions.progress.expected.toLocaleString()}</span>
            <span>Collected: ₱${summary.contributions.progress.collected.toLocaleString()}</span>
          </div>
          <div style="background: #e0e0e0; border-radius: 10px; height: 24px; overflow: hidden;">
            <div style="background: linear-gradient(90deg, #4caf50, #8bc34a); height: 100%; width: ${summary.contributions.progress.percentage}%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 12px;">
              ${summary.contributions.progress.percentage}%
            </div>
          </div>
          <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 12px; color: #757575;">
            <span>Remaining: ₱${summary.contributions.progress.remaining.toLocaleString()}</span>
            <span>${summary.contributions.paid} members paid</span>
          </div>
        </div>
        <div style="height: 180px; position: relative;">
          <canvas id="contributionProgressChart"></canvas>
        </div>
      </div>

      <!-- Activity Trend -->
      <div class="dashboard-panel" style="padding: 20px;">
        <div class="panel-header-row">
          <h4 class="panel-title"><i class="fas fa-calendar-days"></i> Activity Trend</h4>
          <span class="panel-subtitle">System activity</span>
        </div>
        <div style="height: 250px; position: relative;">
          <canvas id="activityTrendChart"></canvas>
        </div>
      </div>
    </div>

    <!-- RECENT ACTIVITY TIMELINE -->
    <div class="dashboard-panel" style="padding: 20px; margin-bottom: 20px;">
      <div class="panel-header-row">
        <h4 class="panel-title"><i class="fas fa-clock"></i> Recent Oversight Activity</h4>
        <span class="panel-subtitle">Latest actions</span>
      </div>
      <div style="max-height: 300px; overflow-y: auto;">
  `;

  if (summary.activity.recent && summary.activity.recent.length > 0) {
    summary.activity.recent.forEach(activity => {
      const statusColors = {
        'Pending': '#ffc107',
        'Approved': '#4caf50', 
        'Released': '#2196f3',
        'Rejected': '#f44336',
        'PAID': '#4caf50',
        'NOT_PAID': '#f44336'
      };
      const statusColor = statusColors[activity.status] || '#757575';
      
      html += `
        <div style="display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
          <div style="width: 36px; height: 36px; border-radius: 50%; background: ${statusColor}20; color: ${statusColor}; display: flex; align-items: center; justify-content: center; font-size: 14px;">
            <i class="fas fa-${activity.icon}"></i>
          </div>
          <div style="flex: 1;">
            <div style="font-size: 13px; font-weight: 600; color: #333;">${activity.description}</div>
            <div style="font-size: 11px; color: #757575;">${activity.type} • ${activity.date}</div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 13px; font-weight: 600; color: #333;">₱${activity.amount.toLocaleString()}</div>
            <div style="font-size: 11px; color: ${statusColor}; font-weight: 500;">${activity.status}</div>
          </div>
        </div>
      `;
    });
  } else {
    html += '<div style="padding: 20px; text-align: center; color: #888;">No recent activity</div>';
  }

  html += `
      </div>
    </div>

    <div style="text-align: center; color: #999; font-size: 12px; margin-top: 20px;">
      Last updated: ${data.generated_at}
    </div>
  `;

  contentDiv.innerHTML = html;

  // Store current summary data for chart switching
  window.currentSummaryData = summary;

  // Initialize charts after DOM is updated
  setTimeout(() => {
    initializeOversightCharts(summary);
  }, 100);
}

function handlePeriodChange() {
  const period = document.getElementById("oversight-period-filter").value;
  const customDateRange = document.getElementById("custom-date-range");

  if (period === "custom") {
    customDateRange.style.display = "grid";
  } else {
    customDateRange.style.display = "none";
  }

  const state = getOversightFilterState();
  window.__oversightFilterState = { ...state, period };
}

function handleDepartmentChange() {
  const state = getOversightFilterState();
  window.__oversightFilterState = { ...state, college: state.college || '' };
}

function applyOversightFilters() {
  const state = getOversightFilterState();
  window.__oversightFilterState = { ...state };

  if (state.period === "custom") {
    if (!state.custom_start || !state.custom_end) {
      alert("Please select both a start date and end date for the custom range.");
      return;
    }
    if (state.custom_start > state.custom_end) {
      alert("The custom start date cannot be later than the end date.");
      return;
    }
  }

  loadOversightSummary();
}

function handleAttentionAction(action) {
  // Navigate to appropriate section based on action type
  const actionMap = {
    'aid-requests': 'presidential-aid-requests',
    'contributions': 'president-contributions', 
    'payments': 'presidential-payments',
    'compliance': 'reports-paid-unpaid'
  };
  
  const targetId = actionMap[action];
  if (targetId) {
    const menuItem = document.querySelector(`[data-target="${targetId}"]`);
    if (menuItem) {
      menuItem.click();
    }
  }
}

function initializeOversightCharts(summary) {
  const VALID_DEPARTMENTS = [
    "CCSICT",
    "IAT",
    "PS",
    "CED",
    "SAS",
    "CBM",
    "CCJE"
  ];

  const summaryData = summary || {};
  const membersByCollege = safeArray(summaryData.members?.by_college);
  const complianceByCollege = safeArray(summaryData.payments?.compliance_by_college);
  const duesTrend = safeArray(summaryData.payments?.dues_trend);
  const balanceTrend = safeArray(summaryData.funds?.balance_trend);
  const aidActivity = safeArray(summaryData.claims?.aid_activity);
  const activityTrend = safeArray(summaryData.activity?.trend);
  const paymentStatus = summaryData.payments?.status_breakdown || {};
  const financialMovement = summaryData.funds?.financial_movement || {};
  const pipelineStages = summaryData.claims?.pipeline_stages || {};
  const contributionProgress = summaryData.contributions?.progress || {};

  const filteredColleges = membersByCollege.filter(c => VALID_DEPARTMENTS.includes(c?.college));
  const filteredCompliance = complianceByCollege.filter(c => VALID_DEPARTMENTS.includes(c?.college));

  // Chart.js default configuration
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.color = '#666';
  
  // 1. Monthly Dues Payment Status (Donut Chart)
  const duesStatusCtx = document.getElementById('duesStatusChart');
  if (duesStatusCtx) {
    oversightCharts.duesStatus = new Chart(duesStatusCtx, {
      type: 'doughnut',
      data: {
        labels: ['Paid', 'Pending', 'Unpaid'],
        datasets: [{
          data: [
            safeNumber(paymentStatus.paid),
            safeNumber(paymentStatus.pending),
            safeNumber(paymentStatus.unpaid)
          ],
          backgroundColor: ['#4caf50', '#ffc107', '#f44336'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        cutout: '70%'
      }
    });
  }

  // 2. Monthly Dues Trend (Line Chart)
  const duesTrendCtx = document.getElementById('duesTrendChart');
  if (duesTrendCtx) {
    oversightCharts.duesTrend = new Chart(duesTrendCtx, {
      type: 'line',
      data: {
        labels: duesTrend.map(d => d?.month || ''),
        datasets: [{
          label: 'Paid Members',
          data: duesTrend.map(d => safeNumber(d?.paid_members)),
          borderColor: '#1b5e20',
          backgroundColor: 'rgba(27, 94, 32, 0.1)',
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    });
  }

  // 3. Members by College (Horizontal Bar Chart)
  const membersByCollegeCtx = document.getElementById('membersByCollegeChart');
  if (membersByCollegeCtx) {
    oversightCharts.membersByCollege = new Chart(membersByCollegeCtx, {
      type: 'bar',
      data: {
        labels: filteredColleges.map(c => c?.college || ''),
        datasets: [{
          label: 'Members',
          data: filteredColleges.map(c => safeNumber(c?.count)),
          backgroundColor: '#1b5e20',
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          x: {
            beginAtZero: true
          }
        }
      }
    });
  }

  // 4. Payment Compliance by College (Horizontal Bar Chart)
  const complianceByCollegeCtx = document.getElementById('complianceByCollegeChart');
  if (complianceByCollegeCtx) {
    const complianceData = filteredCompliance.map(c => ({
      college: c?.college || '',
      compliance: safeNumber(c?.compliance)
    }));

    oversightCharts.complianceByCollege = new Chart(complianceByCollegeCtx, {
      type: 'bar',
      data: {
        labels: complianceData.map(c => c.college),
        datasets: [{
          label: 'Compliance %',
          data: complianceData.map(c => c.compliance),
          backgroundColor: complianceData.map(c => {
            if (c.compliance >= 90) return '#4caf50';
            if (c.compliance >= 70) return '#ffc107';
            return '#f44336';
          }),
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            max: 100
          }
        }
      }
    });
  }

  // 5. Financial Movement (Bar Chart)
  const financialMovementCtx = document.getElementById('financialMovementChart');
  if (financialMovementCtx) {
    oversightCharts.financialMovement = new Chart(financialMovementCtx, {
      type: 'bar',
      data: {
        labels: ['Contributions', 'Medical Aid', 'Death Aid', 'Other Inflows', 'Releases'],
        datasets: [{
          label: 'Amount',
          data: [
            safeNumber(financialMovement.contributions),
            safeNumber(financialMovement.medical_aid),
            safeNumber(financialMovement.death_aid),
            safeNumber(financialMovement.other_inflow),
            safeNumber(financialMovement.releases)
          ],
          backgroundColor: ['#4caf50', '#00bcd4', '#9c27b0', '#2196f3', '#ff5722'],
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    });
  }

  // 6. Fund Balance Trend (Line Chart)
  const fundBalanceTrendCtx = document.getElementById('fundBalanceTrendChart');
  if (fundBalanceTrendCtx) {
    oversightCharts.fundBalanceTrend = new Chart(fundBalanceTrendCtx, {
      type: 'line',
      data: {
        labels: balanceTrend.map(b => b?.month || ''),
        datasets: [{
          label: 'Fund Balance',
          data: balanceTrend.map(b => safeNumber(b?.balance)),
          borderColor: '#1b5e20',
          backgroundColor: 'rgba(27, 94, 32, 0.1)',
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: false
          }
        }
      }
    });
  }

  // 7. Aid Activity (Grouped Bar Chart)
  const aidActivityCtx = document.getElementById('aidActivityChart');
  if (aidActivityCtx) {
    oversightCharts.aidActivity = new Chart(aidActivityCtx, {
      type: 'bar',
      data: {
        labels: aidActivity.map(a => a?.month || ''),
        datasets: [
          {
            label: 'Medical Aid',
            data: aidActivity.map(a => safeNumber(a?.medical)),
            backgroundColor: '#00bcd4',
            borderRadius: 4
          },
          {
            label: 'Death Aid',
            data: aidActivity.map(a => safeNumber(a?.death)),
            backgroundColor: '#9c27b0',
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top'
          }
        },
        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    });
  }

  // 8. Claim Approval Pipeline (Funnel Chart)
  const pipelineCtx = document.getElementById('pipelineChart');
  if (pipelineCtx) {
    oversightCharts.pipeline = new Chart(pipelineCtx, {
      type: 'bar',
      data: {
        labels: ['Treasurer Review', 'Auditor Verified', 'President Approval', 'Released'],
        datasets: [{
          label: 'Claims',
          data: [
            safeNumber(pipelineStages.treasurer_review),
            safeNumber(pipelineStages.auditor_review),
            safeNumber(pipelineStages.president_review),
            safeNumber(pipelineStages.released)
          ],
          backgroundColor: ['#2196f3', '#ffc107', '#9c27b0', '#4caf50'],
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    });
  }

  // 9. Contribution Progress (Donut Chart)
  const contributionProgressCtx = document.getElementById('contributionProgressChart');
  if (contributionProgressCtx) {
    oversightCharts.contributionProgress = new Chart(contributionProgressCtx, {
      type: 'doughnut',
      data: {
        labels: ['Collected', 'Remaining'],
        datasets: [{
          data: [
            safeNumber(contributionProgress.collected),
            safeNumber(contributionProgress.remaining)
          ],
          backgroundColor: ['#4caf50', '#e0e0e0'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        cutout: '75%'
      }
    });
  }

  // 10. Activity Trend (Line Chart)
  const activityTrendCtx = document.getElementById('activityTrendChart');
  if (activityTrendCtx) {
    oversightCharts.activityTrend = new Chart(activityTrendCtx, {
      type: 'line',
      data: {
        labels: activityTrend.map(a => a?.month || ''),
        datasets: [{
          label: 'Activities',
          data: activityTrend.map(a => safeNumber(a?.activities)),
          borderColor: '#ff5722',
          backgroundColor: 'rgba(255, 87, 34, 0.1)',
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    });
  }
}

function switchDuesTrendView(view) {
  const chart = oversightCharts.duesTrend;
  if (!chart) return;
  
  const membersBtn = document.getElementById('dues-trend-members');
  const amountBtn = document.getElementById('dues-trend-amount');
  
  if (view === 'members') {
    chart.data.datasets[0].data = window.currentSummaryData.payments.dues_trend.map(d => d.paid_members);
    chart.data.datasets[0].label = 'Paid Members';
    chart.data.datasets[0].borderColor = '#1b5e20';
    chart.data.datasets[0].backgroundColor = 'rgba(27, 94, 32, 0.1)';
    membersBtn.style.background = '#1b5e20';
    membersBtn.style.color = 'white';
    membersBtn.style.boxShadow = '0 2px 8px rgba(27, 94, 32, 0.35)';
    amountBtn.style.background = 'transparent';
    amountBtn.style.color = '#333';
    amountBtn.style.boxShadow = 'none';
  } else {
    chart.data.datasets[0].data = window.currentSummaryData.payments.dues_trend.map(d => d.collected_amount);
    chart.data.datasets[0].label = 'Collection Amount';
    chart.data.datasets[0].borderColor = '#2196f3';
    chart.data.datasets[0].backgroundColor = 'rgba(33, 150, 243, 0.1)';
    amountBtn.style.background = '#1b5e20';
    amountBtn.style.color = 'white';
    amountBtn.style.boxShadow = '0 2px 8px rgba(27, 94, 32, 0.35)';
    membersBtn.style.background = 'transparent';
    membersBtn.style.color = '#333';
    membersBtn.style.boxShadow = 'none';
  }
  
  chart.update();
}

function navigateToReport(reportType) {
  const reportMap = {
    'members-college': 'reports-members-college',
    'paid-unpaid': 'reports-paid-unpaid',
    'pending-claims': 'reports-pending-claims',
    'custom-builder': 'reports-custom-builder',
    'membership-status': 'reports-membership-status',
    'medical-aid': 'reports-medical-aid',
    'death-aid': 'reports-death-aid',
    'contributions': 'reports-contributions',
    'fund': 'reports-fund'
  };

  const targetId = reportMap[reportType];
  if (targetId) {
    // Find the menu item and click it
    const menuItem = document.querySelector(`[data-target="${targetId}"]`);
    if (menuItem) {
      menuItem.click();
    } else {
      console.log(`Menu item not found for: ${targetId}`);
      // Try to find the oversight reports folder and open it
      const oversightFolder = document.querySelector('[onclick*="folder-reports"]');
      if (oversightFolder) {
        oversightFolder.click();
        setTimeout(() => {
          const menuItem = document.querySelector(`[data-target="${targetId}"]`);
          if (menuItem) {
            menuItem.click();
          }
        }, 300);
      }
    }
  }
}

// Load oversight summary on page load if the section is visible
document.addEventListener('DOMContentLoaded', () => {
  console.log("DOM loaded");
  const oversightSection = document.getElementById('view-reports-compiler');
  console.log("Oversight section:", oversightSection);
  if (oversightSection) {
    console.log("Oversight section classes:", oversightSection.classList);
    if (oversightSection.classList.contains('active')) {
      console.log("Loading oversight summary on DOM load");
      loadOversightSummary();
    } else {
      console.log("Oversight section not active");
    }

    // Use MutationObserver to detect when the section becomes active
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
          const target = mutation.target;
          if (target.id === 'view-reports-compiler' && target.classList.contains('active')) {
            console.log("Oversight section became active, loading summary");
            loadOversightSummary();
          }
        }
      });
    });

    observer.observe(oversightSection, { attributes: true });
  }

  // Add click handler to Oversight Summary menu item
  const oversightMenuItem = document.querySelector('[data-target="view-reports-compiler"]');
  if (oversightMenuItem) {
    oversightMenuItem.addEventListener('click', () => {
      console.log("Oversight Summary menu item clicked");
      setTimeout(() => {
        loadOversightSummary();
      }, 100);
    });
  }
});

// ==========================================================================
// MEMBERS BY COLLEGE REPORT
// ==========================================================================

async function generateMembersByCollegeReport() {
  const department = document.getElementById("members-college-filter").value;  // Changed from college to department
  const membershipStatus = document.getElementById("members-status-filter").value;
  const paymentStatus = document.getElementById("members-payment-filter").value;
  const year = document.getElementById("members-year-filter").value;
  const month = document.getElementById("members-month-filter").value;

  const contentDiv = document.getElementById("reports-members-college-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({
      college: department,  // Keep as 'college' for backend compatibility
      membership_status: membershipStatus,
      payment_status: paymentStatus,
      year: year,
      month: month
    });

    const response = await fetch(`/api/president/oversight/members-by-college/?${params}`, {
      method: "GET",
      headers: {
        "X-CSRFToken": getCSRFToken(),
      },
    });

    const data = await response.json();

    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }

    renderMembersByCollegeReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "members_by_college", params: params };
    attachReportToolbar("reports-members-college-content", data.report, "members_by_college", params);
    
    // Store data globally for drill-down functionality
    window.currentMembersByCollegeData = data;
  } catch (error) {
    console.error("Failed to generate members by college report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderMembersByCollegeReport(data) {
  const contentDiv = document.getElementById("reports-members-college-content");
  
  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Report Summary</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Departments</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${data.summary.total_colleges}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Members</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${data.summary.total_members}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Generated At</div>
          <div style="font-size: 14px; font-weight: 600; color: #333;">${data.summary.generated_at}</div>
        </div>
      </div>
    </div>

    <!-- College Summary Table -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">College Overview</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 800px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">College</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Total Members</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Active</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Inactive</th>
              <th style="padding: 16px; text-align: center; font-size: 14px; font-weight: 600;">Action</th>
            </tr>
          </thead>
          <tbody>
  `;

  if (data.report_data.length === 0) {
    html += '<tr><td colspan="5" style="padding: 40px; text-align: center; color: #888;">No members found matching the selected filters</td></tr>';
  } else {
    data.report_data.forEach(college => {
      html += `
        <tr style="border-bottom: 1px solid #e0e0e0; background: white; transition: background-color 0.2s;">
          <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${college.college}</td>
          <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">${college.total_members}</td>
          <td style="padding: 16px; text-align: right; font-size: 14px; color: #28a745; font-weight: 500;">${college.active_members}</td>
          <td style="padding: 16px; text-align: right; font-size: 14px; color: #dc3545; font-weight: 500;">${college.total_members - college.active_members}</td>
          <td style="padding: 16px; text-align: center;">
            <button onclick="viewCollegeMembers('${college.college}')" style="padding: 8px 16px; background: #1b5e20; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.2s;">
              View Members
            </button>
          </td>
        </tr>
      `;
    });
  }

  html += `
          </tbody>
        </table>
      </div>
    </div>

    <!-- College Members Detail Section (Hidden by default) -->
    <div id="college-members-detail" style="display: none;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h5 style="margin: 0; color: #333; font-size: 16px; font-weight: 600;" id="college-members-title">College Members</h5>
        <div style="display: flex; align-items: center; gap: 8px;">
          <button onclick="previewCollegeMembers()" style="padding: 8px 16px; background: #1b5e20; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600; cursor: pointer;">
            <i class="fas fa-eye"></i> Print Preview
          </button>
          <button onclick="hideCollegeMembers()" style="padding: 8px 16px; background: #dc3545; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600; cursor: pointer;">
            Close
          </button>
        </div>
      </div>
      <div id="college-members-table"></div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

function viewCollegeMembers(collegeName) {
  const detailSection = document.getElementById("college-members-detail");
  const titleElement = document.getElementById("college-members-title");
  const tableElement = document.getElementById("college-members-table");
  
  detailSection.style.display = "block";
  titleElement.textContent = `${collegeName} - View Members`;
  window.__currentCollegeMembersName = collegeName;
  
  // Get all college data from the report
  const contentDiv = document.getElementById("reports-members-college-content");
  const collegeData = findCollegeData(collegeName);
  
  if (!collegeData || collegeData.members.length === 0) {
    tableElement.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;">No members found</div>';
    return;
  }
  
  let html = `
    <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
      <table style="width: 100%; border-collapse: collapse; min-width: 800px;">
        <thead>
          <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
            <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Name</th>
            <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Position</th>
            <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Status</th>
          </tr>
        </thead>
        <tbody>
  `;
  
  collegeData.members.forEach(member => {
    const statusColor = member.membership_status === 'Active' ? '#28a745' : '#dc3545';
    
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white; transition: background-color 0.2s;">
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${member.full_name}</td>
        <td style="padding: 16px; font-size: 14px; color: #666;">${member.position || 'N/A'}</td>
        <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${statusColor}20; color: ${statusColor};">${member.membership_status}</span></td>
      </tr>
    `;
  });
  
  html += `
        </tbody>
      </table>
    </div>
  `;
  
  tableElement.innerHTML = html;
  
  // Scroll to detail section
  detailSection.scrollIntoView({ behavior: 'smooth' });
}

function hideCollegeMembers() {
  document.getElementById("college-members-detail").style.display = "none";
}

function previewCollegeMembers() {
  const collegeName = window.__currentCollegeMembersName;
  if (!collegeName) return;

  const collegeData = findCollegeData(collegeName);
  if (!collegeData || !collegeData.members || collegeData.members.length === 0) {
    alert("No members to preview for this college.");
    return;
  }

  const source = window.__latestOversightReport;
  const baseReport = source ? source.report : null;

  const report = {
    report_key: "members_by_college",
    report_name: `Members - ${collegeName}`,
    description: `Member roster for ${collegeName} college.`,
    generated_by: baseReport ? baseReport.generated_by : "President",
    generated_at: baseReport ? baseReport.generated_at : new Date().toLocaleString(),
    filters: [
      { label: "College", value: collegeName },
      { label: "Total Members", value: collegeData.members.length },
    ],
    summary: [
      { label: "College", value: collegeName, type: "string" },
      { label: "Total Members", value: collegeData.members.length, type: "count" },
      { label: "Active", value: collegeData.active_members || 0, type: "count" },
      { label: "Paid", value: collegeData.paid_members || 0, type: "count" },
      { label: "Unpaid", value: collegeData.unpaid_members || 0, type: "count" },
    ],
    columns: [
      { key: "member_id", label: "Member ID", align: "left" },
      { key: "full_name", label: "Name", align: "left" },
      { key: "position", label: "Position", align: "left" },
      { key: "membership_status", label: "Status", align: "left" },
      { key: "payment_status", label: "Payment", align: "left" },
    ],
    rows: collegeData.members.map(m => ({
      member_id: m.member_id,
      full_name: m.full_name,
      position: m.position || "N/A",
      membership_status: m.membership_status || "Unknown",
      payment_status: m.payment_status || "N/A",
    })),
  };

  __currentReportKey = "members_by_college";
  __currentReportParams = source && source.params ? source.params.toString() : "";
  renderReportPreviewModal(report);
}

function findCollegeData(collegeName) {
  // This function would need to access the stored report data
  // For now, we'll store it in a global variable when the report is generated
  if (window.currentMembersByCollegeData) {
    return window.currentMembersByCollegeData.report_data.find(c => c.college === collegeName);
  }
  return null;
}

// ==========================================================================
// PAID/UNPAID SUMMARY REPORT
// ==========================================================================

async function generatePaidUnpaidSummary() {
  const year = document.getElementById("paid-unpaid-year-filter").value;
  const month = document.getElementById("paid-unpaid-month-filter").value;
  const department = document.getElementById("paid-unpaid-college-filter").value;  // Changed from college to department

  const contentDiv = document.getElementById("reports-paid-unpaid-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({
      year: year,
      month: month,
      college: department  // Keep as 'college' for backend compatibility
    });

    const response = await fetch(`/api/president/oversight/paid-unpaid-summary/?${params}`, {
      method: "GET",
      headers: {
        "X-CSRFToken": getCSRFToken(),
      },
    });

    const data = await response.json();

    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }

    renderPaidUnpaidSummary(data);
    window.__latestOversightReport = { report: data.report, reportKey: "paid_unpaid_summary", params: params };
    attachReportToolbar("reports-paid-unpaid-content", data.report, "paid_unpaid_summary", params);
  } catch (error) {
    console.error("Failed to generate paid/unpaid summary:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderPaidUnpaidSummary(data) {
  const contentDiv = document.getElementById("reports-paid-unpaid-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Payment Summary for ${data.filters.month}/${data.filters.year}</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow:  0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Members</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${summary.total_members}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Paid</div>
          <div style="font-size: 28px; font-weight: bold; color: #28a745;">${summary.paid_members} <span style="font-size: 16px; color: #666;">(${summary.paid_percentage}%)</span></div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Unpaid</div>
          <div style="font-size: 28px; font-weight: bold; color: #dc3545;">${summary.unpaid_members} <span style="font-size: 16px; color: #666;">(${summary.unpaid_percentage}%)</span></div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Pending</div>
          <div style="font-size: 28px; font-weight: bold; color: #ffc107;">${summary.pending_members} <span style="font-size: 16px; color: #666;">(${summary.pending_percentage}%)</span></div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Collected</div>
          <div style="font-size: 24px; font-weight: bold; color: #1b5e20;">₱${summary.total_collected.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Collection Rate</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${summary.collection_rate}%</div>
        </div>
      </div>
    </div>

    <!-- Department Breakdown Table -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Department Breakdown</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 800px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">College</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Total</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Paid</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Pending</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Unpaid</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Compliance</th>
            </tr>
          </thead>
          <tbody>
  `;

  if (data.department_breakdown && data.department_breakdown.length > 0) {
    data.department_breakdown.forEach(dept => {
      const complianceColor = dept.compliance >= 90 ? '#28a745' : dept.compliance >= 70 ? '#ffc107' : '#dc3545';
      
      html += `
        <tr style="border-bottom: 1px solid #e0e0e0; background: white; transition: background-color 0.2s;">
          <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${dept.college}</td>
          <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">${dept.total}</td>
          <td style="padding: 16px; text-align: right; font-size: 14px; color: #28a745; font-weight: 500;">${dept.paid}</td>
          <td style="padding: 16px; text-align: right; font-size: 14px; color: #ffc107; font-weight: 500;">${dept.pending}</td>
          <td style="padding: 16px; text-align: right; font-size: 14px; color: #dc3545; font-weight: 500;">${dept.unpaid}</td>
          <td style="padding: 16px; text-align: right; font-size: 14px; color: ${complianceColor}; font-weight: 600;">${dept.compliance}%</td>
        </tr>
      `;
    });
  } else {
    html += '<tr><td colspan="6" style="padding: 40px; text-align: center; color: #888;">No department data available</td></tr>';
  }

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

// ==========================================================================
// PENDING CLAIMS REPORT
// ==========================================================================

async function generatePendingClaimsReport() {
  const claimType = document.getElementById("claims-type-filter").value;
  const department = document.getElementById("claims-college-filter").value;  // Changed from college to department

  const contentDiv = document.getElementById("reports-pending-claims-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({
      claim_type: claimType,
      college: department  // Keep as 'college' for backend compatibility
    });

    const response = await fetch(`/api/president/oversight/pending-claims/?${params}`, {
      method: "GET",
      headers: {
        "X-CSRFToken": getCSRFToken(),
      },
    });

    const data = await response.json();

    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }

    renderPendingClaimsReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "pending_claims", params: params };
    attachReportToolbar("reports-pending-claims-content", data.report, "pending_claims", params);
  } catch (error) {
    console.error("Failed to generate pending claims report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderPendingClaimsReport(data) {
  const contentDiv = document.getElementById("reports-pending-claims-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Pending Claims Summary</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Claims</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${summary.total_claims}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1-side0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Medical Claims</div>
          <div style="font-size: 28px; font-weight: bold; color: #007bff;">${summary.medical_claims}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Death Claims</div>
          <div style="font-size: 28px; font-weight: bold; color: #6c757d;">${summary.death_claims}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow:  0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Amount</div>
          <div style="font-size: 24px; font-weight: bold; color: #1b5e20;">₱${summary.total_amount_requested.toLocaleString()}</div>
        </div>
      </div>
    </div>
  `;

  if (data.claims.length === 0) {
    html += '<div style="padding: 60px 40px; text-align: center; color: #888; background: #f8f9fa; border-radius: 12px; border: 1px solid #e0e0e0;"><i class="fas fa-inbox" style="font-size: 64px; margin-bottom: 20px; color: #ccc;"></i><p style="font-size: 16px; margin: 0;">No pending claims found matching the selected filters</p></div>';
  } else {
    html += `
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 1000px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Member</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Department</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Type</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Details</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Amount</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Date Filed</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Current Stage</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Status</th>
            </tr>
          </thead>
          <tbody>
    `;

    data.claims.forEach(claim => {
      const details = claim.claim_type === 'Medical Aid' ? claim.diagnosis : `${claim.deceased_name} (${claim.relationship})`;
      const stageColor = claim.current_stage === 'Treasurer Review' ? '#007bff' : 
                       claim.current_stage === 'Auditor Verification' ? '#ffc107' :
                       claim.current_stage === 'President Approval' ? '#17a2b8' :
                       claim.current_stage === 'Contribution Collection' ? '#28a745' : '#6c757d';
      
      html += `
        <tr style="border-bottom: 1px solid #e0e0e0; background: white; transition: background-color 0.2s;">
          <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${claim.member_name}</td>
          <td style="padding: 16px; font-size: 14px; color: #666;">${claim.college}</td>
          <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${claim.claim_type === 'Medical Aid' ? '#007bff20' : '#6c757d20'}; color: ${claim.claim_type === 'Medical Aid' ? '#007bff' : '#6c757d'};">${claim.claim_type}</span></td>
          <td style="padding: 16px; font-size: 14px; color: #666;">${details}</td>
          <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">₱${claim.amount_requested.toLocaleString()}</td>
          <td style="padding: 16px; font-size: 14px; color: #666;">${claim.date_filed}</td>
          <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${stageColor}20; color: ${stageColor};">${claim.current_stage}</span></td>
          <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: #ffc10720; color: #ffc107;">${claim.status}</span></td>
        </tr>
      `;
    });

    html += `
          </tbody>
        </table>
      </div>
    `;
  }

  contentDiv.innerHTML = html;
}

// ==========================================================================
// CUSTOM REPORT BUILDER
// ==========================================================================

async function generateCustomReport() {
  const contentDiv = document.getElementById("reports-custom-builder-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating custom report...</p></div>';

  // Collect all filter values
  const filters = {
    profile: {
      department: document.getElementById("custom-department").value,
      membership_status: document.getElementById("custom-membership-status").value,
      employment_status: document.getElementById("custom-employment-status").value
    },
    payment: {
      status: document.getElementById("custom-payment-status").value,
      type: document.getElementById("custom-payment-type").value,
      amount_min: document.getElementById("custom-amount-min").value,
      amount_max: document.getElementById("custom-amount-max").value
    },
    date: {
      from: document.getElementById("custom-date-from").value,
      to: document.getElementById("custom-date-to").value
    },
    claims: {
      type: document.getElementById("custom-claim-type").value,
      status: document.getElementById("custom-claim-status").value,
      year: document.getElementById("custom-claim-year").value
    },
    release: {
      status: document.getElementById("custom-release-status").value,
      from: document.getElementById("custom-release-from").value,
      to: document.getElementById("custom-release-to").value
    }
  };

  try {
    const response = await fetch("/api/president/oversight/custom-report/", {
      method: "POST",
      headers: {
        "X-CSRFToken": getCSRFToken(),
        "Content-Type": "application/json"
      },
      body: JSON.stringify(filters)
    });

    const data = await response.json();

    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate custom report"}</p></div>`;
      return;
    }

    renderCustomReport(data);
  } catch (error) {
    console.error("Failed to generate custom report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderCustomReport(data) {
  const contentDiv = document.getElementById("reports-custom-builder-content");
  
  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Custom Report Results</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Records</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${data.summary.total_records}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Generated At</div>
          <div style="font-size: 14px; font-weight: 600; color: #333;">${data.generated_at}</div>
        </div>
      </div>
    </div>
  `;

  if (data.results.length === 0) {
    html += '<div style="padding: 60px 40px; text-align: center; color: #888; background: #f8f9fa; border-radius: 12px; border: 1px solid #e0e0e0;"><i class="fas fa-inbox" style="font-size: 64px; margin-bottom: 20px; color: #ccc;"></i><p style="font-size: 16px; margin: 0;">No records found matching the selected filters</p></div>';
  } else {
    html += `
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 1000px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Name</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Department</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Status</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Payment</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Claims</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Release</th>
            </tr>
          </thead>
          <tbody>
    `;

    data.results.forEach(record => {
      html += `
        <tr style="border-bottom: 1px solid #e0e0e0; background: white; transition: background-color 0.2s;">
          <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${record.name}</td>
          <td style="padding: 16px; font-size: 14px; color: #666;">${record.department}</td>
          <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${record.status_color}20; color: ${record.status_color};">${record.status}</span></td>
          <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${record.payment_color}20; color: ${record.payment_color};">${record.payment}</span></td>
          <td style="padding: 16px; font-size: 14px; color: #666;">${record.claims}</td>
          <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${record.release_color}20; color: ${record.release_color};">${record.release}</span></td>
        </tr>
      `;
    });

    html += `
          </tbody>
        </table>
      </div>
    `;
  }

  contentDiv.innerHTML = html;
}

function resetCustomFilters() {
  // Reset all filter fields to default values
  document.getElementById("custom-department").value = "";
  document.getElementById("custom-membership-status").value = "";
  document.getElementById("custom-employment-status").value = "";
  document.getElementById("custom-payment-status").value = "";
  document.getElementById("custom-payment-type").value = "";
  document.getElementById("custom-amount-min").value = "";
  document.getElementById("custom-amount-max").value = "";
  document.getElementById("custom-date-from").value = "";
  document.getElementById("custom-date-to").value = "";
  document.getElementById("custom-claim-type").value = "";
  document.getElementById("custom-claim-status").value = "";
  document.getElementById("custom-claim-year").value = "";
  document.getElementById("custom-release-status").value = "";
  document.getElementById("custom-release-from").value = "";
  document.getElementById("custom-release-to").value = "";
}

// ==========================================================================
// PRINT FUNCTIONALITY
// ==========================================================================

function printReport(reportType) {
  let contentDiv;
  
  // Map report types to their content div IDs
  const contentMap = {
    'members-college': 'reports-members-college-content',
    'paid-unpaid': 'reports-paid-unpaid-content', 
    'pending-claims': 'reports-pending-claims-content',
    'custom-builder': 'reports-custom-builder-content'
  };
  
  contentDiv = document.getElementById(contentMap[reportType]);
  if (!contentDiv) return;

  // Clone the content to avoid modifying the original
  const contentClone = contentDiv.cloneNode(true);
  
  // Remove sidebar and navigation elements from the clone
  const sidebar = contentClone.querySelector('.sidebar');
  if (sidebar) sidebar.remove();
  
  const headerActions = contentClone.querySelector('.header-actions');
  if (headerActions) headerActions.remove();
  
  const filterSection = contentClone.querySelector('.filter-section');
  if (filterSection) filterSection.remove();

  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>ISU CAUFA - Oversight Report</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        .report-header { text-align: center; margin-bottom: 20px; }
        .report-header h1 { color: #1b5e20; margin: 0; font-size: 24px; }
        .report-header p { color: #666; margin: 5px 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border: 1px solid #ddd; }
        th { background: #1b5e20; color: white; }
        .college-section { margin-bottom: 30px; }
        .college-header { background: #1b5e20; color: white; padding: 10px; }
        .stat-card { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; }
        img { max-width: 72px !important; max-height: 72px !important; }
        .sidebar { display: none !important; }
        .header-actions { display: none !important; }
        .filter-section { display: none !important; }
        .rpt-sheet-brand img { max-width: 72px !important; max-height: 72px !important; }
        @media print { body { -webkit-print-color-adjust: exact; } }
      </style>
    </head>
    <body>
      <div class="report-header">
        <h1>ISU CAUFA - Oversight Report</h1>
        <p>Generated: ${new Date().toLocaleString()}</p>
      </div>
      ${contentClone.innerHTML}
    </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

// ==========================================================================
// ADDITIONAL REPORT FUNCTIONS
// ==========================================================================

async function generateMembershipStatusReport() {
  const department = document.getElementById("membership-status-filter").value;
  const contentDiv = document.getElementById("reports-membership-status-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ college: department });
    const response = await fetch(`/api/president/oversight/membership-status/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderMembershipStatusReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "membership_status", params: params };
    attachReportToolbar("reports-membership-status-content", data.report, "membership_status", params);
  } catch (error) {
    console.error("Failed to generate membership status report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderMembershipStatusReport(data) {
  const contentDiv = document.getElementById("reports-membership-status-content");
  let html = `<div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
    <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Membership Status Report</h4>
    <div style="font-size: 14px; color: #666;">Total Members: ${data.summary.total_members} | Status Categories: ${data.summary.status_categories}</div>
  </div>`;
  
  // Summary cards
  html += `<div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 24px;">`;
  
  data.report_data.forEach(statusGroup => {
    const statusColor = statusGroup.status === 'Active' ? '#28a745' : 
                       statusGroup.status === 'Inactive' ? '#dc3545' : 
                       statusGroup.status === 'Retired' ? '#6c757d' : '#17a2b8';
    const barWidth = (statusGroup.count / data.summary.total_members * 100) || 0;
    
    html += `
      <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">${statusGroup.status}</div>
        <div style="font-size: 28px; font-weight: bold; color: ${statusColor};">${statusGroup.count}</div>
        <div style="margin-top: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden;">
          <div style="height: 8px; background: ${statusColor}; width: ${barWidth}%; transition: width 0.3s;"></div>
        </div>
        <div style="font-size: 12px; color: #666; margin-top: 4px;">${barWidth.toFixed(1)}% of total</div>
      </div>
    `;
  });
  
  html += `</div>`;
  
  // Status chart
  html += `
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Status Distribution</h5>
      <div style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
  `;
  
  data.report_data.forEach(statusGroup => {
    const statusColor = statusGroup.status === 'Active' ? '#28a745' : 
                       statusGroup.status === 'Inactive' ? '#dc3545' : 
                       statusGroup.status === 'Retired' ? '#6c757d' : '#17a2b8';
    const barLength = (statusGroup.count / data.summary.total_members * 50) || 0;
    const barChars = '█'.repeat(Math.floor(barLength));
    
    html += `
      <div style="display: flex; align-items: center; margin-bottom: 12px;">
        <div style="width: 120px; font-size: 14px; font-weight: 600; color: #333;">${statusGroup.status.toUpperCase()}</div>
        <div style="flex: 1; margin: 0 16px; font-family: monospace; color: ${statusColor}; font-size: 14px;">${barChars}</div>
        <div style="width: 80px; font-size: 14px; color: #666; text-align: right;">${statusGroup.count}</div>
      </div>
    `;
  });
  
  html += `
      </div>
    </div>
  `;
  
  // Detailed tables by status
  data.report_data.forEach(statusGroup => {
    html += `<div style="margin-bottom: 24px; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden;">
      <div style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white; padding: 16px 20px;">
        <h5 style="margin: 0; font-size: 18px; font-weight: 600;">${statusGroup.status} (${statusGroup.count} members)</h5>
      </div>
      <div style="padding: 0;">
        <table style="width: 100%; border-collapse: collapse;">
          <thead><tr style="background: #f8f9fa;"><th style="padding: 12px; text-align: left;">Name</th><th style="padding: 12px; text-align: left;">Position</th><th style="padding: 12px; text-align: left;">Department</th><th style="padding: 12px; text-align: left;">Date Joined</th></tr></thead>
          <tbody>`;
    statusGroup.members.forEach(member => {
      html += `<tr style="border-bottom: 1px solid #e0e0e0;"><td style="padding: 12px;">${member.full_name}</td><td style="padding: 12px;">${member.position || 'N/A'}</td><td style="padding: 12px;">${member.department}</td><td style="padding: 12px;">${member.date_joined}</td></tr>`;
    });
    html += `</tbody></table></div></div>`;
  });
  
  contentDiv.innerHTML = html;
}

// Placeholder functions for other reports (to be implemented later)
async function generateMembershipSummaryReport() {
  const year = document.getElementById("membership-summary-filter").value;
  const contentDiv = document.getElementById("reports-membership-summary-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ college: year });
    const response = await fetch(`/api/president/oversight/membership-summary/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderMembershipSummaryReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "membership_summary", params: params };
    attachReportToolbar("reports-membership-summary-content", data.report, "membership_summary", params);
  } catch (error) {
    console.error("Failed to generate membership summary report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderMembershipSummaryReport(data) {
  const contentDiv = document.getElementById("reports-membership-summary-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Membership Statistics</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Registered</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${summary.total_registered}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">New This Year</div>
          <div style="font-size: 28px; font-weight: bold; color: #007bff;">${summary.new_members_this_year}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Active</div>
          <div style="font-size: 28px; font-weight: bold; color: #28a745;">${summary.active_members}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Inactive</div>
          <div style="font-size: 28px; font-weight: bold; color: #dc3545;">${summary.inactive_members}</div>
        </div>
      </div>
    </div>

    <!-- By College -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">By College</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 600px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">College</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Members</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">% of Total</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.by_college.forEach(college => {
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${college.college}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">${college.count}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">${college.percentage}%</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>

    <!-- By Membership Status -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">By Membership Status</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 400px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Status</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Count</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.by_membership_type.forEach(type => {
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${type.type}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">${type.count}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>

    <!-- Yearly Trend -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Membership Trend</h5>
      <div style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
  `;

  data.yearly_trend.forEach(year => {
    const barWidth = (year.count / summary.total_registered * 100) || 0;
    html += `
      <div style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
          <span style="font-size: 14px; font-weight: 600; color: #333;">${year.year}</span>
          <span style="font-size: 14px; color: #666;">${year.count} members</span>
        </div>
        <div style="background: #e0e0e0; border-radius: 4px; overflow: hidden;">
          <div style="height: 24px; background: #1b5e20; width: ${barWidth}%; transition: width 0.3s;"></div>
        </div>
      </div>
    `;
  });

  html += `
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

async function generateMonthlyDuesSummaryReport() {
  const year = document.getElementById("monthly-dues-year-filter").value;
  const contentDiv = document.getElementById("reports-monthly-dues-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ year: year });
    const response = await fetch(`/api/president/oversight/monthly-dues-summary/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderMonthlyDuesSummaryReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "monthly_dues_summary", params: params };
    attachReportToolbar("reports-monthly-dues-content", data.report, "monthly_dues_summary", params);
  } catch (error) {
    console.error("Failed to generate monthly dues summary report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderMonthlyDuesSummaryReport(data) {
  const contentDiv = document.getElementById("reports-monthly-dues-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Monthly Dues Summary for ${data.filters.year}</h4>
      <div style="font-size: 14px; color: #666; margin-bottom: 16px;">Expected per member: ₱${summary.expected_per_month}</div>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Expected Collections</div>
          <div style="font-size: 24px; font-weight: bold; color: #1b5e20;">₱${summary.total_expected.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Collected</div>
          <div style="font-size: 24px; font-weight: bold; color: #28a745;">₱${summary.total_collected.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Unpaid</div>
          <div style="font-size: 24px; font-weight: bold; color: #dc3545;">₱${summary.total_unpaid.toLocaleString()}</div>
        </div>
      </div>
    </div>

    <!-- Monthly Trend -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Monthly Trend</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 800px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Month</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Expected</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Collected</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Unpaid</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.monthly_breakdown.forEach(month => {
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${month.month_name}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">₱${month.expected.toLocaleString()}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #28a745; font-weight: 500;">₱${month.collected.toLocaleString()}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #dc3545; font-weight: 500;">₱${month.unpaid.toLocaleString()}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>

    <!-- Payment Method -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Payment Method</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 600px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Payment Method</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Members</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Amount</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.payment_methods.forEach(method => {
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${method.method}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">${method.members}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">₱${method.amount.toLocaleString()}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

async function generateContributionsSummaryReport() {
  const year = document.getElementById("contributions-year-filter").value;
  const contentDiv = document.getElementById("reports-contributions-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ year: year });
    const response = await fetch(`/api/president/oversight/contributions-summary/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderContributionsSummaryReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "contributions_summary", params: params };
    attachReportToolbar("reports-contributions-content", data.report, "contributions_summary", params);
  } catch (error) {
    console.error("Failed to generate contributions summary report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderContributionsSummaryReport(data) {
  const contentDiv = document.getElementById("reports-contributions-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Contributions Summary for ${data.filters.year}</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Contributions</div>
          <div style="font-size: 24px; font-weight: bold; color: #1b5e20;">₱${summary.total_contributions.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Collected</div>
          <div style="font-size: 24px; font-weight: bold; color: #28a745;">₱${summary.total_collected.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Medical Aid</div>
          <div style="font-size: 20px; font-weight: bold; color: #007bff;">₱${summary.medical_expected.toLocaleString()}</div>
          <div style="font-size: 12px; color: #666; margin-top: 4px;">Collected: ₱${summary.medical_collected.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Death Aid</div>
          <div style="font-size: 20px; font-weight: bold; color: #6c757d;">₱${summary.death_expected.toLocaleString()}</div>
          <div style="font-size: 12px; color: #666; margin-top: 4px;">Collected: ₱${summary.death_collected.toLocaleString()}</div>
        </div>
      </div>
    </div>

    <!-- Contributions Table -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Contribution Details</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 800px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Aid Case</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Type</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Expected</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Collected</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Remaining</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Status</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.contributions_table.forEach(contribution => {
    const statusColor = contribution.status === 'Complete' ? '#28a745' : '#ffc107';
    
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333; font-family: monospace;">${contribution.case_id}</td>
        <td style="padding: 16px; font-size: 14px; color: #333;">${contribution.type}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">₱${contribution.expected.toLocaleString()}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #28a745; font-weight: 500;">₱${contribution.collected.toLocaleString()}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #dc3545; font-weight: 500;">₱${contribution.remaining.toLocaleString()}</td>
        <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${statusColor}20; color: ${statusColor};">${contribution.status}</span></td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

async function generateFundSummaryReport() {
  const year = document.getElementById("fund-year-filter").value;
  const contentDiv = document.getElementById("reports-fund-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ year: year });
    const response = await fetch(`/api/president/oversight/fund-summary/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderFundSummaryReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "fund_summary", params: params };
    attachReportToolbar("reports-fund-content", data.report, "fund_summary", params);
  } catch (error) {
    console.error("Failed to generate fund summary report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderFundSummaryReport(data) {
  const contentDiv = document.getElementById("reports-fund-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Fund Summary for ${data.filters.year}</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Opening Balance</div>
          <div style="font-size: 24px; font-weight: bold; color: #1b5e20;">₱${summary.opening_balance.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Inflow</div>
          <div style="font-size: 24px; font-weight: bold; color: #28a745;">₱${summary.total_inflow.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Outflow</div>
          <div style="font-size: 24px; font-weight: bold; color: #dc3545;">₱${summary.total_outflow.toLocaleString()}</div>
        </div>
        <div class="stat-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Current Balance</div>
          <div style="font-size: 32px; font-weight: bold; color: #1b5e20;">₱${summary.current_balance.toLocaleString()}</div>
        </div>
      </div>
    </div>

    <!-- Fund Activity -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Fund Activity</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 800px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Date</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Description</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Inflow</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Outflow</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Balance</th>
            </tr>
          </thead>
          <tbody>
  `;

  let runningBalance = summary.opening_balance;
  data.fund_activity.forEach(transaction => {
    runningBalance += transaction.inflow - transaction.outflow;
    
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333;">${transaction.date}</td>
        <td style="padding: 16px; font-size: 14px; color: #333;">${transaction.description}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #28a745; font-weight: 500;">${transaction.inflow > 0 ? '₱' + transaction.inflow.toLocaleString() : '-'}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #dc3545; font-weight: 500;">${transaction.outflow > 0 ? '₱' + transaction.outflow.toLocaleString() : '-'}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333; font-weight: 600;">₱${runningBalance.toLocaleString()}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

async function generateMedicalAidReport() {
  const year = document.getElementById("medical-aid-year-filter").value;
  const contentDiv = document.getElementById("reports-medical-aid-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ year: year });
    const response = await fetch(`/api/president/oversight/medical-aid/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderMedicalAidReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "medical_aid", params: params };
    attachReportToolbar("reports-medical-aid-content", data.report, "medical_aid", params);
  } catch (error) {
    console.error("Failed to generate medical aid report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderMedicalAidReport(data) {
  const contentDiv = document.getElementById("reports-medical-aid-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Medical Aid Status for ${data.filters.year}</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Requests</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${summary.total_requests}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Pending</div>
          <div style="font-size: 28px; font-weight: bold; color: #ffc107;">${summary.pending}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Approved</div>
          <div style="font-size: 28px; font-weight: bold; color: #28a745;">${summary.approved}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Released</div>
          <div style="font-size: 28px; font-weight: bold; color: #007bff;">${summary.released}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Rejected</div>
          <div style="font-size: 28px; font-weight: bold; color: #dc3545;">${summary.rejected}</div>
        </div>
      </div>
    </div>

    <!-- Medical Aid Table -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Medical Aid Cases</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 1000px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Member</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Bill Amount</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Expected Contribution</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Contributions</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Released</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Status</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Date</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.medical_table.forEach(item => {
    const statusColor = item.status === 'Released' ? '#007bff' : 
                       item.status === 'Approved' ? '#28a745' : 
                       item.status === 'Pending' || item.status === 'Under Review' ? '#ffc107' : '#dc3545';
    
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${item.member}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">₱${item.bill_amount.toLocaleString()}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #666;">₱${item.expected_contribution}/member</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #28a745; font-weight: 500;">₱${item.contributions.toLocaleString()}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #007bff; font-weight: 500;">₱${item.released.toLocaleString()}</td>
        <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${statusColor}20; color: ${statusColor};">${item.status}</span></td>
        <td style="padding: 16px; font-size: 14px; color: #666;">${item.date}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

async function generateDeathAidReport() {
  const year = document.getElementById("death-aid-year-filter").value;
  const contentDiv = document.getElementById("reports-death-aid-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ year: year });
    const response = await fetch(`/api/president/oversight/death-aid/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderDeathAidReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "death_aid", params: params };
    attachReportToolbar("reports-death-aid-content", data.report, "death_aid", params);
  } catch (error) {
    console.error("Failed to generate death aid report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderDeathAidReport(data) {
  const contentDiv = document.getElementById("reports-death-aid-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Death Aid Status for ${data.filters.year}</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Requests</div>
          <div style="font-size: 28px; font-weight: bold; color: #1b5e20;">${summary.total_requests}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Pending</div>
          <div style="font-size: 28px; font-weight: bold; color: #ffc107;">${summary.pending}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Approved</div>
          <div style="font-size: 28px; font-weight: bold; color: #28a745;">${summary.approved}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Released</div>
          <div style="font-size: 28px; font-weight: bold; color: #007bff;">${summary.released}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Rejected</div>
          <div style="font-size: 28px; font-weight: bold; color: #dc3545;">${summary.rejected}</div>
        </div>
      </div>
    </div>

    <!-- Beneficiary Categories Reference -->
    <div style="margin-bottom: 24px; background: #e3f2fd; padding: 16px; border-radius: 8px; border: 1px solid #bbdefb;">
      <h5 style="margin: 0 0 12px; color: #1976d2; font-size: 14px; font-weight: 600;">Beneficiary Categories & Contribution Amounts</h5>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; font-size: 13px; color: #424242;">
        <div><strong>Member:</strong> ₱500</div>
        <div><strong>Husband/Wife:</strong> ₱300</div>
        <div><strong>Parents/Children:</strong> ₱250</div>
        <div><strong>Brother/Sister (Full Blood):</strong> ₱100</div>
      </div>
    </div>

    <!-- Death Aid Table -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Death Aid Cases</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 1000px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Requester</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Beneficiary</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Category</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Contribution</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Contributions</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Status</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Date</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.death_table.forEach(item => {
    const statusColor = item.status === 'Released' ? '#007bff' : 
                       item.status === 'Approved' ? '#28a745' : 
                       item.status === 'Pending' || item.status === 'Under Review' ? '#ffc107' : '#dc3545';
    
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${item.requester}</td>
        <td style="padding: 16px; font-size: 14px; color: #333;">${item.beneficiary}</td>
        <td style="padding: 16px; font-size: 14px; color: #666;">${item.category}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">₱${item.contribution}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #28a745; font-weight: 500;">₱${item.contributions.toLocaleString()}</td>
        <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${statusColor}20; color: ${statusColor};">${item.status}</span></td>
        <td style="padding: 16px; font-size: 14px; color: #666;">${item.date}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

async function generateApprovedClaimsReport() {
  const year = document.getElementById("approved-claims-year-filter").value;
  const contentDiv = document.getElementById("reports-approved-claims-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ year: year });
    const response = await fetch(`/api/president/oversight/approved-claims/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderApprovedClaimsReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "approved_claims", params: params };
    attachReportToolbar("reports-approved-claims-content", data.report, "approved_claims", params);
  } catch (error) {
    console.error("Failed to generate approved claims report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderApprovedClaimsReport(data) {
  const contentDiv = document.getElementById("reports-approved-claims-content");

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Approved Claims for ${data.filters.year}</h4>
      <div style="font-size: 14px; color: #666;">Total Approved: ${data.summary.total_approved}</div>
    </div>

    <!-- Approved Claims Table -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Approval Chain</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 1000px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Type</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Requester</th>
              <th style="padding: 16px; text-align: center; font-size: 14px; font-weight: 600;">Treasurer</th>
              <th style="padding: 16px; text-align: center; font-size: 14px; font-weight: 600;">Auditor</th>
              <th style="padding: 16px; text-align: center; font-size: 14px; font-weight: 600;">President</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Approval Date</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.approved_table.forEach(claim => {
    const treasurerColor = claim.treasurer === 'Approved' ? '#28a745' : '#dc3545';
    const auditorColor = claim.auditor === 'Approved' ? '#28a745' : '#dc3545';
    const presidentColor = claim.president === 'Approved' ? '#28a745' : '#dc3545';
    
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333;">${claim.type}</td>
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${claim.requester}</td>
        <td style="padding: 16px; text-align: center;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${treasurerColor}20; color: ${treasurerColor};">${claim.treasurer}</span></td>
        <td style="padding: 16px; text-align: center;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${auditorColor}20; color: ${auditorColor};">${claim.auditor}</span></td>
        <td style="padding: 16px; text-align: center;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${presidentColor}20; color: ${presidentColor};">${claim.president}</span></td>
        <td style="padding: 16px; font-size: 14px; color: #666;">${claim.approval_date}</td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

async function generateReleasedClaimsReport() {
  const year = document.getElementById("released-claims-year-filter").value;
  const contentDiv = document.getElementById("reports-released-claims-content");
  contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Generating report...</p></div>';

  try {
    const params = new URLSearchParams({ year: year });
    const response = await fetch(`/api/president/oversight/released-claims/?${params}`, {
      method: "GET",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    const data = await response.json();
    if (!data.ok) {
      contentDiv.innerHTML = `<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to generate report"}</p></div>`;
      return;
    }
    renderReleasedClaimsReport(data);
    window.__latestOversightReport = { report: data.report, reportKey: "released_claims", params: params };
    attachReportToolbar("reports-released-claims-content", data.report, "released_claims", params);
  } catch (error) {
    console.error("Failed to generate released claims report:", error);
    contentDiv.innerHTML = '<div style="padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to generate report. Please try again.</p></div>';
  }
}

function renderReleasedClaimsReport(data) {
  const contentDiv = document.getElementById("reports-released-claims-content");
  const summary = data.summary;

  let html = `
    <div class="report-summary" style="background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #e0e0e0;">
      <h4 style="margin: 0 0 20px; color: #333; font-size: 16px; font-weight: 600;">Released Claims for ${data.filters.year}</h4>
      <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Medical Aid Released</div>
          <div style="font-size: 24px; font-weight: bold; color: #007bff;">₱${summary.total_medical_released.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Death Aid Released</div>
          <div style="font-size: 24px; font-weight: bold; color: #6c757d;">₱${summary.total_death_released.toLocaleString()}</div>
        </div>
        <div class="stat-card-mini" style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px 4px rgba(0,0,0,0.05);">
          <div style="font-size: 14px; color: #666; margin-bottom: 8px; font-weight: 500;">Total Released</div>
          <div style="font-size: 32px; font-weight: bold; color: #1b5e20;">₱${summary.total_released.toLocaleString()}</div>
        </div>
      </div>
    </div>

    <!-- Released Claims Table -->
    <div style="margin-bottom: 24px;">
      <h5 style="margin: 0 0 16px; color: #333; font-size: 16px; font-weight: 600;">Release History</h5>
      <div style="overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <table style="width: 100%; border-collapse: collapse; min-width: 1000px;">
          <thead>
            <tr style="background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white;">
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Type</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Requester</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Approved Amount</th>
              <th style="padding: 16px; text-align: right; font-size: 14px; font-weight: 600;">Released Amount</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Release Date</th>
              <th style="padding: 16px; text-align: left; font-size: 14px; font-weight: 600;">Status</th>
            </tr>
          </thead>
          <tbody>
  `;

  data.released_table.forEach(claim => {
    html += `
      <tr style="border-bottom: 1px solid #e0e0e0; background: white;">
        <td style="padding: 16px; font-size: 14px; color: #333;">${claim.type}</td>
        <td style="padding: 16px; font-size: 14px; color: #333; font-weight: 500;">${claim.requester}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #333;">₱${claim.approved_amount.toLocaleString()}</td>
        <td style="padding: 16px; text-align: right; font-size: 14px; color: #007bff; font-weight: 500;">₱${claim.released_amount.toLocaleString()}</td>
        <td style="padding: 16px; font-size: 14px; color: #666;">${claim.release_date}</td>
        <td style="padding: 16px;"><span style="display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: #007bff20; color: #007bff;">${claim.status}</span></td>
      </tr>
    `;
  });

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  contentDiv.innerHTML = html;
}

function showComingSoon(contentId) {
  const contentDiv = document.getElementById(contentId);
  contentDiv.innerHTML = '<div style="padding: 60px 40px; text-align: center; color: #888; background: #f8f9fa; border-radius: 12px; border: 1px solid #e0e0e0;"><i class="fas fa-tools" style="font-size: 64px; margin-bottom: 20px; color: #ccc;"></i><p style="font-size: 16px; margin: 0;">This report is under development. Please use the Custom Report Builder for advanced filtering.</p></div>';
}

// ==========================================================================
// PRINT AND EXPORT FUNCTIONALITY
// ==========================================================================

function printReport(reportTitle) {
  // Create a print-friendly version
  const printContent = document.getElementById("reports-content") || document.body;
  
  // Open print dialog
  const originalTitle = document.title;
  document.title = `${reportTitle} - CAUFA Oversight Report`;
  
  window.print();
  
  // Restore original title
  document.title = originalTitle;
}

function exportToCSV(tableId, filename) {
  const table = document.querySelector(tableId);
  if (!table) {
    alert("No table found to export");
    return;
  }
  
  let csv = [];
  const rows = table.querySelectorAll("tr");
  
  for (let i = 0; i < rows.length; i++) {
    const row = [], cols = rows[i].querySelectorAll("td, th");
    
    for (let j = 0; j < cols.length; j++) {
      let text = cols[j].innerText.replace(/,/g, "");
      text = text.replace(/₱/g, "PHP ");
      row.push('"' + text + '"');
    }
    
    csv.push(row.join(","));
  }
  
  const csvFile = new Blob([csv.join("\n")], { type: "text/csv" });
  const downloadLink = document.createElement("a");
  downloadLink.download = filename;
  downloadLink.href = window.URL.createObjectURL(csvFile);
  downloadLink.style.display = "none";
  document.body.appendChild(downloadLink);
  downloadLink.click();
  document.body.removeChild(downloadLink);
}

// ==========================================================================
// HELPER FUNCTIONS
// ==========================================================================

function getCSRFToken() {
  const cookies = document.cookie.split(';');
  for (let cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'csrftoken') return decodeURIComponent(value);
  }
  return '';
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = String(now.getMonth() + 1).padStart(2, '0');
  const minYear = 2024;
  const maxYear = 2030;

  const yearSelects = document.querySelectorAll('[id$="-year-filter"]');
  yearSelects.forEach(select => {
    const existingValues = new Set(Array.from(select.options).map(option => Number(option.value)).filter(value => Number.isFinite(value)));

    for (let year = minYear; year <= maxYear; year++) {
      if (!existingValues.has(year)) {
        const option = document.createElement('option');
        option.value = String(year);
        option.textContent = String(year);
        select.appendChild(option);
      }
    }

    if (select.querySelector(`option[value="${currentYear}"]`)) {
      select.value = String(currentYear);
    } else if (select.querySelector(`option[value="${String(maxYear)}"]`)) {
      select.value = String(maxYear);
    }
  });

  const monthSelects = document.querySelectorAll('[id$="-month-filter"]');
  monthSelects.forEach(select => {
    if (select.querySelector(`option[value="${currentMonth}"]`)) {
      select.value = currentMonth;
    }
  });
});