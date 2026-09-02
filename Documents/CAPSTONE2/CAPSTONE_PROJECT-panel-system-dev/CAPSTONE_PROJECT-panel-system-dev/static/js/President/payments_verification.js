function formatAuditEvidence(value) {
  const evidence = String(value || "").trim();
  return evidence ? `Evidence: ${evidence}` : "—";
}

function formatAuditRemarks(value) {
  const remarks = String(value || "").trim();
  return (
    remarks ||
    "Auditor verified and forwarded to President for final executive sign-off."
  );
}

function getEl(id) {
  return document.getElementById(id);
}

function pHasData(v) {
  if (v === undefined || v === null || v === "") return false;
  const s = String(v).trim();
  return s !== "" && s !== "—";
}

function pHideIfEmpty(elId, value) {
  const el = getEl(elId);
  if (!el) return;
  const wrap = el.closest(".readonly-field");
  if (!wrap) return;
  wrap.style.display = pHasData(value) ? "" : "none";
}

function updatePresidentNotifDots() {
  const dot = getEl("approval-desk-dot");
  if (dot) {
    const paymentsCount = presidentialQueueCache.length || 0;
    const aidsCount =
      (typeof db !== "undefined" && db.pendingAids && db.pendingAids.length) || 0;
    const finishCount = (typeof window.__finishApprovalCount !== "undefined" ? window.__finishApprovalCount : 0) || 0;
    const contribCount = (typeof contributionsCache !== "undefined" ? contributionsCache.length : 0) || 0;
    const regCount = (typeof window.__presidentRegCount !== "undefined" ? window.__presidentRegCount : 0) || 0;
    const total = paymentsCount + aidsCount + finishCount + contribCount + regCount;
    dot.style.display = total > 0 ? "inline-flex" : "none";
    dot.textContent = total > 0 ? total : "";
    dot.setAttribute("data-zero", total > 0 ? "0" : "1");
    dot.classList.toggle("show", total > 0);
  }

  const pDot = getEl("pres-payments-dot");
  if (pDot) {
    const count = presidentialQueueCache.length || 0;
    pDot.style.display = count > 0 ? "inline-flex" : "none";
    pDot.textContent = count > 0 ? count : "";
    pDot.setAttribute("data-zero", count > 0 ? "0" : "1");
    pDot.classList.toggle("show", count > 0);
  }

  const aDot = getEl("pres-aid-dot");
  if (aDot) {
    const aidsCount =
      (typeof db !== "undefined" && db.pendingAids && db.pendingAids.length) || 0;
    aDot.style.display = aidsCount > 0 ? "inline-flex" : "none";
    aDot.textContent = aidsCount > 0 ? aidsCount : "";
    aDot.setAttribute("data-zero", aidsCount > 0 ? "0" : "1");
    aDot.classList.toggle("show", aidsCount > 0);
  }
  if (typeof window.normalizeNotifDots === "function") window.normalizeNotifDots();
}

function ppGetChecked(id) {
  var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]:checked"), vals = [];
  for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v !== "") vals.push(v); }
  return vals;
}function ppGetAllValues(id) {
  var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]"), vals = [];
  for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") vals.push(cbs[i].value); }
  return vals;
}
function ppToggleAll(containerId, checked) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var cbs = container.querySelectorAll('input[type="checkbox"]');
  for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") cbs[i].checked = checked; }
  ppApplyFilter();
}
function ppSyncAll(containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var cbs = container.querySelectorAll('input[type="checkbox"]');
  var allBox = cbs.length > 0 ? cbs[0] : null;
  if (!allBox) return;
  var allChecked = true;
  for (var i = 1; i < cbs.length; i++) { if (!cbs[i].checked) { allChecked = false; break; } }
  allBox.checked = allChecked;
  ppApplyFilter();
}
function ppToggleFilter() {
  var card = document.getElementById("ppFilterCard");
  if (!card) return;
  var opening = card.style.display === "none";
  card.style.display = opening ? "block" : "none";
  if (opening) {
    ppFillFilters();
    var handler = function(e) {
      var btn = document.querySelector('[onclick="ppToggleFilter()"]');
      if (card.contains(e.target) || (btn && btn.contains(e.target))) return;
      document.removeEventListener("click", handler);
      card.style.display = "none";
      ppApplyFilter();
    };
    setTimeout(function() { document.addEventListener("click", handler); }, 0);
  }
}
function ppFillFilters() {
  var types = {}, i, p, arr = (db && db.pendingPayments) ? db.pendingPayments : [];
  for (i = 0; i < arr.length; i++) { p = arr[i]; if (p.type) types[p.type] = 1; }
  var tk = Object.keys(types).sort();
  var tc = document.getElementById("ppTypeCheckboxes");
  if (tc) {
    tc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="ppToggleAll(\'ppTypeCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
    for (i = 0; i < tk.length; i++) tc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' + tk[i] + '" checked onchange="ppSyncAll(\'ppTypeCheckboxes\');ppApplyFilter()"> <span>' + tk[i] + '</span></label>';
  }
}
function ppApplyFilter() {
  var types = ppGetChecked("ppTypeCheckboxes");
  if (types.length === 0) { types = ppGetAllValues("ppTypeCheckboxes"); ppSyncAll("ppTypeCheckboxes"); }
  renderPendingTable(presidentialQueueCache, types);
}

let presidentialQueueCache = [];

document.addEventListener("turbo:load", function () {
  updatePresidentNotifDots();
  loadPresidentialQueue();
  loadPresidentialAidsQueue();

  const ppSelectAll = document.getElementById("pp-select-all");
  if (ppSelectAll) {
    ppSelectAll.addEventListener("change", function () {
      const checked = this.checked;
      document.querySelectorAll("#pendingPaymentsTable .pp-row-check").forEach(cb => {
        cb.checked = checked;
        const id = cb.value;
        if (checked) ppState.selectedIds.add(id);
        else ppState.selectedIds.delete(id);
        const row = cb.closest("tr");
        if (row) row.classList.toggle("selected-row", checked);
      });
      updatePpBatchBar();
    });
  }
  document.getElementById("pp-batch-approve")?.addEventListener("click", function () {
    submitPpBatchVerify("Approved");
  });
  document.getElementById("pp-batch-reject")?.addEventListener("click", function () {
    submitPpBatchVerify("Rejected");
  });
  document.getElementById("pp-batch-clear")?.addEventListener("click", function () {
    clearPpSelection();
  });
});

async function loadPresidentialQueue() {
  try {
    const response = await fetch("/api/payments/presidential-queue/");
    const result = await response.json();

    if (result.success) {
      presidentialQueueCache = result.payments || [];
      if (typeof db !== "undefined") db.pendingPayments = presidentialQueueCache;
      renderPendingTable(presidentialQueueCache);
      ppFillFilters();
    } else {
      console.error("Queue Retrieval Error:", result.message);
      presidentialQueueCache = [];
      if (typeof db !== "undefined") db.pendingPayments = [];
    }
  } catch (error) {
    console.error("Failed to fetch executive data:", error);
    presidentialQueueCache = [];
    if (typeof db !== "undefined") db.pendingPayments = [];
  } finally {
    updatePresidentNotifDots();
  }
}

let ppState = { selectedIds: new Set() };

function renderPendingTable(payments, filterTypes) {
  const tbody = document.querySelector("#pendingPaymentsTable tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  // Apply filter if provided
  let filteredPayments = payments;
  if (filterTypes && filterTypes.length > 0) {
    filteredPayments = payments.filter(item => filterTypes.includes(item.type));
  }

  if (!filteredPayments || filteredPayments.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#757575;">No active entries found inside verification workspace.</td></tr>`;
    updatePpBatchBar();
    return;
  }

  filteredPayments.forEach((item) => {
    const row = document.createElement("tr");
    row.style.cursor = "pointer";
    const ref = item.reference_code || "—";
    const name = item.member_name || "—";
    const amount =
      item.amount_paid != null
        ? `₱${Number(item.amount_paid).toLocaleString(undefined, { minimumFractionDigits: 2 })}`
        : "—";
    const method = item.payment_method || "—";
    const id = item.id != null ? item.id : "";

    if (ppState.selectedIds.has(String(id))) {
      row.classList.add("selected-row");
    }

    let typeLabel = method;
    let typeBadge = "badge badge-info";
    if (item.type === "monthly_dues_salary") {
      typeLabel = "Monthly Dues (Salary Deduction)";
      typeBadge = "badge-monthly-dues-salary";
    } else if (item.type === "monthly_dues_otc") {
      typeLabel = "Monthly Dues (OTC)";
      typeBadge = "badge-monthly-dues-otc";
    } else if (item.type === "membership_fee") {
      typeLabel = "Membership Fee";
      typeBadge = "badge-membership-fee";
    }

    row.innerHTML = `
      <td><input type="checkbox" class="pp-row-check" value="${id}" ${ppState.selectedIds.has(String(id)) ? "checked" : ""}></td>
      <td><strong>${ref}</strong></td>
      <td>${name}</td>
      <td>${amount}</td>
      <td><span class="${typeBadge}" style="font-size:0.75rem;">${typeLabel}</span></td>
      <td>
        <button class="btn-brand btn-brand-primary" onclick="selectPaymentRow(event, ${id})">
          Select
        </button>
      </td>
    `;
    const cb = row.querySelector(".pp-row-check");
    cb.addEventListener("click", function (e) {
      e.stopPropagation();
      togglePpRowCheck(id, this.checked);
    });
    row.addEventListener("click", function (e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
      populateDecisionDesk(item);
    });
    tbody.appendChild(row);
  });
  updatePpBatchBar();
  
  // Update select-all checkbox state
  const selectAll = document.getElementById("pp-select-all");
  if (selectAll) {
    const allBoxes = document.querySelectorAll("#pendingPaymentsTable .pp-row-check");
    selectAll.checked = allBoxes.length > 0 && Array.from(allBoxes).every((cb) => cb.checked);
  }
}

function togglePpRowCheck(id, checked) {
  if (checked) {
    ppState.selectedIds.add(String(id));
  } else {
    ppState.selectedIds.delete(String(id));
  }
  const row = document.querySelector(`#pendingPaymentsTable .pp-row-check[value="${id}"]`)?.closest("tr");
  if (row) row.classList.toggle("selected-row", checked);
  updatePpBatchBar();
}

function updatePpBatchBar() {
  const bar = document.getElementById("pp-batch-bar");
  const countEl = document.getElementById("pp-selected-count");
  const count = ppState.selectedIds.size;
  if (!bar || !countEl) return;
  countEl.textContent = count + " selected";
  bar.style.display = count > 0 ? "flex" : "none";
}

function clearPpSelection() {
  ppState.selectedIds.clear();
  document.querySelectorAll("#pendingPaymentsTable .pp-row-check").forEach(cb => cb.checked = false);
  document.querySelectorAll("#pendingPaymentsTable tr").forEach(tr => tr.classList.remove("selected-row"));
  const selectAll = document.getElementById("pp-select-all");
  if (selectAll) selectAll.checked = false;
  updatePpBatchBar();
}

async function submitPpBatchVerify(decision) {
  const ids = Array.from(ppState.selectedIds).map(Number);
  if (ids.length === 0) return;

  const label = decision === "Approved" ? "Approve" : "Reject";
  const confirmed = await Swal.fire({title:label + ' ' + ids.length + ' payment entr' + (ids.length === 1 ? 'y' : 'ies') + '?',icon:'question',showCancelButton:true,confirmButtonText:label,cancelButtonText:'Cancel'});
  if (!confirmed.isConfirmed) return;

  var ztOk = await window.ensureZeroTrust();
  if (!ztOk) return;

  if (typeof showProcessing === "function") {
    showProcessing(
      label + " " + ids.length + " payment entr" + (ids.length === 1 ? "y" : "ies") + "…"
    );
  }

  try {
    const resp = await fetch("/api/payments/presidential-decision/batch/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        ids: ids,
        decision: decision,
        remarks: decision === "Rejected" ? "Batch rejected." : "",
      }),
    });
    const data = await resp.json();
    if (typeof closeProcessing === "function") closeProcessing();
    if (!resp.ok || !data.success) {
      showToast(data.message || "Batch operation failed.", true);
      return;
    }
    showToast(`Processed ${data.processed} entr${data.processed === 1 ? "y" : "ies"} (${data.skipped} skipped).`, false);
    clearPpSelection();
    clearPaymentApprovalSelection();
    await loadPresidentialQueue();
  } catch (e) {
    if (typeof closeProcessing === "function") closeProcessing();
    showToast("Network/server error during batch operation.", true);
  }
}

function populateDecisionDesk(item) {
  document.getElementById("selectedPaymentHeader").innerText =
    `Inspecting Ref: ${item.reference_code} | ${item.member_name}`;

  document.getElementById("pReadName").innerText = item.member_name;
  document.getElementById("pReadEmpId").innerText = item.employee_id;
  document.getElementById("pReadDept").innerText = item.department;
  document.getElementById("pReadStatus").innerText = item.membership_status;
  document.getElementById("pReadContact").innerText = item.contact_info;
  document.getElementById("pReadCovered").innerText = item.covered_period;
  document.getElementById("pReadExpected").innerText =
    `₱${(item.expected || item.amount_paid).toFixed(2)}`;
  document.getElementById("pReadMethod").innerText = item.payment_method;
  document.getElementById("pReadRef").innerText = item.reference_code;
  document.getElementById("pReadEncoder").innerText = item.encoder_name;

  document.getElementById("pApprovedMembershipTypeText").innerText =
    item.membership_type;
  document.getElementById("pApprovedMembershipRefText").innerText =
    item.membership_ref;
  document.getElementById("pApprovedMembershipMonthText").innerText =
    item.membership_month;
  document.getElementById("pApprovedMembershipAmountText").innerText =
    `₱${item.membership_amount.toFixed(2)}`;

  // Auditor summary (from backend payload)
  document.getElementById("pAuditByText").innerText =
    item?.auditorName && String(item.auditorName).trim()
      ? item.auditorName
      : "—";

  document.getElementById("pAuditDateText").innerText =
    item?.auditorDate && String(item.auditorDate).trim()
      ? item.auditorDate
      : "—";

  document.getElementById("pAuditEvidenceText").innerText = formatAuditEvidence(
    item?.auditorEvidence,
  );

  document.getElementById("pAuditRemarksText").innerText = formatAuditRemarks(
    item?.auditorRemarks,
  );

  document.getElementById("pReturnCountText").innerText =
    item.return_count != null ? String(item.return_count) : "—";
  document.getElementById("pReturnedReasonText").innerText =
    item.returned_reason || "—";

  // Hide verification-summary details that carry no data
  pHideIfEmpty("pAuditEvidenceText", item?.auditorEvidence);
  pHideIfEmpty("pReturnCountText", item.return_count);
  pHideIfEmpty("pReturnedReasonText", item.returned_reason);

  // System Logs & Audit Trail card stays hidden unless timeline data exists
  const logsCard = getEl("pSystemLogsCard");
  if (logsCard) {
    logsCard.style.display =
      item.timeline && item.timeline.length > 0 ? "block" : "none";
  }

  document.getElementById("p_target_id").value = item.id;
  document.getElementById("p_approved_amount").value =
    item.amount_paid.toFixed(2);

  renderTimeline(item.timeline);
}

function selectPaymentRow(event, id) {
  event.stopPropagation();
  const targetItem = presidentialQueueCache.find((x) => x.id === id);
  if (targetItem) populateDecisionDesk(targetItem);
}

function diffObject(oldObj, newObj) {
  if (!oldObj && !newObj) return "";
  const changed = [];
  const allKeys = new Set([
    ...Object.keys(oldObj || {}),
    ...Object.keys(newObj || {}),
  ]);
  allKeys.forEach((key) => {
    if (key === "id" || key === "user_id_PK" || key === "member_id_PK") return;
    const o = oldObj ? oldObj[key] : undefined;
    const n = newObj ? newObj[key] : undefined;
    if (String(o ?? "null") !== String(n ?? "null")) {
      changed.push(
        `<div style="margin:4px 0; border-bottom:1px solid #eee; padding:4px 0;">
          <span style="color:#666; font-weight:600;">${escapeHtml(key)}</span><br>
          <span style="color:#c62828;">− ${escapeHtml(String(o ?? "null"))}</span><br>
          <span style="color:#2e7d32;">+ ${escapeHtml(String(n ?? "null"))}</span>
        </div>`
      );
    }
  });
  return changed.join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderTimeline(timelineArray) {
  const tbody = document.querySelector("#pTimelineTable tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  if (!timelineArray || timelineArray.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #757575">No history tracking points bound.</td></tr>`;
    return;
  }

  timelineArray.forEach((log, idx) => {
    const hasSnapshot = log.old_values || log.new_values;
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><small>${log.timestamp}</small></td>
      <td><span class="badge">${log.role}</span></td>
      <td>${log.user}</td>
      <td><strong>${log.action}</strong></td>
      <td><span style="font-size:0.85rem; color:#555;">${log.notes}</span></td>
      <td>${hasSnapshot ? `<button style="background:#1565c0;color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px;" onclick="openPaymentDiffModal(${idx})">View changes</button>` : '<span style="color:#999;">—</span>'}</td>
    `;
    tbody.appendChild(row);
  });

  window.__paymentTimeline = timelineArray;
}

function openPaymentDiffModal(idx) {
  const log = window.__paymentTimeline[idx];
  if (!log) return;
  openDiffModal(log.old_values, log.new_values, log.action);
}

function openDiffModal(oldValues, newValues, action) {
  const body = document.getElementById("diffModalBody");
  let html = "";
  if (action === "CREATED" && newValues) {
    const keys = Object.keys(newValues).filter((k) => k !== "id" && k !== "user_id_PK" && k !== "member_id_PK").slice(0, 10);
    html = "<div style='margin-bottom:12px;'><strong>Initial Record Values</strong></div>" +
      keys.map((k) => `<div style="margin:4px 0;"><span style="color:#666;font-weight:600;">${escapeHtml(k)}:</span> ${escapeHtml(String(newValues[k] ?? "null"))}</div>`).join("");
  } else if (action === "RESUBMITTED" && (oldValues || newValues)) {
    const diff = diffObject(oldValues, newValues);
    html = diff ? `<div style='margin-bottom:12px;'><strong>Changes Made (Old → New)</strong></div>${diff}` : "<em>No field-level changes detected.</em>";
  } else if ((action === "RETURNED" || action === "REJECTED") && newValues) {
    const keys = Object.keys(newValues).filter((k) => k !== "id" && k !== "user_id_PK" && k !== "member_id_PK").slice(0, 10);
    html = "<div style='margin-bottom:12px;'><strong>Snapshot at Time of Return</strong></div>" +
      keys.map((k) => `<div style="margin:4px 0;"><span style="color:#666;font-weight:600;">${escapeHtml(k)}:</span> ${escapeHtml(String(newValues[k] ?? "null"))}</div>`).join("");
  } else {
    html = "<em>No change data available for this entry.</em>";
  }
  body.innerHTML = html;
  document.getElementById("diffModal").style.display = "block";
}

function handleDecisionChange(selectId, remarksId) {
  const decisionElement = document.getElementById(selectId);
  const remarksField = document.getElementById(remarksId);
  const labelField = document.getElementById(remarksId + "_label");

  if (decisionElement.value === "Rejected") {
    remarksField.setAttribute("required", "true");
    labelField.innerHTML = `Decision Remarks & Directives <span style="color:#d32f2f;">(Mandatory for Rejections)</span>`;
  } else {
    remarksField.removeAttribute("required");
    labelField.innerHTML = `Decision Remarks & Directives (Optional Override)`;
  }
}

function clearPaymentApprovalSelection() {
  const form = document.getElementById("paymentApprovalForm");
  if (form) {
    form.reset();
  }
  document.getElementById("p_target_id").value = "";
  document.getElementById("selectedPaymentHeader").innerText =
    "No item selected";

  const selectors = [
    "#pReadName",
    "#pReadEmpId",
    "#pReadDept",
    "#pReadStatus",
    "#pReadContact",
    "#pReadCovered",
    "#pReadExpected",
    "#pReadMethod",
    "#pReadRef",
    "#pReadEncoder",
    "#pApprovedMembershipTypeText",
    "#pApprovedMembershipRefText",
    "#pApprovedMembershipMonthText",
    "#pApprovedMembershipAmountText",
    "#pAuditByText",
    "#pAuditDateText",
    "#pAuditEvidenceText",
    "#pAuditRemarksText",
    "#pReturnCountText",
    "#pReturnedReasonText",
  ];
  selectors.forEach((sel) => {
    const element = document.querySelector(sel);
    if (element) element.innerText = "—";
  });

  const timelineBody = document.querySelector("#pTimelineTable tbody");
  if (timelineBody) {
    timelineBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #757575;">No tracking logs compiled. Select a transaction to generate path timelines.</td></tr>`;
  }

  // Re-show any readonly-fields hidden because their data was unavailable
  ["pAuditEvidenceText", "pReturnCountText", "pReturnedReasonText"].forEach(
    (id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const wrap = el.closest(".readonly-field");
      if (wrap) wrap.style.display = "";
    }
  );
  const logsCard = getEl("pSystemLogsCard");
  if (logsCard) logsCard.style.display = "none";
}

async function loadPresidentialAidsQueue() {
  try {
    const response = await fetch("/api/president/auditor-approved-aids/list/");
    const result = await response.json();

    if (result.success) {
      db.pendingAids = result.aids || [];
    } else {
      console.error("Aids Queue Retrieval Error:", result.message);
      db.pendingAids = [];
    }
  } catch (error) {
    console.error("Failed to fetch aids data:", error);
    db.pendingAids = [];
  } finally {
    renderPendingAidsTable();
    updatePresidentNotifDots();
  }
}

async function submitPresidentialPaymentDecision(event) {
  event.preventDefault();

  const targetId = document.getElementById("p_target_id").value;
  const decision = document.getElementById("p_decision").value;
  const remarks = document.getElementById("p_remarks").value;

  if (!targetId) {
    Swal.fire({icon:'warning',title:'No Selection',text:'Please pick an active entry package from the ledger list layout beforehand.'});
    return;
  }

  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

  const payload = {
    target_id: targetId,
    decision: decision,
    remarks: remarks,
  };

  if (typeof showProcessing === "function") {
    showProcessing("Submitting " + decision + " ruling…");
  }

  try {
    const response = await fetch("/api/payments/presidential-decision/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify(payload),
    });

    const result = await response.json();
    if (typeof closeProcessing === "function") closeProcessing();

    if (result.success) {
      Swal.fire({icon:'success',title:'Transaction Updated',text:result.message});
      await loadPresidentialQueue();
      try {
        clearPaymentApprovalSelection();
      } catch (clearErr) {
        console.error("UI reset failed after successful submission:", clearErr);
      }
    } else {
      Swal.fire({icon:'error',title:'Error',text:"Execution Error: " + result.message});
    }
    } catch (error) {
    if (typeof closeProcessing === "function") closeProcessing();
    console.error("Transmission layout communication interruption: ", error);
    Swal.fire({icon:'error',title:'Critical Failure',text:"Critical failure submitting transaction ruling updates.\n\nDetails: " + (error.message || error)});
  }
}

document.addEventListener("click", function (e) {
  const modal = document.getElementById("diffModal");
  if (modal && e.target === modal) {
    modal.style.display = "none";
  }
});
