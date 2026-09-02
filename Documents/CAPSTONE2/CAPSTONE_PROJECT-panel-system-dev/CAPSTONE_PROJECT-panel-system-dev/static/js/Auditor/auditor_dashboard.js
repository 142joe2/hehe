(function () {
  "use strict";

  const CSRF_HEADER_NAME = "X-CSRFToken";

  // Chart variables - declared at top to be accessible throughout
  var heatmapDonutChart = null;
  var heatmapRateChart = null;
  var heatmapStackedChart = null;

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function showToast(message, isError = false) {
    const host = document.getElementById("toastContainer");
    if (!host) {
      alert(message);
      return;
    }
    const toast = document.createElement("div");
    toast.className = `custom-toast ${isError ? "toast-error" : ""}`;
    toast.innerHTML = `<p style="font-size:0.85rem;font-weight:500;margin:0;">${message}</p>`;
    host.appendChild(toast);
    setTimeout(() => toast.classList.add("show"), 10);
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function formatMoneyPHP(num) {
    const n = typeof num === "number" ? num : parseFloat(num || "0");
    return new Intl.NumberFormat("en-PH", {
      style: "currency",
      currency: "PHP",
    }).format(n);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderPaymentStatusBadge(status) {
    const normalized = String(status || "").toLowerCase();
    const styles = {
      paid: { bg: "#d4edda", color: "#1e7e34", icon: "check-circle" },
      "full payment": { bg: "#d4edda", color: "#1e7e34", icon: "check-circle" },
      "advance / covered": { bg: "#d1ecf1", color: "#0b7285", icon: "calendar-check" },
      advance: { bg: "#d1ecf1", color: "#0b7285", icon: "calendar-check" },
      pending: { bg: "#fff3cd", color: "#b07d0e", icon: "clock" },
      unpaid: { bg: "#f8d7da", color: "#c62828", icon: "times-circle" },
      default: { bg: "#e9ecef", color: "#495057", icon: "minus-circle" },
    };
    const s = styles[normalized] || styles.default;
    return `<span style="display:inline-flex;align-items:center;gap:6px;background:${s.bg};color:${s.color};padding:4px 10px;border-radius:20px;font-size:12px;font-weight:600;"><i class="fas fa-${s.icon}"></i>${escapeHtml(status)}</span>`;
  }

  function getPaymentSourceLabel(p) {
    return (
      p.source_label ||
      (p.type === "OTC Fee Payment" ? "Membership Fee" : "Monthly Dues")
    );
  }

  function getPaymentTypeLabel(p) {
    return (
      p.payment_type ||
      (p.type === "OTC Fee Payment" ? "OTC Payment" : "OTC Payment")
    );
  }

  /* === EDIT: Map status text to badge CSS class === */
  function getStatusBadgeClass(statusText) {
    const text = (statusText || "").toLowerCase();
    if (text.indexOf("medical") !== -1) return "badge-medical-aid";
    if (text.indexOf("death") !== -1) return "badge-death-aid";
    if (text.indexOf("salary deduction") !== -1) return "badge-monthly-dues-salary";
    if (text.indexOf("otc") !== -1 || text.indexOf("monthly dues") !== -1) return "badge-monthly-dues-otc";
    if (text.indexOf("membership") !== -1) return "badge-membership-fee";
    return "badge-zero";
  }
  /* === END EDIT === */

  const PAYMENT_VERIFICATION_FIELDS = {
    membership_fee: [
      { key: "amount", label: "Actual amount paid" },
      { key: "ref", label: "Official receipt / ref code" },
      { key: "month", label: "Deduction month / Covered Period" },
      { key: "date", label: "Payment date" },
      { key: "proof_status", label: "Uploaded proof" },
      { key: "method", label: "Payment method" },
      { key: "encoded_by", label: "Encoded by" },
    ],
    monthly_dues: [
      { key: "amount", label: "Actual amount paid" },
      { key: "ref", label: "Official receipt / ref code" },
      { key: "month", label: "Deduction month / Covered Period" },
      { key: "date", label: "Payment date" },
      { key: "proof_status", label: "Uploaded proof" },
      { key: "method", label: "Payment method" },
      { key: "encoded_by", label: "Encoded by" },
    ],
  };

  const MEMBERSHIP_FEE_VERIFICATION_FIELDS = [
    { key: "amount", label: "Actual amount paid" },
    { key: "ref", label: "Official receipt / ref code" },
    { key: "payment_date", label: "Payment date" },
    { key: "proof_status", label: "Uploaded proof" },
    { key: "payment_status", label: "Payment method" },
    { key: "encoded_by", label: "Encoded by" },
  ];

  function getFieldValue(item, fieldKey) {
    if (fieldKey === "proof_status") {
      return "Review evidence viewer above";
    }
    if (fieldKey.startsWith("member.")) {
      const subKey = fieldKey.slice(7);
      const member = item.member || {};
      return member[subKey] || "";
    }
    return item[fieldKey] || "";
  }

  function renderPaymentFieldCheckboxes(item) {
    const container = getEl("pAuditFieldCheckboxes");
    if (!container) return;

    const source = item.source || (item.type === "OTC Fee Payment" ? "membership_fee" : "monthly_dues");
    const fields = PAYMENT_VERIFICATION_FIELDS[source] || PAYMENT_VERIFICATION_FIELDS.membership_fee;

    container.innerHTML = "";
    fields.forEach(function (f) {
      const value = getFieldValue(item, f.key);
      const uid = "chk_p_" + f.key.replace(/\./g, "_");
      const wrapper = document.createElement("div");
      wrapper.style.cssText = "border:1px solid #dfe9df;border-radius:10px;margin-bottom:8px;background:#fff;overflow:hidden;";
      wrapper.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;">' +
        '<input type="checkbox" id="' +
        uid +
        '" data-field="' +
        f.key +
        '" style="flex-shrink:0;width:16px;height:16px;">' +
        '<label for="' +
        uid +
        '" style="font-weight:600;font-size:0.82rem;color:#1b5e20;margin:0;cursor:pointer;flex:1;">' +
        escapeHtml(f.label) +
        '</label>' +
        "</div>" +
        '<div class="chk-p-detail" style="display:none;padding:0 12px 12px 36px;">' +
        '<div style="font-size:0.78rem;color:#757575;margin-bottom:6px;line-height:1.3;">' +
        escapeHtml(value) +
        '</div>' +
        '<input type="text" data-remark-for="' +
        f.key +
        '" placeholder="Describe the issue..." style="width:100%;padding:6px 10px;border-radius:8px;border:1px solid #cfdccc;font-size:0.8rem;font-family:inherit;box-sizing:border-box;">' +
        "</div>";
      const chk = wrapper.querySelector('input[type="checkbox"]');
      const detail = wrapper.querySelector(".chk-p-detail");
      chk.addEventListener("change", function () {
        detail.style.display = chk.checked ? "block" : "none";
      });
      container.appendChild(wrapper);
    });
  }

  function renderMembershipFeeFieldCheckboxes(item) {
    const container = getEl("mfAuditFieldCheckboxes");
    if (!container) return;

    container.innerHTML = "";
    MEMBERSHIP_FEE_VERIFICATION_FIELDS.forEach(function (f) {
      const value = getFieldValue(item, f.key);
      const uid = "chk_mf_" + f.key.replace(/\./g, "_");
      const wrapper = document.createElement("div");
      wrapper.style.cssText = "border:1px solid #dfe9df;border-radius:10px;margin-bottom:8px;background:#fff;overflow:hidden;";
      wrapper.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;">' +
        '<input type="checkbox" id="' +
        uid +
        '" data-field="' +
        f.key +
        '" style="flex-shrink:0;width:16px;height:16px;">' +
        '<label for="' +
        uid +
        '" style="font-weight:600;font-size:0.82rem;color:#1b5e20;margin:0;cursor:pointer;flex:1;">' +
        escapeHtml(f.label) +
        '</label>' +
        "</div>" +
        '<div class="chk-mf-detail" style="display:none;padding:0 12px 12px 36px;">' +
        '<div style="font-size:0.78rem;color:#757575;margin-bottom:6px;line-height:1.3;">' +
        escapeHtml(value) +
        '</div>' +
        '<input type="text" data-remark-for="' +
        f.key +
        '" placeholder="Describe the issue..." style="width:100%;padding:6px 10px;border-radius:8px;border:1px solid #cfdccc;font-size:0.8rem;font-family:inherit;box-sizing:border-box;">' +
        "</div>";
      const chk = wrapper.querySelector('input[type="checkbox"]');
      const detail = wrapper.querySelector(".chk-mf-detail");
      chk.addEventListener("change", function () {
        detail.style.display = chk.checked ? "block" : "none";
      });
      container.appendChild(wrapper);
    });
  }

  function buildRejectionDetailsJSON(containerId) {
    const container = getEl(containerId);
    if (!container) return null;

    const checkboxes = container.querySelectorAll('input[type="checkbox"]');
    const details = [];

    checkboxes.forEach(function (chk) {
      if (!chk.checked) return;
      const field = chk.getAttribute("data-field");
      const remarkInput = container.querySelector('input[data-remark-for="' + field + '"]');
      const remark = remarkInput ? remarkInput.value.trim() : "";
      if (!field) return;
      details.push({ field: field, remarks: remark });
    });

    if (details.length === 0) return null;
    return JSON.stringify({ rejection_details: details });
  }

  function renderPaymentTypeCell(p) {
    const sourceLabel = escapeHtml(getPaymentSourceLabel(p));
    const typeLabel = escapeHtml(getPaymentTypeLabel(p));
    return `
      <span class="${getStatusBadgeClass(sourceLabel)}" style="font-size:0.72rem;">${sourceLabel}</span>
      <br>
      <span class="${getStatusBadgeClass(typeLabel)}" style="font-size:0.72rem;margin-top:4px;">${typeLabel}</span>
    `;
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  let state = {
    pendingPayments: [],
    pendingAids: [],
    pendingMembershipFees: [],
    auditedLogs: [],
    filteredAuditedLogs: [],
    auditLogPage: 1,
    selectedPaymentId: "",
    selectedAidId: "",
    selectedMembershipFeeId: "",
    selectedPaymentIds: new Set(),
    selectedAidIds: new Set(),
  };

  async function getJSON(url) {
    const resp = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || `Request failed: ${url}`);
    }
    return data;
  }

  async function postForm(url, fd) {
    const csrf = getCSRFToken();
    const headers = {
      "X-Requested-With": "XMLHttpRequest",
      Accept: "application/json",
      ...(csrf ? { [CSRF_HEADER_NAME]: csrf } : {}),
    };

    console.log("postForm request", { url, headers, formData: Array.from(fd.entries()) });
    const resp = await fetch(url, {
      method: "POST",
      body: fd,
      headers,
      credentials: "same-origin",
    });

    const clone = resp.clone();
    const data = await resp.json().catch(async () => {
      const text = await clone.text().catch(() => "");
      return { error: text || resp.statusText };
    });
    // Return data even if not ok, so caller can handle errors properly
    if (!resp.ok || !data.ok) {
      const detail = data.error || `Server error ${resp.status}`;
      console.error("postForm error", { url, status: resp.status, statusText: resp.statusText, detail });
    }
    return data;
  }

  function clearPaymentUI() {
    state.selectedPaymentId = "";

    const header = getEl("selectedPaymentHeader");
    if (header) header.innerText = "No item selected";

    const resets = [
      "pReadName",
      "pReadEmpId",
      "pReadDept",
      "pReadPos",
      "pReadContact",
      "pReadEmail",
      "pReadStatus",
      "pReadCovered",
      "pReadExpected",
      "pReadPaid",
      "pReadDate",
      "pReadMethod",
      "pReadRef",
      "pReadEncoder",
    ];
    resets.forEach((id) => {
      const el = getEl(id);
      if (el) el.innerText = "—";
    });

    const returnDetails = getEl("pAuditReturnDetails");
    if (returnDetails) returnDetails.style.display = "none";

    const pFieldContainer = getEl("pAuditFieldCheckboxes");
    if (pFieldContainer) pFieldContainer.innerHTML = "";

    if (window.renderEmptyState) {
      window.renderEmptyState();
    }

    const form = getEl("paymentVerificationForm");
    if (form) form.reset();
    const auditId = getEl("pAuditID");
    if (auditId) auditId.value = "";
    const preview = getEl("p_findings_preview");
    if (preview) preview.style.display = "none";
  }

  function clearAidUI() {
    state.selectedAidId = "";

    const header = getEl("selectedAidHeader");
    if (header) header.innerText = "No claim file selected";

    const fieldsContainer = getEl("aidInspectionFields");
    if (fieldsContainer) fieldsContainer.style.display = "none";

    if (window.renderEmptyState) {
      window.renderEmptyState("aidEvidenceScreen");
    }

    const form = getEl("aidVerificationForm");
    if (form) form.reset();
    const auditId = getEl("aAuditID");
    if (auditId) auditId.value = "";
    const auditType = getEl("aAuditType");
    if (auditType) auditType.value = "";
    const preview = getEl("a_findings_preview");
    if (preview) preview.style.display = "none";

    const typeLabel = getEl("aidInspectionTypeLabel");
    if (typeLabel) typeLabel.innerText = "";

    if (window.toggleAidAuditEvidenceRequirement) {
      window.toggleAidAuditEvidenceRequirement();
    }
  }

  function getCurrentOfficerId() {
    const el = document.getElementById("currentOfficerId");
    return el ? parseInt(el.textContent, 10) : null;
  }

  async function submitPayBatchVerify(result) {
    const ids = Array.from(state.selectedPaymentIds).map(Number);
    if (ids.length === 0) return;

    const items = state.pendingPayments
      .filter(p => state.selectedPaymentIds.has(String(p.id)))
      .map(p => ({ table_name: getPaymentTableName(p), record_id: p.entity_id }));

    if (items.length === 0) return;

    const label = result === "Verified" ? "Verify" : "Return";
    const swalResult = await Swal.fire({
      title: `${label} ${items.length} Payment Entr${items.length === 1 ? "y" : "ies"}?`,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: `Yes, ${label.toLowerCase()}`,
      cancelButtonText: "Cancel",
      reverseButtons: true,
    });
    if (!swalResult.isConfirmed) return;

    try {
      const resp = await fetch("/api/auditor/verify-batch/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          items: items,
          result: result,
          remarks: result === "Returned" ? "Batch returned for revision." : "",
        }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        showToast(data.error || "Batch operation failed.", true);
        return;
      }
      showToast(`Processed ${data.processed} entr${data.processed === 1 ? "y" : "ies"} (${data.skipped} skipped).`, false);
      clearPaySelection();
      await refreshAll();
    } catch (e) {
      showToast("Network/server error during batch operation.", true);
    }
  }

  function togglePayRowCheck(pid, checked) {
    if (checked) {
      state.selectedPaymentIds.add(String(pid));
    } else {
      state.selectedPaymentIds.delete(String(pid));
    }
    const row = document.querySelector(`#pendingPaymentsTable .pay-row-check[value="${pid}"]`)?.closest("tr");
    if (row) row.classList.toggle("selected-row", checked);
    updatePayBatchBar();
  }

  function updatePayBatchBar() {
    const bar = document.getElementById("pay-batch-bar");
    const countEl = document.getElementById("pay-selected-count");
    const count = state.selectedPaymentIds.size;
    if (!bar || !countEl) return;
    countEl.textContent = count + " selected";
    bar.style.display = count > 0 ? "flex" : "none";
  }

  function clearPaySelection() {
    state.selectedPaymentIds.clear();
    document.querySelectorAll("#pendingPaymentsTable .pay-row-check").forEach(cb => cb.checked = false);
    document.querySelectorAll("#pendingPaymentsTable tr").forEach(tr => tr.classList.remove("selected-row"));
    const selectAll = document.getElementById("pay-select-all");
    if (selectAll) selectAll.checked = false;
    updatePayBatchBar();
  }

  function getPaymentTableName(p) {
    return (p.source || "").toLowerCase() === "monthly_dues" ? "monthly_dues" : "membership_fee";
  }

  function createPaymentRow(p) {
    const tr = document.createElement("tr");
    const pid = p.id;
    if (state.selectedPaymentIds.has(String(pid))) {
      tr.classList.add("selected-row");
    }
    const currentId = getCurrentOfficerId();
    const prevReturnedByYou = p.returned_by_auditor_id_FK && currentId && Number(p.returned_by_auditor_id_FK) === currentId;
    const returnBadge = prevReturnedByYou ? ' <span style="color:#e53935;font-size:0.7rem;font-weight:600;">⚡ Previously returned by you</span>' : "";
    tr.innerHTML = `
      <td><input type="checkbox" class="pay-row-check" value="${pid}" ${state.selectedPaymentIds.has(String(pid)) ? "checked" : ""}></td>
      <td style="font-weight:600;color:#1b5e20;">${escapeHtml(p.ref || "")}</td>
      <td>${escapeHtml(p.member && p.member.member_name ? p.member.member_name : "")}${returnBadge}</td>
      <td style="font-weight:600;">${escapeHtml(formatMoneyPHP(p.amount))}</td>
      <td>${renderPaymentTypeCell(p)}</td>
      <td><button class="btn-select-glow">Select</button></td>
    `;
    const cb = tr.querySelector(".pay-row-check");
    cb.addEventListener("click", function (e) {
      e.stopPropagation();
      togglePayRowCheck(pid, this.checked);
    });
    tr.querySelector("button.btn-select-glow").addEventListener("click", function (e) {
      e.stopPropagation();
      selectPayment(pid);
    });
    tr.addEventListener("click", function (e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
      selectPayment(pid);
    });
    return tr;
  }

  function auditGetChecked(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]:checked"), vals = [];
    for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v !== "") vals.push(v); }
    return vals;
  }
  function auditGetAllValues(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]"), vals = [];
    for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") vals.push(cbs[i].value); }
    return vals;
  }
  function auditToggleAll(containerId, checked) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") cbs[i].checked = checked; }
    refreshAll();
  }
  function auditSyncAll(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    var allBox = cbs.length > 0 ? cbs[0] : null;
    if (!allBox) return;
    var allChecked = true;
    for (var i = 1; i < cbs.length; i++) { if (!cbs[i].checked) { allChecked = false; break; } }
    allBox.checked = allChecked;
  }
  window.auditToggleAll = auditToggleAll;
  window.auditSyncAll = auditSyncAll;
  window.auditGetChecked = auditGetChecked;
  window.auditGetAllValues = auditGetAllValues;

  function makeAuditToggle(cardId, fillFn, applyFn) {
    return function() {
      var card = document.getElementById(cardId);
      if (!card) return;
      var opening = card.style.display === "none";
      card.style.display = opening ? "block" : "none";
      if (opening) {
        fillFn();
        var handler = function(e) {
          if (card.contains(e.target)) return;
          document.removeEventListener("click", handler);
          card.style.display = "none";
          applyFn();
        };
        setTimeout(function() { document.addEventListener("click", handler); }, 0);
      }
    };
  }

  window.audPayToggle = makeAuditToggle("audPayFilterCard",
    function() {
      var tc = document.getElementById("audPayTypeCheckboxes");
      if (tc) {
        tc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="auditToggleAll(\'audPayTypeCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>' +
          '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="monthly_dues" checked onchange="auditSyncAll(\'audPayTypeCheckboxes\');refreshAll()"> <span>Monthly Dues</span></label>' +
          '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="membership_fee" checked onchange="auditSyncAll(\'audPayTypeCheckboxes\');refreshAll()"> <span>Membership Fee</span></label>';
      }
    }, refreshAll);
  window.audAidToggle = makeAuditToggle("audAidFilterCard",
    function() {
      var tc = document.getElementById("audAidTypeCheckboxes");
      if (tc) {
        tc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="auditToggleAll(\'audAidTypeCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>' +
          '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="medical" checked onchange="auditSyncAll(\'audAidTypeCheckboxes\');refreshAll()"> <span>Medical</span></label>' +
          '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="death" checked onchange="auditSyncAll(\'audAidTypeCheckboxes\');refreshAll()"> <span>Death Aid</span></label>';
      }
    }, refreshAll);
  window.audFeeToggle = makeAuditToggle("audFeeFilterCard",
    function() {
      var stats = {}, i, f, arr = state.pendingMembershipFees || [];
      for (i = 0; i < arr.length; i++) { f = arr[i]; if (f.payment_status) stats[f.payment_status] = 1; }
      var sk = Object.keys(stats).sort();
      var sc = document.getElementById("audFeeStatusCheckboxes");
      if (sc) {
        sc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="auditToggleAll(\'audFeeStatusCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
        for (i = 0; i < sk.length; i++) sc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' + escapeHtml(sk[i]) + '" checked onchange="auditSyncAll(\'audFeeStatusCheckboxes\');refreshAll()"> <span>' + escapeHtml(sk[i]) + '</span></label>';
      }
    }, refreshAll);

  function renderPaymentsTable() {
    const tbody = document.querySelector("#pendingPaymentsTable tbody");
    if (!tbody) return;

    var checked = auditGetChecked("audPayTypeCheckboxes");
    if (checked.length === 0) { checked = auditGetAllValues("audPayTypeCheckboxes"); auditSyncAll("audPayTypeCheckboxes"); }

    var arr = state.pendingPayments || [], flt = [], i, p;
    for (i = 0; i < arr.length; i++) {
      p = arr[i];
      var raw = p.source_label
        ? (p.source_label === "Membership Fee" ? "membership_fee" : "monthly_dues")
        : (p.type === "OTC Fee Payment" ? "membership_fee" : "monthly_dues");

      if (checked.length && checked.indexOf(raw) === -1) continue;
      if (p.payment_status === "Approved" || p.auditor_status === "Auditor Verified" || p.auditor_status === "President Approved") {
        continue;
      }
      flt.push(p);
    }

    tbody.innerHTML = "";
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      updatePayBatchBar();
      return;
    }
    flt.forEach((p) => {
      const tr = createPaymentRow(p);
      tbody.appendChild(tr);
    });
    updatePayBatchBar();
  }

  function toggleAidRowCheck(aid, checked) {
    if (checked) {
      state.selectedAidIds.add(String(aid));
    } else {
      state.selectedAidIds.delete(String(aid));
    }
    const row = document.querySelector(`#pendingAidsTable .aid-row-check[value="${aid}"]`)?.closest("tr");
    if (row) row.classList.toggle("selected-row", checked);
    updateAidBatchBar();
  }

  function updateAidBatchBar() {
    const bar = document.getElementById("aid-batch-bar");
    const countEl = document.getElementById("aid-selected-count");
    const count = state.selectedAidIds.size;
    if (!bar || !countEl) return;
    countEl.textContent = count + " selected";
    bar.style.display = count > 0 ? "flex" : "none";
  }

  function clearAidSelection() {
    state.selectedAidIds.clear();
    document.querySelectorAll("#pendingAidsTable .aid-row-check").forEach(cb => cb.checked = false);
    document.querySelectorAll("#pendingAidsTable tr").forEach(tr => tr.classList.remove("selected-row"));
    const selectAll = document.getElementById("aid-select-all");
    if (selectAll) selectAll.checked = false;
    updateAidBatchBar();
  }

  function getAidTableName(a) {
    const t = (a.type || "").toLowerCase();
    return t.includes("medical") ? "medical_aid" : "death_aid";
  }

  async function submitAidBatchVerify(result) {
    const ids = Array.from(state.selectedAidIds).map(Number);
    if (ids.length === 0) return;

    const items = state.pendingAids
      .filter(a => state.selectedAidIds.has(String(a.id)))
      .map(a => ({ table_name: getAidTableName(a), record_id: a.entity_id }));

    if (items.length === 0) return;

    const label = result === "Verified" ? "Verify" : "Return";
    const swalResult = await Swal.fire({
      title: `${label} ${items.length} Aid Entr${items.length === 1 ? "y" : "ies"}?`,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: `Yes, ${label.toLowerCase()}`,
      cancelButtonText: "Cancel",
      reverseButtons: true,
    });
    if (!swalResult.isConfirmed) return;

    try {
      const resp = await fetch("/api/auditor/verify-batch/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          items: items,
          result: result,
          remarks: result === "Returned" ? "Batch returned for revision." : "",
        }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        showToast(data.error || "Batch operation failed.", true);
        return;
      }
      showToast(`Processed ${data.processed} entr${data.processed === 1 ? "y" : "ies"} (${data.skipped} skipped).`, false);
      clearAidSelection();
      await refreshAll();
    } catch (e) {
      showToast("Network/server error during batch operation.", true);
    }
  }

  function renderAidsTable() {
    const tbody = document.querySelector("#pendingAidsTable tbody");
    if (!tbody) return;

    var checked = auditGetChecked("audAidTypeCheckboxes");
    if (checked.length === 0) { checked = auditGetAllValues("audAidTypeCheckboxes"); auditSyncAll("audAidTypeCheckboxes"); }
    var arr = state.pendingAids || [], flt = [], i, a;
    for (i = 0; i < arr.length; i++) {
      a = arr[i];
      if (checked.length) {
        var tc = (a.type || "").toLowerCase();
        var match = (checked.indexOf("medical") !== -1 && tc.indexOf("medical") !== -1) ||
                    (checked.indexOf("death") !== -1 && tc.indexOf("death") !== -1);
        if (!match) continue;
      }
      flt.push(a);
    }

    tbody.innerHTML = "";
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      updateAidBatchBar();
      return;
    }
    flt.forEach((a) => {
      const aid = a.id;
      const tr = document.createElement("tr");
      if (state.selectedAidIds.has(String(aid))) {
        tr.classList.add("selected-row");
      }
      tr.innerHTML = `
        <td><input type="checkbox" class="aid-row-check" value="${aid}" ${state.selectedAidIds.has(String(aid)) ? "checked" : ""}></td>
        <td>${a.member && a.member.member_name ? a.member.member_name : a.claimantName || ""}</td>
        <td><span class="${getStatusBadgeClass(a.type)}" style="font-size:0.75rem;">${a.type || ""}</span></td>
        <td style="font-weight:600;">${formatMoneyPHP(a.assigned_amount != null ? a.assigned_amount : (a.benefit || a.reqAmount || 0))} <span style="font-size:0.7rem;color:#90a4ae;font-weight:400;">/per member</span></td>
        <td><button class="btn-select-glow">Select</button></td>
      `;
      const cb = tr.querySelector(".aid-row-check");
      cb.addEventListener("click", function (e) {
        e.stopPropagation();
        toggleAidRowCheck(aid, this.checked);
      });
      tr.querySelector("button.btn-select-glow").addEventListener("click", function (e) {
        e.stopPropagation();
        selectAid(aid);
      });
      tr.addEventListener("click", function (e) {
        if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
        selectAid(aid);
      });
      tbody.appendChild(tr);
    });
    updateAidBatchBar();
  }

  function renderMembershipFeesTable() {
    const tbody = document.querySelector("#pendingMembershipFeesTable tbody");
    if (!tbody) return;

    var stats = auditGetChecked("audFeeStatusCheckboxes");
    if (stats.length === 0) { stats = auditGetAllValues("audFeeStatusCheckboxes"); auditSyncAll("audFeeStatusCheckboxes"); }
    var arr = state.pendingMembershipFees || [], flt = [], i, fee;
    for (i = 0; i < arr.length; i++) {
      fee = arr[i];
      if (stats.length && stats.indexOf(fee.payment_status) === -1) continue;
      flt.push(fee);
    }

    tbody.innerHTML = "";
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      return;
    }
    flt.forEach((fee) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight:600;color:#1b5e20;">${fee.ref || ""}</td>
        <td>${fee.member_name || ""}</td>
        <td style="font-weight:600;">${formatMoneyPHP(fee.amount)}</td>
        <td>${fee.payment_date || ""}</td>
        <td><span class="${getStatusBadgeClass(fee.payment_status)}" style="font-size:0.75rem;">${fee.payment_status || "Pending"}</span></td>
        <td><button class="btn-select-glow">Select</button></td>
      `;
      tr.onclick = () => selectMembershipFee(fee.fee_id);
      tbody.appendChild(tr);
    });
  }

  function setEvidenceScreen({ badgeText, titleText, descText }) {
    const badge = getEl("paymentEvidenceBadge");
    const title = getEl("paymentEvidenceTitle");
    const desc = getEl("paymentEvidenceDesc");
    const screen = getEl("paymentEvidenceScreen");

    if (badge) badge.innerText = badgeText;
    if (title) title.innerText = titleText;
    if (desc) desc.innerText = descText;
    if (screen) screen.style.borderColor = "#fbc02d";
  }

  function selectPayment(id) {
    state.selectedPaymentId = String(id);

    const item = state.pendingPayments.find((p) => String(p.id) === String(id));
    if (!item) return;

    if (item.payment_status === "Approved" || item.auditor_status === "Auditor Verified" || item.auditor_status === "President Approved") {
      showToast("This payment has already been authorized and cannot be selected for audit.", true);
      return;
    }

    const header = getEl("selectedPaymentHeader");
    if (header)
      header.innerText = `Reviewing Entry: ${item.id} (${getPaymentSourceLabel(item)} · ${getPaymentTypeLabel(item)})`;

    const m = item.member || {};
    if (getEl("pReadName")) getEl("pReadName").innerText = m.member_name || "—";
    if (getEl("pReadEmpId"))
      getEl("pReadEmpId").innerText = m.employee_id || "—";
    if (getEl("pReadDept")) getEl("pReadDept").innerText = m.department || "—";
    if (getEl("pReadPos")) getEl("pReadPos").innerText = m.position || "—";
    if (getEl("pReadContact"))
      getEl("pReadContact").innerText = m.contact || "—";
    if (getEl("pReadEmail")) getEl("pReadEmail").innerText = m.email || "—";
    if (getEl("pReadStatus"))
      getEl("pReadStatus").innerText = m.membership_status || "—";

    if (getEl("pReadCovered"))
      getEl("pReadCovered").innerText = item.month || "—";
    if (getEl("pReadExpected"))
      getEl("pReadExpected").innerText = formatMoneyPHP(item.expected);
    if (getEl("pReadPaid"))
      getEl("pReadPaid").innerText = formatMoneyPHP(item.amount);
    if (getEl("pReadDate")) getEl("pReadDate").innerText = item.date || "—";
    if (getEl("pReadMethod"))
      getEl("pReadMethod").innerText = item.method || "—";
    if (getEl("pReadRef")) getEl("pReadRef").innerText = item.ref || "—";
    if (getEl("pReadEncoder"))
      getEl("pReadEncoder").innerText = item.encoded_by || "—";

    const auditId = getEl("pAuditID");
    if (auditId) {
      const identifier = (item.source && item.entity_id != null)
        ? `${item.source}:${item.entity_id}`
        : item.entity_id || item.id;
      auditId.value = identifier;
    }
    const auditDate = getEl("pAuditDate");
    if (auditDate) auditDate.value = new Date().toLocaleString();

    const modelType =
      item.source ||
      (item.type === "OTC Fee Payment" ? "membership_fee" : "monthly_dues");
    if (window.fetchMediaForRecord) {
      window.fetchMediaForRecord(item.id, modelType).then((proof) => {
        if (proof) {
          window.renderMediaPreview(
            proof.fileUrl,
            proof.fileType,
            proof.fileName,
          );
        }
      });
    }

    renderPaymentFieldCheckboxes(item);
  }

  function selectAid(id) {
    state.selectedAidId = String(id);

    const item = state.pendingAids.find((a) => String(a.id) === String(id));
    if (!item) return;

    var numericId = String(item.aid_type === "medical_aid" || item.type === "Medical Aid Request" ? item.id : item.id).split("-").pop();
    if (isNaN(numericId)) numericId = String(item.id);

    const header = getEl("selectedAidHeader");
    if (header) header.innerText = `Inspecting Claim: ${item.id}`;

    if (window.renderAidInspectionFields) {
      window.renderAidInspectionFields(item, "aidEvidenceScreen");
    }

    const fieldsContainer = getEl("aidInspectionFields");
    if (fieldsContainer) fieldsContainer.style.display = "block";

    const auditId = getEl("aAuditID");
    // Format ID as "table-name-id" for backend compatibility
    const tableName = getAidTableName(item);
    const tablePrefix = tableName === "medical_aid" ? "medical" : "death";
    if (auditId) auditId.value = `${tablePrefix}-${item.entity_id}`;
    
    const auditType = getEl("aAuditType");
    if (auditType) auditType.value = tableName;
    
    const auditDate = getEl("aAuditDate");
    if (auditDate) auditDate.value = new Date().toLocaleString();

    const aidType = item.aid_type ||
      (item.type === "Medical Aid Request" ? "medical_aid" : "death_aid");

    if (window.fetchMediaForRecord) {
      window.fetchMediaForRecord(numericId, aidType, "aidEvidenceScreen").then((proof) => {
        if (proof && window.renderMediaPreview) {
          window.renderMediaPreview(proof.fileUrl, proof.fileType, proof.fileName, "aidEvidenceScreen");
        }
      });
    }

    if (window.toggleAidAuditEvidenceRequirement) {
      window.toggleAidAuditEvidenceRequirement();
    }
  }

  function clearMembershipFeeUI() {
    state.selectedMembershipFeeId = "";

    const header = getEl("selectedMembershipFeeHeader");
    if (header) header.innerText = "No fee submission selected";

    const resets = [
      "mfReadName",
      "mfReadEmpId",
      "mfReadDept",
      "mfReadPos",
      "mfReadContact",
      "mfReadEmail",
      "mfReadStatus",
      "mfReadRef",
      "mfReadAmount",
      "mfReadDate",
      "mfReadStatusDetail",
      "mfReadDeposit",
      "mfReadEncoder",
    ];
    resets.forEach((id) => {
      const el = getEl(id);
      if (el) el.innerText = "—";
    });

    const returnDetails = getEl("mfAuditReturnDetails");
    if (returnDetails) returnDetails.style.display = "none";

    const mfFieldContainer = getEl("mfAuditFieldCheckboxes");
    if (mfFieldContainer) mfFieldContainer.innerHTML = "";

    if (window.renderEmptyState) {
      window.renderEmptyState("membershipFeeEvidenceScreen");
    }

    const form = getEl("membershipFeeVerificationForm");
    if (form) form.reset();
    const auditId = getEl("mfAuditID");
    if (auditId) auditId.value = "";
    const preview = getEl("mf_findings_preview");
    if (preview) preview.style.display = "none";
  }

  function selectMembershipFee(id) {
    state.selectedMembershipFeeId = String(id);

    const item = state.pendingMembershipFees.find(
      (f) => String(f.fee_id) === String(id),
    );
    if (!item) return;

    const header = getEl("selectedMembershipFeeHeader");
    if (header) header.innerText = `Inspecting Fee: ${item.ref || item.fee_id}`;

    const m = item.member || {};
    if (getEl("mfReadName"))
      getEl("mfReadName").innerText = item.member_name || m.member_name || "—";
    if (getEl("mfReadEmpId"))
      getEl("mfReadEmpId").innerText = m.employee_id || "—";
    if (getEl("mfReadDept"))
      getEl("mfReadDept").innerText = m.department || "—";
    if (getEl("mfReadPos")) getEl("mfReadPos").innerText = m.position || "—";
    if (getEl("mfReadContact"))
      getEl("mfReadContact").innerText = m.contact || "—";
    if (getEl("mfReadEmail")) getEl("mfReadEmail").innerText = m.email || "—";
    if (getEl("mfReadStatus"))
      getEl("mfReadStatus").innerText = m.membership_status || "—";

    if (getEl("mfReadRef")) getEl("mfReadRef").innerText = item.ref || "—";
    if (getEl("mfReadAmount"))
      getEl("mfReadAmount").innerText = formatMoneyPHP(item.amount);
    if (getEl("mfReadDate"))
      getEl("mfReadDate").innerText = item.payment_date || "—";
    if (getEl("mfReadStatusDetail"))
      getEl("mfReadStatusDetail").innerText = item.payment_status || "—";
    if (getEl("mfReadDeposit"))
      getEl("mfReadDeposit").innerText = item.deposit_reference || "—";
    if (getEl("mfReadEncoder"))
      getEl("mfReadEncoder").innerText = item.encoded_by || "—";

    const auditId = getEl("mfAuditID");
    if (auditId) auditId.value = item.fee_id || item.entity_id;
    const auditDate = getEl("mfAuditDate");
    if (auditDate) auditDate.value = new Date().toLocaleString();

    if (window.fetchMediaForRecord) {
      window
        .fetchMediaForRecord(
          item.fee_id,
          "membership_fee",
          "membershipFeeEvidenceScreen",
        )
        .then((proof) => {
          if (proof) {
            window.renderMediaPreview(
              proof.fileUrl,
              proof.fileType,
              proof.fileName,
              "membershipFeeEvidenceScreen",
            );
          }
        });
    }
  }

  function closeMembershipFeeAudit() {
    clearMembershipFeeUI();
  }

  async function refreshAll() {
    state.pendingPayments = [];
    state.pendingAids = [];
    state.pendingMembershipFees = [];

    try {
      const payments = await getJSON("/api/auditor/pending-payments/list/");
      state.pendingPayments = payments.payments || [];
    } catch (e) {
      showToast(e.message || "Failed loading pending payments.", true);
    }

    try {
      const aids = await getJSON("/api/auditor/pending-aids/list/");
      state.pendingAids = aids.aids || [];
    } catch (e) {
      showToast(e.message || "Failed loading pending aids.", true);
    }

    try {
      const fees = await getJSON("/api/auditor/pending-membership-fees/list/");
      state.pendingMembershipFees = fees.fees || [];
    } catch (e) {
      showToast(e.message || "Failed loading pending membership fees.", true);
    }

    renderPaymentsTable();
    renderAidsTable();
    renderMembershipFeesTable();
    loadAuditedLogs();
    loadReportTable();

    if (typeof fetchAuditorRegistrationRequests === "function") {
      try { fetchAuditorRegistrationRequests(); } catch (e) {}
    }

    const totalPending = state.pendingPayments.length + state.pendingAids.length;
    const dot = getEl("audit-folder-dot");
    if (dot) {
      dot.textContent = totalPending;
      dot.classList.toggle("show", totalPending > 0);
      dot.setAttribute("data-zero", totalPending > 0 ? "0" : "1");
    }

    const pDot = getEl("payments-audit-dot");
    if (pDot) {
      pDot.textContent = state.pendingPayments.length;
      pDot.classList.toggle("show", state.pendingPayments.length > 0);
      pDot.setAttribute("data-zero", state.pendingPayments.length > 0 ? "0" : "1");
    }

    const aDot = getEl("aid-audit-dot");
    if (aDot) {
      aDot.textContent = state.pendingAids.length;
      aDot.classList.toggle("show", state.pendingAids.length > 0);
      aDot.setAttribute("data-zero", state.pendingAids.length > 0 ? "0" : "1");
    }

    const mfDot = getEl("auditor-membership-fees-dot");
    if (mfDot) {
      mfDot.textContent = state.pendingMembershipFees.length;
      mfDot.classList.toggle("show", state.pendingMembershipFees.length > 0);
      mfDot.setAttribute("data-zero", state.pendingMembershipFees.length > 0 ? "0" : "1");
    }

    // Update audit-folder-dot to include membership fees
    const folderDot = getEl("audit-folder-dot");
    if (folderDot) {
      var grandTotal = state.pendingPayments.length + state.pendingAids.length + state.pendingMembershipFees.length;
      folderDot.textContent = grandTotal;
      folderDot.classList.toggle("show", grandTotal > 0);
      folderDot.setAttribute("data-zero", grandTotal > 0 ? "0" : "1");
    }
  }

  // Export refreshAll to window so inline onclick handlers and other scripts can call it.
  try { window.refreshAll = refreshAll; } catch (e) {}

  // Lightweight helper: only reload the pending payments list so a just-verified
  // payment disappears from the "Payments Audit" card immediately, without waiting
  // on the heavier refreshAll() that also reloads aids, fees, logs and reports.
  async function refreshPaymentsOnly() {
    try {
      const payments = await getJSON("/api/auditor/pending-payments/list/");
      if (!payments || !payments.ok) return;
      state.pendingPayments = payments.payments || [];
    } catch (e) {
      return;
    }
    renderPaymentsTable();
    const pDot = getEl("payments-audit-dot");
    if (pDot) {
      pDot.textContent = state.pendingPayments.length;
      pDot.classList.toggle("show", state.pendingPayments.length > 0);
      pDot.setAttribute("data-zero", state.pendingPayments.length > 0 ? "0" : "1");
    }
    const folderDot = getEl("audit-folder-dot");
    if (folderDot) {
      const total =
        state.pendingPayments.length +
        (state.pendingAids || []).length +
        (state.pendingMembershipFees || []).length;
      folderDot.textContent = total;
      folderDot.classList.toggle("show", total > 0);
      folderDot.setAttribute("data-zero", total > 0 ? "0" : "1");
    }
  }

  /* === AUDITED LOGS === */
  state.auditedLogs = [];

  async function loadAuditedLogs() {
    try {
      const data = await getJSON("/api/auditor/audited-logs/");
      state.auditedLogs = data.logs || [];
    } catch (e) {
      state.auditedLogs = [];
    }
    applyAuditLogFilters();
  }

  function applyAuditLogFilters() {
    const searchVal = (getEl("auditLogSearch")?.value || "").toLowerCase().trim();
    const resultVal = (getEl("auditLogResultFilter")?.value || "").trim();
    const dateFrom = getEl("auditLogDateFrom")?.value || "";
    const dateTo = getEl("auditLogDateTo")?.value || "";

    var filtered = state.auditedLogs.filter(function (log) {
      if (searchVal && !log.member_name.toLowerCase().includes(searchVal)) return false;
      if (resultVal && (log.result || "").toLowerCase().indexOf(resultVal.toLowerCase()) === -1) return false;
      if (dateFrom && log.verified_at && log.verified_at.slice(0, 10) < dateFrom) return false;
      if (dateTo && log.verified_at && log.verified_at.slice(0, 10) > dateTo) return false;
      return true;
    });

    state.filteredAuditedLogs = filtered;
    state.auditLogPage = 1;

    renderAuditedLogs(filtered);
  }

  function renderAuditedLogs(logs) {
    var tbody = document.querySelector("#auditedLogsTable tbody");
    if (!tbody) return;

    var pageSize = 20;
    var totalPages = Math.max(1, Math.ceil(logs.length / pageSize));
    if (state.auditLogPage > totalPages) state.auditLogPage = totalPages;
    if (state.auditLogPage < 1) state.auditLogPage = 1;

    renderAuditLogPagination(logs, pageSize, totalPages);

    if (!logs || logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#757575;padding:24px;">No audited log entries found.</td></tr>';
      return;
    }

    var start = (state.auditLogPage - 1) * pageSize;
    var pageLogs = logs.slice(start, start + pageSize);

    var html = "";
    for (var i = 0; i < pageLogs.length; i++) {
      var log = pageLogs[i];
      var dateLabel = log.verified_at ? new Date(log.verified_at).toLocaleString() : "—";
      var amountLabel = log.amount ? formatMoneyPHP(log.amount) : "—";
      var resultBadge = (function (s) {
        var lower = (s || "").toLowerCase();
        if (lower.indexOf("verified") !== -1 || lower.indexOf("approved") !== -1 || lower.indexOf("released") !== -1)
          return '<span style="background:rgba(27,94,32,0.1);color:#1b5e20;padding:4px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">' + escapeHtml(s) + '</span>';
        if (lower.indexOf("returned") !== -1 || lower.indexOf("rejected") !== -1)
          return '<span style="background:rgba(229,57,53,0.1);color:#e53935;padding:4px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">' + escapeHtml(s) + '</span>';
        return '<span style="background:rgba(158,158,158,0.1);color:#757575;padding:4px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">' + escapeHtml(s) + '</span>';
      })(log.result);
      var evidenceIcon = log.has_evidence
        ? '<span style="color:#1b5e20;font-size:1.1rem;cursor:pointer;" title="Evidence on file">&#128206;</span>'
        : '<span style="color:#bdbdbd;font-size:0.78rem;">None</span>';

      html += "<tr>";
      html += "<td style='white-space:nowrap;font-size:0.78rem;'>" + escapeHtml(dateLabel) + "</td>";
      html += "<td>" + escapeHtml(log.transaction_type || "") + "</td>";
      html += "<td><strong>" + escapeHtml(log.member_name || "") + "</strong></td>";
      html += "<td style='font-weight:600;'>" + amountLabel + "</td>";
      html += "<td>" + resultBadge + "</td>";
      html += "<td style='max-width:220px;font-size:0.78rem;'>" + escapeHtml(log.remarks || "") + "</td>";
      html += "<td style='font-size:0.78rem;line-height:1.6;'>";
      html += "<div><span style='color:#1b5e20;font-weight:600;'>&#10003;</span> " + escapeHtml(log.auditor_name || "") + "</div>";
      html += "<div><span style='color:#1565c0;font-weight:600;'>&#10003;</span> " + escapeHtml(log.president_name || "\u2014") + "</div>";
      html += "</td>";
      html += "<td style='text-align:center;'>" + evidenceIcon + "</td>";
      html += "</tr>";
    }
    tbody.innerHTML = html;
  }

  function auditLogGoToPage(page) {
    state.auditLogPage = page;
    renderAuditedLogs(state.filteredAuditedLogs || []);
  }

  function renderAuditLogPagination(logs, pageSize, totalPages) {
    var pag = getEl("auditLogPagination");
    var countEl = getEl("auditLogCount");
    if (!pag) return;

    var total = logs.length;
    if (countEl) {
      countEl.textContent = total === 0
        ? "No entries"
        : "Showing " + ((state.auditLogPage - 1) * pageSize + 1) + "\u2013" + Math.min(state.auditLogPage * pageSize, total) + " of " + total;
    }

    if (totalPages <= 1) {
      pag.innerHTML = "";
      return;
    }

    pag.innerHTML = "";
    var makeBtn = function (label, target, active, disabled) {
      var b = document.createElement("button");
      b.className = "btn-brand " + (active ? "btn-brand-primary" : "btn-brand-secondary");
      b.style.cssText = "padding:4px 10px;font-size:0.78rem;";
      b.textContent = label;
      b.disabled = !!disabled;
      b.type = "button";
      b.onclick = function () { auditLogGoToPage(target); };
      return b;
    };
    var ell = function () {
      var s = document.createElement("span");
      s.style.cssText = "color:#5f6b5f;padding:0 2px;font-size:0.8rem;";
      s.textContent = "\u2026";
      return s;
    };

    pag.appendChild(makeBtn("\u2039 Prev", state.auditLogPage - 1, false, state.auditLogPage <= 1));

    var maxBtns = 7;
    var from = Math.max(1, state.auditLogPage - Math.floor(maxBtns / 2));
    var to = Math.min(totalPages, from + maxBtns - 1);
    from = Math.max(1, to - maxBtns + 1);

    if (from > 1) {
      pag.appendChild(makeBtn("1", 1, false, false));
      if (from > 2) pag.appendChild(ell());
    }
    for (var p = from; p <= to; p++) {
      pag.appendChild(makeBtn(String(p), p, p === state.auditLogPage, false));
    }
    if (to < totalPages) {
      if (to < totalPages - 1) pag.appendChild(ell());
      pag.appendChild(makeBtn(String(totalPages), totalPages, false, false));
    }

    pag.appendChild(makeBtn("Next \u203a", state.auditLogPage + 1, false, state.auditLogPage >= totalPages));
  }

  async function handlePaymentSubmit(e) {
    e.preventDefault();

    const auditTargetId = (getEl("pAuditID") || {}).value;
    if (!auditTargetId) {
      console.error("submitPaymentVerification: missing pAuditID");
      showToast(
        "Please select an active transaction log from the inbox first.",
        true,
      );
      return;
    }

    const result = (getEl("pAuditResult") || {}).value || "";
    if (!result || !["Verified", "Returned"].includes(result)) {
      console.error("submitPaymentVerification: invalid pAuditResult", result);
      showToast(
        "Please select a valid verification result.",
        true,
      );
      return;
    }

    let fieldRemarks = "";
    if (result === "Returned") {
      const json = buildRejectionDetailsJSON("pAuditFieldCheckboxes");
      if (json) fieldRemarks = json;
    }

    const fd = new FormData();
    fd.append("pAuditID", auditTargetId);
    fd.append("pAuditRemarks", (getEl("pAuditRemarks") || {}).value || "");
    fd.append("pAuditResult", result);
    fd.append("pAuditFieldRemarks", fieldRemarks);

    const fileInput = getEl("p_findings_file");
    if (fileInput && fileInput.files && fileInput.files[0]) {
      fd.append("p_findings_file", fileInput.files[0]);
    }

    if (window.ensureZeroTrust) {
      const ztOk = await window.ensureZeroTrust();
      if (!ztOk) {
        showToast("Zero Trust verification is required to approve payments.", true);
        return;
      }
    }

    // Immediate feedback while the server processes the verification request.
    showToast("Submitting verification...", false);

    try {
      const data = await postForm("/api/auditor/verify-payment/", fd);
      if (data && data.ok === false) {
        if (data.error && data.error.includes("already been acted upon")) {
          showToast("This record has already been verified. Refreshing the list...", true);
        } else {
          showToast(data.error || "Failed submitting payment audit.", true);
        }
        if (typeof refreshPaymentsOnly === "function") refreshPaymentsOnly();
        return;
      }
      showToast("Payment audit submitted to system log.", false);
      clearPaymentUI();
      // Remove the verified/returned item right away via a lightweight payments
      // refresh, then let the full dashboard sync run in the background.
      if (typeof refreshPaymentsOnly === "function") {
        await refreshPaymentsOnly();
      } else {
        renderPaymentsTable();
      }
      refreshAll();
    } catch (err) {
      if (err.message && err.message.includes("already been acted upon")) {
        showToast("This record has already been verified. Refreshing the list...", true);
        await refreshAll();
        clearPaymentUI();
      } else {
        showToast(err.message || "Failed submitting payment audit.", true);
      }
    }
  }

  async function handleAidSubmit(e) {
    e.preventDefault();

    const auditTargetId = (getEl("aAuditID") || {}).value;
    if (!auditTargetId) {
      showToast(
        "Please select an active claim record from the inbox first.",
        true,
      );
      return;
    }

    const auditResult = (getEl("aAuditResult") || {}).value || "";
    if (!auditResult) {
      showToast("Please select a verification result (Verified or Returned).", true);
      return;
    }

    // Get table name for consistency with bulk verification
    const tableName = (getEl("aAuditType") || {}).value || "";

    const fd = new FormData();
    fd.append("aAuditID", auditTargetId);
    fd.append("aAuditRemarks", (getEl("aAuditRemarks") || {}).value || "");
    fd.append("aAuditResult", auditResult);
    
    // Add table_name for consistency with bulk verification
    if (tableName) {
      fd.append("table_name", tableName);
    }

    const fileInput = getEl("a_findings_file");
    if (fileInput && fileInput.files && fileInput.files[0]) {
      fd.append("a_findings_file", fileInput.files[0]);
    }

    console.log("Submitting aid verification:", {
      auditTargetId,
      auditResult,
      tableName,
      formDataEntries: Array.from(fd.entries())
    });

    try {
      const data = await postForm("/api/auditor/verify-aid/", fd);
      console.log("Verification response:", data);
      
      if (data && data.ok) {
        showToast("Aid audit submitted to system log.", false);
        clearAidUI();
        await refreshAll();
      } else {
        if (data.error && data.error.includes("already been acted upon")) {
          showToast("This record has already been verified. Refreshing the list...", true);
          await refreshAll();
          clearAidUI();
        } else {
          showToast(data.error || "Failed submitting aid audit.", true);
        }
      }
    } catch (err) {
      console.error("Verification error:", err);
      showToast(err.message || "Failed submitting aid audit.", true);
    }
  }

  async function handleMembershipFeeSubmit(e) {
    e.preventDefault();

    const auditTargetId = (getEl("mfAuditID") || {}).value;
    if (!auditTargetId) {
      showToast(
        "Please select a membership fee record from the inbox first.",
        true,
      );
      return;
    }

    const result = (getEl("mfAuditResult") || {}).value || "";
    let fieldRemarks = "";
    if (result === "Returned") {
      const json = buildRejectionDetailsJSON("mfAuditFieldCheckboxes");
      if (json) fieldRemarks = json;
    }

    const fd = new FormData();
    fd.append("mfAuditID", auditTargetId);
    fd.append("mfAuditRemarks", (getEl("mfAuditRemarks") || {}).value || "");
    fd.append("mfAuditResult", result);
    fd.append("mfAuditFieldRemarks", fieldRemarks);

    const fileInput = getEl("mf_findings_file");
    if (fileInput && fileInput.files && fileInput.files[0]) {
      fd.append("p_findings_file", fileInput.files[0]);
    }

    try {
      await postForm("/api/auditor/verify-membership-fee/", fd);
      showToast("Membership fee audit submitted to system log.", false);
      clearMembershipFeeUI();
      await refreshAll();
    } catch (err) {
      if (err.message && err.message.includes("already been acted upon")) {
        showToast("This record has already been verified. Refreshing the list...", true);
        await refreshAll();
        clearMembershipFeeUI();
      } else {
        showToast(err.message || "Failed submitting membership fee audit.", true);
      }
    }
  }

  function bindForms() {
    window.submitPaymentVerification = handlePaymentSubmit;
    window.submitAidVerification = handleAidSubmit;
    window.submitMembershipFeeVerification = handleMembershipFeeSubmit;

    const paymentForm = getEl("paymentVerificationForm");
    if (paymentForm) {
      // Avoid double-binding: setting both `onsubmit` and `addEventListener('submit')`
      // causes duplicate POSTs (and duplicate backend artifacts) on a single click.
      paymentForm.onsubmit = handlePaymentSubmit;
    }

    const aidForm = getEl("aidVerificationForm");
    if (aidForm) {
      // Avoid double-binding: setting both `onsubmit` and `addEventListener('submit')`
      // causes duplicate POSTs (and duplicate backend artifacts) on a single click.
      aidForm.onsubmit = handleAidSubmit;
    }

    const membershipFeeForm = getEl("membershipFeeVerificationForm");
    if (membershipFeeForm) {
      // Avoid double-binding: setting both `onsubmit` and `addEventListener('submit')`
      // causes duplicate POSTs (and duplicate backend artifacts) on a single click.
      membershipFeeForm.onsubmit = handleMembershipFeeSubmit;
    }

    const membershipFeeAuditForm = getEl("membershipFeeAuditForm");
    if (membershipFeeAuditForm) {
      membershipFeeAuditForm.onsubmit = handleMembershipFeeSubmit;
      membershipFeeAuditForm.addEventListener(
        "submit",
        handleMembershipFeeSubmit,
      );
    }
  }

  function bindCancelButtons() {
    window.clearPaymentVerificationSelection = clearPaymentUI;
    window.clearAidVerificationSelection = clearAidUI;
    window.clearMembershipFeeVerificationSelection = clearMembershipFeeUI;
  }

  function bindReturnForCorrectionButtons() {
    const paymentBtn = getEl("btnReturnPaymentForCorrection");
    if (paymentBtn) {
      paymentBtn.addEventListener("click", () => {
        if (paymentBtn.dataset.submitting === "1") return;
        paymentBtn.dataset.submitting = "1";
        paymentBtn.disabled = true;

        const resultSelect = getEl("pAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        togglePaymentAuditEvidenceRequirement();
        const form = getEl("paymentVerificationForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }

    const aidBtn = getEl("btnReturnAidForCorrection");
    if (aidBtn) {
      aidBtn.addEventListener("click", () => {
        if (aidBtn.dataset.submitting === "1") return;
        aidBtn.dataset.submitting = "1";
        aidBtn.disabled = true;

        const resultSelect = getEl("aAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        toggleAidAuditEvidenceRequirement();
        const form = getEl("aidVerificationForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }

    const mfBtn = getEl("btnReturnMembershipFeeForCorrection");
    if (mfBtn) {
      mfBtn.addEventListener("click", () => {
        if (mfBtn.dataset.submitting === "1") return;
        mfBtn.dataset.submitting = "1";
        mfBtn.disabled = true;

        const resultSelect = getEl("mfAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        toggleMembershipFeeAuditEvidenceRequirement();
        const form = getEl("membershipFeeVerificationForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }

    const mfAuditBtn = getEl("btnReturnMembershipFeeAuditForCorrection");
    if (mfAuditBtn) {
      mfAuditBtn.addEventListener("click", () => {
        if (mfAuditBtn.dataset.submitting === "1") return;
        mfAuditBtn.dataset.submitting = "1";
        mfAuditBtn.disabled = true;

        const resultSelect = getEl("mfAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        const form = getEl("membershipFeeAuditForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }
  }

  function setupCollapsibleSidebar() {
    const sidebar = getEl("appSidebar");
    const headerToggle = getEl("headerSidebarToggle");
    const headerToggleIcon = getEl("headerSidebarToggleIcon");

    // Restore persisted collapsed state (mockup behavior)
    try {
      if (localStorage.getItem("sidebar_collapsed") === "1") {
        sidebar.classList.add("collapsed");
        if (headerToggleIcon) {
          headerToggleIcon.classList.remove("fa-bars");
          headerToggleIcon.classList.add("fa-chevron-left");
        }
        if (headerToggle) headerToggle.setAttribute("title", "Expand Sidebar");
      }
    } catch (e) {}

    if (headerToggle) {
      headerToggle.addEventListener("click", () => {
        const isMobile = window.matchMedia("(max-width: 1200px)").matches;
        if (isMobile) {
          sidebar.classList.toggle("open-mobile");
        } else {
          sidebar.classList.toggle("collapsed");
        }
        const collapsed = sidebar.classList.contains("collapsed");
        const isOpen = sidebar.classList.contains("open-mobile");
        try { localStorage.setItem("sidebar_collapsed", collapsed ? "1" : "0"); } catch (e) {}
        if (headerToggleIcon) {
          if (isMobile) {
            if (isOpen) {
              headerToggleIcon.classList.remove("fa-bars");
              headerToggleIcon.classList.add("fa-chevron-left");
            } else {
              headerToggleIcon.classList.remove("fa-chevron-left");
              headerToggleIcon.classList.add("fa-bars");
            }
          } else {
            if (collapsed) {
              headerToggleIcon.classList.remove("fa-bars");
              headerToggleIcon.classList.add("fa-chevron-left");
            } else {
              headerToggleIcon.classList.remove("fa-chevron-left");
              headerToggleIcon.classList.add("fa-bars");
            }
          }
        }
        headerToggle.setAttribute("title", collapsed || isOpen ? "Close Sidebar" : "Open Sidebar");
      });
    }

    // Mockup behavior: clicking a group title collapses/expands its section
    document.querySelectorAll(".sidebar .nav-group-title").forEach((title) => {
      title.style.cursor = "pointer";
      title.style.userSelect = "none";
      title.setAttribute("title", "Toggle section");
      title.addEventListener("click", () => {
        const hidden = title.classList.toggle("collapsed");
        let el = title.nextElementSibling;
        while (el && !el.classList.contains("nav-group-title")) {
          if (el.classList.contains("menu-item") || el.classList.contains("nested-folder")) {
            el.style.display = hidden ? "none" : "";
          }
          el = el.nextElementSibling;
        }
        try { localStorage.setItem("sb_group_" + (title.textContent || "").trim().toLowerCase(), hidden ? "1" : "0"); } catch (e) {}
      });
      // Restore persisted section state
      try {
        var wasCollapsed = localStorage.getItem("sb_group_" + (title.textContent || "").trim().toLowerCase()) === "1";
        if (wasCollapsed) {
          title.classList.add("collapsed");
          let el2 = title.nextElementSibling;
          while (el2 && !el2.classList.contains("nav-group-title")) {
            if (el2.classList.contains("menu-item") || el2.classList.contains("nested-folder")) {
              el2.style.display = "none";
            }
            el2 = el2.nextElementSibling;
          }
        }
      } catch (e) {}
    });
  }

  function setupFolders() {
    const activeLink = document.querySelector(".menu-item.active");
    if (activeLink) {
      const parentFolder = activeLink.closest(".nested-folder");
      if (parentFolder) {
        const contents = parentFolder.querySelector(".folder-contents");
        const header = parentFolder.querySelector(".folder-header");
        if (contents) contents.classList.add("open");
        const chevron = header && header.querySelector(".chevron-icon");
        if (chevron) chevron.style.transform = "rotate(180deg)";
      }
    }
  }

  function toggleFolder(folderId, headerElement) {
    const sidebar = getEl("appSidebar");
    const hdrIcon = getEl("headerSidebarToggleIcon");
    if (sidebar && sidebar.classList.contains("collapsed")) {
      sidebar.classList.remove("collapsed");
      try { localStorage.setItem("sidebar_collapsed", "0"); } catch (e) {}
      if (hdrIcon) {
        hdrIcon.classList.remove("fa-chevron-left");
        hdrIcon.classList.add("fa-bars");
      }
    }
    // On mobile, ensure sidebar is visible when interacting with folders
    if (sidebar && !sidebar.classList.contains("open-mobile")) {
      const isMobile = window.matchMedia("(max-width: 1200px)").matches;
      if (isMobile) {
        sidebar.classList.add("open-mobile");
        if (hdrIcon) {
          hdrIcon.classList.remove("fa-bars");
          hdrIcon.classList.add("fa-chevron-left");
        }
      }
    }

    const contents = document.getElementById(folderId);
    if (!contents) return;
    const isOpen = contents.classList.contains("open");

    document.querySelectorAll(".folder-contents").forEach((el) => {
      el.classList.remove("open");
      const parentHeader =
        el.parentElement && el.parentElement.querySelector(".chevron-icon");
      if (parentHeader) parentHeader.style.transform = "rotate(0deg)";
    });

    if (!isOpen) {
      contents.classList.add("open");
      const chevron =
        headerElement && headerElement.querySelector(".chevron-icon");
      if (chevron) chevron.style.transform = "rotate(180deg)";
    }
  }

  function setActiveModule(targetId) {
    const menuItems = document.querySelectorAll(".menu-item");
    menuItems.forEach((mi) => {
      mi.classList.remove("active");
      if (mi.getAttribute("data-target") === targetId) {
        mi.classList.add("active");
      }
    });

    document.querySelectorAll(".dashboard-module").forEach((mod) => {
      mod.classList.remove("active");
      if (mod.id === targetId) {
        mod.classList.add("active");
      }
    });

    const sidebar = getEl("appSidebar");
    if (sidebar) sidebar.classList.remove("open-mobile");

    const activeItem = document.querySelector(
      `.menu-item[data-target="${targetId}"]`,
    );
    if (activeItem) {
      const titleEl = activeItem.querySelector(".menu-text");
      if (titleEl) {
        const currentModuleTitle = getEl("currentModuleTitle");
        if (currentModuleTitle)
          currentModuleTitle.innerText = titleEl.innerText;
      }
    }

    if (targetId === "compliance-heatmap") {
      [heatmapDonutChart, heatmapRateChart, heatmapStackedChart].forEach((chart) => {
        if (chart) chart.resize();
      });
    }

    // Fire module init hooks (mockup parity data loaders). Dispatching here
    // guarantees hooks run on EVERY navigation path — sidebar clicks call this
    // closure directly, bypassing any window.setActiveModule wrapper.
    try {
      if (window.nxModuleInit) window.nxModuleInit(targetId);
    } catch (e) {}
  }

  function setupNavigation() {
    const menuItems = document.querySelectorAll(".menu-item");
    menuItems.forEach((item) => {
      item.addEventListener("click", () => {
        const target = item.getAttribute("data-target");
        if (!target) return;

        setActiveModule(target);

        localStorage.setItem("auditor_active_tab", target);

        const sidebar = getEl("appSidebar");
        if (sidebar) sidebar.classList.remove("open-mobile");

        const titleEl = item.querySelector(".menu-text");
        if (titleEl) {
          const currentModuleTitle = getEl("currentModuleTitle");
          if (currentModuleTitle)
            currentModuleTitle.innerText = titleEl.innerText;
        }

        var parentContents = item.closest(".folder-contents");
        if (parentContents && !parentContents.classList.contains("open")) {
          var folderHeader = parentContents.parentElement && parentContents.parentElement.querySelector(".folder-header");
          if (folderHeader) toggleFolder(parentContents.id, folderHeader);
        }
      });
    });

    const mobileToggle = getEl("mobileSidebarToggle");
    if (mobileToggle) {
      mobileToggle.addEventListener("click", () => {
        const sidebar = getEl("appSidebar");
        if (sidebar) sidebar.classList.add("open-mobile");
      });
    }
  }

  async function init() {
    window.triggerFileUpload =
      window.triggerFileUpload ||
      function (id) {
        const el = getEl(id);
        if (el) el.click();
      };

    window.showAttachedPreview =
      window.showAttachedPreview ||
      function (input, labelId) {
        if (input.files && input.files.length > 0) {
          const el = getEl(labelId);
          if (el) el.style.display = "block";
        }
      };

    window.togglePaymentAuditEvidenceRequirement =
      window.togglePaymentAuditEvidenceRequirement ||
      function () {
        const select = getEl("pAuditResult");
        const evidenceGroup = getEl("evidenceGroup");
        const badge = getEl("p_findings_req_badge");
        const fileInput = getEl("p_findings_file");
        const btnReturn = getEl("btnReturnPaymentForCorrection");
        const btnVerify = getEl("btnSubmitPaymentVerification");

        if (!select || !badge || !fileInput) return;

        if (select.value === "Returned") {
          badge.innerText = "Required finding evidence";
          badge.style.background = "rgba(229,57,53,0.1)";
          badge.style.color = "#e53935";
          fileInput.setAttribute("required", "");
          if (evidenceGroup) evidenceGroup.style.display = "block";
          if (btnReturn) btnReturn.style.display = "inline-flex";
          if (btnVerify) btnVerify.style.display = "none";
          const returnDetails = getEl("pAuditReturnDetails");
          if (returnDetails) returnDetails.style.display = "block";
        } else {
          badge.innerText = "Required documentation";
          badge.style.background = "rgba(27,94,32,0.1)";
          badge.style.color = "#1b5e20";
          fileInput.removeAttribute("required");
          if (evidenceGroup) {
            evidenceGroup.style.display = "none";
            fileInput.value = "";
            const previewIndicator = getEl("p_findings_preview");
            if (previewIndicator) previewIndicator.style.display = "none";
          }
          if (btnReturn) btnReturn.style.display = "none";
          if (btnVerify) btnVerify.style.display = "inline-flex";
          const returnDetails = getEl("pAuditReturnDetails");
          if (returnDetails) returnDetails.style.display = "none";
        }
      };

    window.toggleAidAuditEvidenceRequirement =
      window.toggleAidAuditEvidenceRequirement ||
      function () {
        const select = getEl("aAuditResult");
        const evidenceGroup = getEl("aEvidenceGroup");
        const badge = getEl("a_findings_req_badge");
        const fileInput = getEl("a_findings_file");
        const btnReturn = getEl("btnReturnAidForCorrection");
        const btnSubmit = getEl("btnSubmitAidVerification");

        if (!select || !badge || !fileInput) return;

        if (select.value === "Returned") {
          badge.innerText = "Required finding evidence";
          badge.style.background = "rgba(229,57,53,0.1)";
          badge.style.color = "#e53935";
          fileInput.setAttribute("required", "");
          if (evidenceGroup) evidenceGroup.style.display = "block";
          if (btnReturn) btnReturn.style.display = "inline-flex";
          if (btnSubmit) btnSubmit.style.display = "none";
        } else {
          badge.innerText = "Required documentation";
          badge.style.background = "rgba(27,94,32,0.1)";
          badge.style.color = "#1b5e20";
          fileInput.removeAttribute("required");
          if (evidenceGroup) {
            evidenceGroup.style.display = "none";
            fileInput.value = "";
            const previewIndicator = getEl("a_findings_preview");
            if (previewIndicator) previewIndicator.style.display = "none";
          }
          if (btnReturn) btnReturn.style.display = "none";
          if (btnSubmit) btnSubmit.style.display = "inline-flex";
        }
      };

    window.toggleMembershipFeeAuditEvidenceRequirement =
      window.toggleMembershipFeeAuditEvidenceRequirement ||
      function () {
        const select = getEl("mfAuditResult");
        const evidenceGroup = getEl("mfEvidenceGroup");
        const badge = getEl("mf_findings_req_badge");
        const fileInput = getEl("mf_findings_file");
        const btnReturn = getEl("btnReturnMembershipFeeForCorrection");
        const btnSubmit = getEl("btnSubmitMembershipFeeVerification");

        if (!select || !badge || !fileInput) return;

        if (select.value === "Returned") {
          badge.innerText = "Required finding evidence";
          badge.style.background = "rgba(229,57,53,0.1)";
          badge.style.color = "#e53935";
          fileInput.setAttribute("required", "");
          if (evidenceGroup) evidenceGroup.style.display = "block";
          if (btnReturn) btnReturn.style.display = "inline-flex";
          if (btnSubmit) btnSubmit.style.display = "none";
          const returnDetails = getEl("mfAuditReturnDetails");
          if (returnDetails) returnDetails.style.display = "block";
        } else {
          badge.innerText = "Required documentation";
          badge.style.background = "rgba(27,94,32,0.1)";
          badge.style.color = "#1b5e20";
          fileInput.removeAttribute("required");
          if (evidenceGroup) {
            evidenceGroup.style.display = "none";
            fileInput.value = "";
            const previewIndicator = getEl("mf_findings_preview");
            if (previewIndicator) previewIndicator.style.display = "none";
          }
          if (btnReturn) btnReturn.style.display = "none";
          if (btnSubmit) btnSubmit.style.display = "inline-flex";
          const returnDetails = getEl("mfAuditReturnDetails");
          if (returnDetails) returnDetails.style.display = "none";
        }
      };

    bindForms();
    bindCancelButtons();
    bindReturnForCorrectionButtons();
    setupNavigation();
    setupFolders();
    setupCollapsibleSidebar();

    // Restore last selected tab (persists across refresh, cleared on logout).
    const savedTab = localStorage.getItem("auditor_active_tab");
    if (savedTab) {
      setActiveModule(savedTab);
      var savedItem = document.querySelector('.menu-item[data-target="' + savedTab + '"]');
      if (savedItem) {
        var parentContents = savedItem.closest(".folder-contents");
        if (parentContents && !parentContents.classList.contains("open")) {
          var folderHeader = parentContents.parentElement && parentContents.parentElement.querySelector(".folder-header");
          if (folderHeader) toggleFolder(parentContents.id, folderHeader);
        }
      }
    }

    clearPaymentUI();
    clearAidUI();
    clearMembershipFeeUI();

    togglePaymentAuditEvidenceRequirement();
    toggleAidAuditEvidenceRequirement();
    toggleMembershipFeeAuditEvidenceRequirement();

    // Auto-refresh dashboard data every 30 seconds
    setInterval(() => {
      if (typeof refreshAll === 'function') {
        refreshAll();
      }
    }, 30000);

    const paySelectAll = document.getElementById("pay-select-all");
    if (paySelectAll) {
      paySelectAll.addEventListener("change", function () {
        const checked = this.checked;
        document.querySelectorAll("#pendingPaymentsTable .pay-row-check").forEach(cb => {
          cb.checked = checked;
          const pid = cb.value;
          if (checked) state.selectedPaymentIds.add(pid);
          else state.selectedPaymentIds.delete(pid);
          const row = cb.closest("tr");
          if (row) row.classList.toggle("selected-row", checked);
        });
        updatePayBatchBar();
      });
    }
    document.getElementById("pay-batch-verify")?.addEventListener("click", function () {
      submitPayBatchVerify("Verified");
    });
    document.getElementById("pay-batch-return")?.addEventListener("click", function () {
      submitPayBatchVerify("Returned");
    });
    document.getElementById("pay-batch-clear")?.addEventListener("click", function () {
      clearPaySelection();
    });

    // Set default month and year for heatmap and auto-load on filter change
    const now = new Date();
    const heatmapMonth = document.getElementById("heatmap-month");
    const heatmapYear = document.getElementById("heatmap-year");
    if (heatmapMonth && !heatmapMonth.value) heatmapMonth.value = String(now.getMonth() + 1).padStart(2, '0');
    
    // Dynamically populate year dropdown based on actual payment years
    await populateHeatmapYears();
    
    // Set year to current year after population, defaulting to most recent year
    if (heatmapYear) {
      const currentYear = now.getFullYear();
      const availableYears = Array.from(heatmapYear.options).map(opt => parseInt(opt.value));
      if (availableYears.includes(currentYear)) {
        heatmapYear.value = currentYear;
      } else if (availableYears.length > 0) {
        heatmapYear.value = availableYears[availableYears.length - 1]; // Most recent year
      }
    }
    
    ["heatmap-month", "heatmap-year", "heatmap-payment-type", "heatmap-payment-status"].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", loadComplianceHeatmap);
    });
    window.loadComplianceHeatmap = loadComplianceHeatmap;
    loadComplianceHeatmap();

  // ==========================================================================
  // COMPLIANCE HEAT MAP FUNCTIONS
  // ==========================================================================

  async function populateHeatmapYears() {
    const sel = document.getElementById("heatmap-year");
    if (!sel) return;
    let years = [];
    try {
      const response = await fetch("/api/auditor/payment-years/", {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const result = await response.json();
      if (result.ok && Array.isArray(result.years) && result.years.length) {
        years = result.years;
      }
    } catch (error) {
      console.error("Failed to load payment years:", error);
    }
    // Fallback: never leave the dropdown stuck on "Loading..."
    if (!years.length) {
      const y = new Date().getFullYear();
      years = [y - 2, y - 1, y, y + 1];
    }
    const previous = sel.value;
    sel.innerHTML = "";
    years.forEach(year => {
      const option = document.createElement("option");
      option.value = year;
      option.textContent = year;
      sel.appendChild(option);
    });
    const currentYear = new Date().getFullYear();
    if (years.includes(currentYear)) {
      sel.value = currentYear;
    } else if (previous && years.includes(parseInt(previous))) {
      sel.value = previous;
    } else {
      sel.value = years[years.length - 1];
    }
  }

  const heatmapColorMap = {
    green: "#28a745",
    yellow: "#ffc107",
    orange: "#fd7e14",
    red: "#dc3545",
  };

  function destroyHeatmapCharts() {
    [heatmapDonutChart, heatmapRateChart, heatmapStackedChart].forEach((chart) => {
      if (chart) {
        chart.destroy();
      }
    });
    heatmapDonutChart = null;
    heatmapRateChart = null;
    heatmapStackedChart = null;
  }

  async function loadComplianceHeatmap() {
    const month = document.getElementById("heatmap-month").value;
    const year = document.getElementById("heatmap-year").value;
    const paymentType = document.getElementById("heatmap-payment-type").value;
    const paymentStatus = document.getElementById("heatmap-payment-status").value;

    const btn = document.querySelector("#compliance-heatmap .hm-load-btn");
    if (btn) btn.disabled = true;

    const grid = document.getElementById("heatmap-grid");
    grid.innerHTML = '<div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #888;"><i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i><p>Building heat map...</p></div>';

    try {
      const params = new URLSearchParams({
        month: month,
        year: year,
        payment_type: paymentType,
        payment_status: paymentStatus,
      });

      const response = await fetch(`/api/auditor/compliance-heatmap/?${params}`, {
        method: "GET",
        headers: {
          "X-CSRFToken": getCSRFToken(),
        },
      });

      const data = await response.json();

      if (!data.ok) {
        grid.innerHTML = `<div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>${data.error || "Failed to load compliance data"}</p></div>`;
        return;
      }

      // Update analytics cards
      document.getElementById("heatmap-total-departments").textContent = data.analytics.total_departments;
      document.getElementById("heatmap-fully-compliant").textContent = data.analytics.fully_compliant;
      document.getElementById("heatmap-needs-followup").textContent = data.analytics.needs_followup;
      document.getElementById("heatmap-total-paid").textContent = data.analytics.total_paid_members;
      document.getElementById("heatmap-total-advance").textContent = data.analytics.total_advance_members;
      document.getElementById("heatmap-total-pending").textContent = data.analytics.total_pending_payments;
      document.getElementById("heatmap-total-unpaid").textContent = data.analytics.total_unpaid_members;
      document.getElementById("heatmap-overall-compliance").textContent = data.analytics.overall_compliance_rate + "%";
      document.getElementById("heatmap-total-collections").textContent = formatMoneyPHP(data.analytics.total_monthly_collections);

      const hasChartJs = typeof Chart !== "undefined";
      const departments = data.departments || [];

      // Build charts
      if (hasChartJs) {
        destroyHeatmapCharts();
        buildHeatmapCharts(departments, data.analytics);
      }

      // Render department cards
      if (departments.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #888;"><i class="fas fa-info-circle" style="font-size: 32px; margin-bottom: 12px;"></i><p>No department data available for the selected filters</p></div>';
        return;
      }

      const sorted = [...departments].sort((a, b) => b.compliance_rate - a.compliance_rate);

      grid.innerHTML = sorted.map(dept => {
        const bgColor = heatmapColorMap[dept.color] || "#6c757d";
        const rate = dept.compliance_rate;

        return `
          <div class="heat-cell" onclick="openDepartmentDetail('${escapeHtml(dept.department)}', '${data.month}')">
            <div class="heat-cell-top" style="background: linear-gradient(90deg, ${bgColor}, ${bgColor}cc);"></div>
            <div class="heat-cell-body">
              <div class="heat-cell-head">
                <div>
                  <div class="heat-cell-name"><i class="fas fa-building"></i>${escapeHtml(dept.department)}</div>
                  <div class="heat-cell-members"><i class="fas fa-users"></i> ${dept.total_members} members</div>
                </div>
                <div class="heat-rate-badge" style="background: ${bgColor};">
                  ${rate}<small>%</small>
                </div>
              </div>
              <div class="heat-progress">
                <div class="heat-progress-fill" style="width: ${Math.min(100, rate)}%; background: ${bgColor};"></div>
              </div>
              <div class="heat-cell-stats">
                <div class="heat-stat paid"><div class="num">${dept.paid}</div><div class="lbl">Paid</div></div>
                <div class="heat-stat advance"><div class="num">${dept.advance}</div><div class="lbl">Advance</div></div>
                <div class="heat-stat pending"><div class="num">${dept.pending}</div><div class="lbl">Pending</div></div>
                <div class="heat-stat unpaid"><div class="num">${dept.unpaid}</div><div class="lbl">Unpaid</div></div>
              </div>${dept.paid_other_method ? `<div class="heat-cell-hint"><i class="fas fa-info-circle"></i> ${dept.paid_other_method} paid via ${escapeHtml(paymentType)}</div>` : ''}
            </div>
          </div>
        `;
      }).join("");

    } catch (error) {
      console.error("Failed to load compliance heatmap:", error);
      grid.innerHTML = '<div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #dc3545;"><i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px;"></i><p>Failed to load compliance data. Please try again.</p></div>';
    } finally {
      const btn2 = document.querySelector("#compliance-heatmap .hm-load-btn");
      if (btn2) btn2.disabled = false;
    }
  }

  // Canvas value labels — draws % / counts at bar ends so 0% data is
  // obviously "data", never a broken blank chart.
  const hmValueLabels = {
    id: "hmValueLabels",
    afterDatasetsDraw(chart) {
      if (chart.config.type !== "bar") return;
      const horizontal = chart.options.indexAxis === "y";
      const { ctx } = chart;
      chart.data.datasets.forEach((ds, di) => {
        if (!ds.hmLabel && !ds.hmLabelCounts) return;
        const meta = chart.getDatasetMeta(di);
        if (meta.hidden) return;
        meta.data.forEach((bar, i) => {
          const raw = ds.data[i];
          if (raw == null) return;
          if (ds.hmLabelCounts && !raw) return; // skip zeros in stacked counts
          const text = ds.hmLabel ? raw + "%" : String(raw);
          ctx.save();
          ctx.font = "700 11px 'Inter',-apple-system,'Segoe UI',Roboto,sans-serif";
          if (horizontal) {
            const wide = bar.width > 26;
            ctx.fillStyle = wide ? "#ffffff" : "#546e7a";
            ctx.textAlign = wide ? "right" : "left";
            ctx.textBaseline = "middle";
            ctx.fillText(text, wide ? bar.x - 5 : bar.x + 5, bar.y);
          } else {
            ctx.fillStyle = "#546e7a";
            ctx.textAlign = "center";
            ctx.textBaseline = "bottom";
            ctx.fillText(text, bar.x, bar.y - 4);
          }
          ctx.restore();
        });
      });
    },
  };

  function buildHeatmapCharts(departments, analytics) {
    const donutCtx = document.getElementById("heatmap-donut-chart");
    const stackedCtx = document.getElementById("heatmap-stacked-chart");

    const rateLabels = departments.map(d => d.department);

    const pctEl = document.getElementById("heatmap-donut-pct");
    if (pctEl) pctEl.textContent = (analytics.overall_compliance_rate || 0) + "%";

    // Compliance rate per department — pure HTML/CSS bars (cannot fail to render,
    // unlike canvas bars created while the tab was hidden).
    const rateBox = document.getElementById("heatmap-rate-bars");
    if (rateBox) {
      if (!departments.length) {
        rateBox.innerHTML = '<p class="pd-card-placeholder">No department data for these filters.</p>';
      } else {
        rateBox.innerHTML = '<div class="hbar-list">' + departments.map(d => {
          const rate = Math.max(0, Math.min(100, Number(d.compliance_rate || 0)));
          const color = heatmapColorMap[d.color] || "#6c757d";
          return '<div class="hbar-row">' +
            '<span class="hbar-name" title="' + String(d.department).replace(/[&<>"']/g, "") + '">' + d.department + '</span>' +
            '<div class="hbar-track"><div class="hbar-fill" style="width:' + rate + '%;background:' + color + ';"></div></div>' +
            '<span class="hbar-val" style="color:' + color + ';">' + rate + '%</span>' +
          '</div>';
        }).join("") + '</div>';
      }
    }

    if (donutCtx) {
      heatmapDonutChart = new Chart(donutCtx, {
        type: "doughnut",
        data: {
          labels: ["Paid", "Pending", "Unpaid"],
          datasets: [{
            data: [
              analytics.total_paid_members,
              analytics.total_pending_payments,
              analytics.total_unpaid_members,
            ],
            backgroundColor: ["#28a745", "#ffc107", "#dc3545"],
            borderWidth: 3,
            borderColor: "#fff",
            hoverOffset: 6,
          }],
        },
        options: {
          animation: false,
          responsive: true,
          maintainAspectRatio: false,
          cutout: "70%",
          plugins: {
            legend: {
              position: "bottom",
              labels: { usePointStyle: true, pointStyle: "circle", padding: 14, font: { size: 11, weight: 600 } },
            },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  return ` ${ctx.label}: ${ctx.raw}`;
                },
              },
            },
          },
        },
      });
    }

    if (stackedCtx && departments.length) {
      heatmapStackedChart = new Chart(stackedCtx, {
        type: "bar",
        data: {
          labels: rateLabels,
          datasets: [
            {
              label: "Paid",
              data: departments.map(d => d.paid),
              backgroundColor: "#28a745",
              borderRadius: 4,
              barThickness: 16,
              hmLabelCounts: true,
            },
            {
              label: "Pending",
              data: departments.map(d => d.pending),
              backgroundColor: "#ffc107",
              borderRadius: 4,
              barThickness: 16,
              hmLabelCounts: true,
            },
            {
              label: "Unpaid",
              data: departments.map(d => d.unpaid),
              backgroundColor: "#dc3545",
              borderRadius: 4,
              barThickness: 16,
              hmLabelCounts: true,
            },
          ],
        },
        options: {
          animation: false,
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            hmValueLabels,
            legend: {
              position: "bottom",
              labels: { usePointStyle: true, pointStyle: "circle", padding: 14, font: { size: 11, weight: 600 } },
            },
          },
          scales: {
            x: { stacked: true, beginAtZero: true, ticks: { precision: 0, font: { size: 10 } }, grid: { color: "#eef3ee" } },
            y: { stacked: true, grid: { display: false }, ticks: { font: { size: 11, weight: 600 }, color: "#455a64" } },
          },
        },
      });
    }
  }

  function buildDeptMonthOptions(selected) {
    const names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"];
    return names.map((n, i) => {
      const v = String(i + 1).padStart(2, "0");
      return `<option value="${v}" ${v === selected ? "selected" : ""}>${n}</option>`;
    }).join("");
  }

  function buildDeptYearOptions(selected) {
    let years = [];
    const source = document.getElementById("heatmap-year");
    if (source) Array.from(source.options).forEach(o => years.push(o.value));
    if (years.length === 0) years = ["2024", "2025", "2026"];
    return years.map(y => `<option value="${y}" ${y === selected ? "selected" : ""}>${y}</option>`).join("");
  }

  async function reloadDepartmentDetail(department) {
    const year = document.getElementById("dept-year").value;
    const month = document.getElementById("dept-month").value;
    const paymentType = document.getElementById("dept-payment-type").value;

    const params = new URLSearchParams({ department: department, month: month, year: year });
    if (paymentType) params.set("payment_method", paymentType);

    try {
      const response = await fetch(`/api/auditor/department-detail/?${params}`, {
        method: "GET",
        headers: {
          "X-CSRFToken": getCSRFToken(),
        },
      });

      const data = await response.json();

      if (!data.ok) {
        showToast(data.error || "Failed to load department details", true);
        return;
      }

      document.getElementById("dept-detail-month-label").textContent = data.month;
      document.getElementById("dept-summary-total").textContent = data.summary.total_members;
      document.getElementById("dept-summary-paid").textContent = data.summary.paid;
      document.getElementById("dept-summary-advance").textContent = data.summary.advance;
      document.getElementById("dept-summary-pending").textContent = data.summary.pending;
      document.getElementById("dept-summary-unpaid").textContent = data.summary.unpaid;

      document.getElementById("department-members-table").innerHTML = data.members.map(member => `
        <tr class="member-row" data-name="${escapeHtml(member.full_name).toLowerCase()}" data-unpaid="${!['Paid', 'Full Payment', 'Advance / Covered'].includes(member.payment_status)}">
          <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">${escapeHtml(member.employee_id)}</td>
          <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">${escapeHtml(member.full_name)}</td>
          <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">${renderPaymentStatusBadge(member.payment_status || member.status_display)}</td>
          <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">${escapeHtml(member.payment_method)}${member.paid_other_method ? ' <span style="display:inline-block;background:#e7f3ff;color:#0b5cad;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;margin-left:4px;">Other Method</span>' : ''}</td>
          <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">${escapeHtml(member.last_payment_date)}</td>
          <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">
            <button onclick="viewMemberPaymentHistory(${member.member_id})" style="padding: 6px 12px; background: #0F5A36; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
              View History
            </button>
          </td>
        </tr>
      `).join('');

      // Re-apply the active search to the refreshed rows
      const searchTerm = (document.getElementById("member-search").value || "").toLowerCase();
      document.querySelectorAll("#department-members-table .member-row").forEach(row => {
        row.style.display = row.getAttribute("data-name").includes(searchTerm) ? "" : "none";
      });
    } catch (error) {
      console.error("Failed to load department detail:", error);
      showToast("Failed to load department details", true);
    }
  }

  async function openDepartmentDetail(department, month) {
    const year = month.split("-")[0];
    const mon = month.split("-")[1];
    const defaultType = document.getElementById("heatmap-payment-type").value;

    // Create modal content with its own month/year/payment-type filters
    const modalHtml = `
      <div id="department-modal" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 2000; display: flex; align-items: center; justify-content: center;">
        <div style="background: #fff; border-radius: 12px; width: 90%; max-width: 900px; max-height: 80vh; overflow: hidden; display: flex; flex-direction: column;">
          <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <h3 style="margin: 0; font-size: 18px;">${escapeHtml(department)}</h3>
              <p style="margin: 4px 0 0; color: #666; font-size: 14px;"><i class="fas fa-calendar-alt"></i> <span id="dept-detail-month-label">Loading...</span></p>
            </div>
            <button onclick="closeDepartmentModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; padding: 0 8px;">&times;</button>
          </div>

          <div style="padding: 14px 20px; background: #f0f5ef; display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <label style="font-size: 12px; font-weight: 600; color: #4b5e4b;"><i class="fas fa-calendar-alt"></i> Month</label>
            <select id="dept-month" style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
              ${buildDeptMonthOptions(mon)}
            </select>
            <label style="font-size: 12px; font-weight: 600; color: #4b5e4b;"><i class="fas fa-calendar"></i> Year</label>
            <select id="dept-year" style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
              ${buildDeptYearOptions(year)}
            </select>
            <label style="font-size: 12px; font-weight: 600; color: #4b5e4b;"><i class="fas fa-wallet"></i> Payment Type</label>
            <select id="dept-payment-type" style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
              <option value="" ${defaultType === "" ? "selected" : ""}>All Types</option>
              <option value="Salary Deduction" ${defaultType === "Salary Deduction" ? "selected" : ""}>Salary Deduction</option>
              <option value="GCash" ${defaultType === "GCash" ? "selected" : ""}>GCash</option>
              <option value="Bank Transfer" ${defaultType === "Bank Transfer" ? "selected" : ""}>Bank Transfer</option>
              <option value="Cash (Office Payment)" ${defaultType === "Cash (Office Payment)" ? "selected" : ""}>Cash (Office Payment)</option>
            </select>
            <span style="margin-left: auto; font-size: 12px; color: #78909c;"><i class="fas fa-sync-alt"></i> Filter switches view to the selected month</span>
          </div>

          <div style="padding: 20px; background: #f8f9fa; display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;">
            <div style="text-align: center;">
              <div style="font-size: 12px; color: #666;">Total Members</div>
              <div style="font-size: 24px; font-weight: 700;" id="dept-summary-total">0</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 12px; color: #666;">Paid</div>
              <div style="font-size: 24px; font-weight: 700; color: #28a745;" id="dept-summary-paid">0</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 12px; color: #666;">Advance/Covered</div>
              <div style="font-size: 24px; font-weight: 700; color: #0b7285;" id="dept-summary-advance">0</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 12px; color: #666;">Pending</div>
              <div style="font-size: 24px; font-weight: 700; color: #ffc107;" id="dept-summary-pending">0</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 12px; color: #666;">Unpaid</div>
              <div style="font-size: 24px; font-weight: 700; color: #dc3545;" id="dept-summary-unpaid">0</div>
            </div>
          </div>

          <div style="padding: 20px; flex: 1; overflow-y: auto;">
            <div style="margin-bottom: 12px; display: flex; gap: 12px; align-items: center;">
              <input type="text" id="member-search" placeholder="Search members..." style="flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px;">
              <button onclick="sendRemindersToUnpaid()" class="btn btn-primary" style="padding: 8px 16px; background: #dc3545; border: none; color: #fff; border-radius: 6px; cursor: pointer;">
                <i class="fas fa-bell"></i> Send Reminders to Unpaid
              </button>
            </div>

            <table style="width: 100%; border-collapse: collapse;">
              <thead>
                <tr style="background: #f8f9fa;">
                  <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; font-size: 13px;">Faculty ID</th>
                  <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; font-size: 13px;">Name</th>
                  <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; font-size: 13px;">Payment</th>
                  <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; font-size: 13px;">Method</th>
                  <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; font-size: 13px;">Last Payment</th>
                  <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; font-size: 13px;">Action</th>
                </tr>
              </thead>
              <tbody id="department-members-table"></tbody>
            </table>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    ["dept-month", "dept-year", "dept-payment-type"].forEach(id => {
      document.getElementById(id).addEventListener("change", function () {
        reloadDepartmentDetail(department);
      });
    });

    // Add search functionality
    document.getElementById('member-search').addEventListener('input', function(e) {
      const searchTerm = e.target.value.toLowerCase();
      document.querySelectorAll('#department-members-table .member-row').forEach(row => {
        row.style.display = row.getAttribute('data-name').includes(searchTerm) ? '' : 'none';
      });
    });

    await reloadDepartmentDetail(department);
  }

  function closeDepartmentModal() {
    const modal = document.getElementById('department-modal');
    if (modal) modal.remove();
  }

  async function viewMemberPaymentHistory(memberId) {
    try {
      const response = await fetch(`/api/auditor/member-payment-history/?member_id=${memberId}`, {
        method: "GET",
        headers: {
          "X-CSRFToken": getCSRFToken(),
        },
      });

      const data = await response.json();

      if (!data.ok) {
        showToast(data.error || "Failed to load payment history", true);
        return;
      }

      // Create payment history modal
      const historyHtml = `
        <div id="payment-history-modal" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 3000; display: flex; align-items: center; justify-content: center;">
          <div style="background: #fff; border-radius: 12px; width: 90%; max-width: 600px; max-height: 80vh; overflow: hidden; display: flex; flex-direction: column;">
            <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
              <div>
                <h3 style="margin: 0; font-size: 18px;">${escapeHtml(data.member.full_name)}</h3>
                <p style="margin: 4px 0 0; color: #666; font-size: 14px;">${escapeHtml(data.member.employee_id)} • ${escapeHtml(data.member.department)}</p>
              </div>
              <button onclick="closePaymentHistoryModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; padding: 0 8px;">&times;</button>
            </div>
            
            <div style="padding: 20px; flex: 1; overflow-y: auto;">
              <h4 style="margin: 0 0 16px;">Monthly Dues Payment History</h4>
              <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 8px;">
                ${data.payment_history.map(payment => `
                  <div style="padding: 12px; border-radius: 8px; text-align: center; border: 2px solid ${payment.status === '✅' ? '#28a745' : payment.status === '⏳' ? '#ffc107' : payment.status === '🔵' ? '#17a2b8' : '#dc3545'}; background: ${payment.status === '✅' ? '#d4edda' : payment.status === '⏳' ? '#fff3cd' : payment.status === '🔵' ? '#d1ecf1' : '#f8d7da'};">
                    <div style="font-size: 24px; margin-bottom: 4px;">${payment.status}</div>
                    <div style="font-size: 11px; font-weight: 600;">${payment.month_display}</div>
                    ${payment.advance_label ? `<div style="font-size: 10px; color: #0b7285; margin-top: 2px; font-weight: 600;">${payment.advance_label}</div>` : ''}
                  </div>
                `).join('')}
              </div>
              
              ${data.payment_history.length === 0 ? '<p style="text-align: center; color: #888; margin-top: 20px;">No payment history available</p>' : ''}
            </div>
          </div>
        </div>
      `;

      document.body.insertAdjacentHTML('beforeend', historyHtml);

    } catch (error) {
      console.error("Failed to load payment history:", error);
      showToast("Failed to load payment history", true);
    }
  }

  function closePaymentHistoryModal() {
    const modal = document.getElementById('payment-history-modal');
    if (modal) modal.remove();
  }

  async function sendRemindersToUnpaid() {
    const unpaidMemberIds = [];
    document.querySelectorAll('.member-row[data-unpaid="true"]').forEach(row => {
      if (row.style.display === 'none') return;
      const memberId = row.querySelector('button').getAttribute('onclick').match(/\d+/)[0];
      unpaidMemberIds.push(parseInt(memberId));
    });

    if (unpaidMemberIds.length === 0) {
      showToast("No unpaid members to send reminders to", true);
      return;
    }

    const swalResult = await Swal.fire({
      title: `Send payment reminders to ${unpaidMemberIds.length} unpaid member${unpaidMemberIds.length === 1 ? "" : "s"}?`,
      html: `This will send a <strong>Monthly Dues Reminder</strong> notification to ${unpaidMemberIds.length} unpaid member${unpaidMemberIds.length === 1 ? "" : "s"} for the selected month.`,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Yes, send reminders",
      cancelButtonText: "Cancel",
      reverseButtons: true,
    });
    if (!swalResult.isConfirmed) return;

    const monthEl = document.getElementById("dept-month");
    const yearEl = document.getElementById("dept-year");
    const month = monthEl ? monthEl.value : document.getElementById("heatmap-month").value;
    const year = yearEl ? yearEl.value : document.getElementById("heatmap-year").value;

    try {
      const csrf = getCSRFToken();
      const response = await fetch('/api/auditor/send-reminder/', {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          ...(csrf ? { "X-CSRFToken": csrf } : {}),
        },
        body: JSON.stringify({
          member_ids: unpaidMemberIds,
          month: month,
          year: year,
        }),
      });

      let data;
      try {
        data = await response.json();
      } catch (parseErr) {
        throw new Error(`Unexpected response (${response.status}). Your session may have expired - refresh and try again.`);
      }

      if (data.ok) {
        showToast(data.message);
      } else if (response.status === 401 || (data && data.session_expired)) {
        showToast("Your session has expired. Please log in again.", true);
        setTimeout(() => { window.location.href = "/?session_expired=1"; }, 1200);
      } else {
        showToast(data.error || "Failed to send reminders", true);
      }
    } catch (error) {
      console.error("Failed to send reminders:", error);
      showToast("Failed to send reminders", true);
    }
  }

  window.loadComplianceHeatmap = loadComplianceHeatmap;
  window.openDepartmentDetail = openDepartmentDetail;
  window.closeDepartmentModal = closeDepartmentModal;
  window.viewMemberPaymentHistory = viewMemberPaymentHistory;
  window.closePaymentHistoryModal = closePaymentHistoryModal;
  window.sendRemindersToUnpaid = sendRemindersToUnpaid;

    const aidSelectAll = document.getElementById("aid-select-all");
    if (aidSelectAll) {
      aidSelectAll.addEventListener("change", function () {
        const checked = this.checked;
        document.querySelectorAll("#pendingAidsTable .aid-row-check").forEach(cb => {
          cb.checked = checked;
          const aid = cb.value;
          if (checked) state.selectedAidIds.add(aid);
          else state.selectedAidIds.delete(aid);
          const row = cb.closest("tr");
          if (row) row.classList.toggle("selected-row", checked);
        });
        updateAidBatchBar();
      });
    }
    document.getElementById("aid-batch-verify")?.addEventListener("click", function () {
      submitAidBatchVerify("Verified");
    });
    document.getElementById("aid-batch-return")?.addEventListener("click", function () {
      submitAidBatchVerify("Returned");
    });
    document.getElementById("aid-batch-clear")?.addEventListener("click", function () {
      clearAidSelection();
    });

    refreshAll();
    loadAuditedLogs();

    getEl("auditLogSearch")?.addEventListener("input", applyAuditLogFilters);
    getEl("auditLogResultFilter")?.addEventListener("change", applyAuditLogFilters);
    getEl("auditLogDateFrom")?.addEventListener("change", applyAuditLogFilters);
    getEl("auditLogDateTo")?.addEventListener("change", applyAuditLogFilters);
  }

  // Global handlers for inline onclick attributes
  window.confirmLogout = function () {
    const logoutUrl = "/logout/";
    Swal.fire({
      title: "Logout?",
      text: "Do you want to log out of the system?",
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Yes, logout",
      cancelButtonText: "No, stay",
      reverseButtons: true,
    }).then((result) => {
      if (result.isConfirmed) {
        // Clear persisted tab on logout
        localStorage.removeItem("auditor_active_tab");
        window.location.href = logoutUrl;
      }
    });
  };

  window.triggerConfirmYes = function () {
    clearPaymentUI();
    clearAidUI();
    refreshAll();
    const modal = getEl("customConfirmModal");
    if (modal) modal.style.display = "none";
    showToast(
      "Compliance Database successfully flushed back to defaults.",
      false,
    );
  };

  window.closeConfirmModal = function () {
    const modal = getEl("customConfirmModal");
    if (modal) modal.style.display = "none";
  };

  window.showCustomModal = function (title, text) {
    const titleEl = getEl("modalAlertTitle");
    const textEl = getEl("modalAlertMessage");
    if (titleEl) titleEl.innerText = title;
    if (textEl) textEl.innerText = text;
    const modal = getEl("customAlertModal");
    if (modal) modal.style.display = "flex";
  };

  window.closeCustomModal = function () {
    const modal = getEl("customAlertModal");
    if (modal) modal.style.display = "none";
  };

  window.toggleFolder = toggleFolder;

  async function loadReportTable() {
    const table = getEl("reportTable");
    if (!table) return;
    const tbody = table.querySelector("tbody");
    if (!tbody) return;
    tbody.innerHTML =
      '<tr><td colspan="5" style="text-align:center;color:#888;">Loading ...</td></tr>';
    try {
      const resp = await fetch("/api/auditor/reports/", {
        credentials: "same-origin",
      });
      const data = await resp.json().catch(() => []);
      if (!resp.ok) {
        throw new Error(
          (data && data.error) || `Request failed: ${resp.status}`,
        );
      }
      if (!Array.isArray(data) || !data.length) {
        tbody.innerHTML =
          '<tr><td colspan="5" style="text-align:center;color:#888;">No generated compliance certifications yet.</td></tr>';
        return;
      }
      tbody.innerHTML = "";
      data.forEach((r) => {
        const tr = document.createElement("tr");
        tr.innerHTML =
          `<td>${r.prepared_date ? new Date(r.prepared_date).toLocaleString() : "-"}</td>` +
          `<td>${r.report_title || r.title || r.report_type || "-"}</td>` +
          `<td>${r.report_period || r.period || "-"} ` +
          `<span style="color:#888;">(${r.certification_status || r.status || "-"})</span></td>` +
          `<td>${(r.prepared_by_user_id_FK && r.prepared_by_user_id_FK.full_name) || r.prepared_by || "-"}</td>` +
          `<td class="action-cell"><button class="btn-icon btn-view" onclick="viewAuditorReport(${r.report_id})">` +
          `<i class="fa-solid fa-eye"></i> View</button></td>`;
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#c00;">Failed to load certifications.</td></tr>';
      showToast(e.message || "Failed loading compliance certifications.", true);
    }
  }

  window.viewAuditorReport = async function (reportId) {
    const titleEl = getEl("modalAlertTitle");
    const textEl = getEl("modalAlertMessage");
    const modal = getEl("customAlertModal");
    if (titleEl) titleEl.innerText = "Loading ...";
    if (textEl) textEl.innerText = "";
    if (modal) modal.style.display = "flex";
    try {
      const resp = await fetch(`/api/auditor/reports/${reportId}/`, {
        credentials: "same-origin",
      });
      const r = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(r.error || `Request failed: ${resp.status}`);
      }
      if (titleEl) titleEl.innerText = r.report_title || r.title || "Compliance Certification";
      if (textEl)
        textEl.innerText =
          `Period: ${r.report_period || r.period || "-"}\n` +
          `Status: ${r.report_status || r.status || "-"}\n` +
          `Presentation: ${r.presentation_status || "-"}\n` +
          `Certification: ${r.certification_status || "-"}\n\n` +
          `Findings:\n${r.findings_summary || "N/A"}`;
    } catch (e) {
      if (titleEl) titleEl.innerText = "Error";
      if (textEl) textEl.innerText = e.message || "Failed to load report detail.";
      showToast(e.message || "Failed to load report detail.", true);
    }
  };

  window.handleReportCompilerSubmit = async function (e) {
    e.preventDefault();
    e.stopPropagation();
    const start = getEl("rep_start")?.value;
    const end = getEl("rep_end")?.value;
    if (!start) {
      showToast("Please select a Start Window Date.", true);
      return;
    }
    // Backend requires {year, month}; derive from the selected start date (YYYY-MM-DD).
    const parts = start.split("-");
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10);
    if (!year || !month) {
      showToast("Invalid start date; could not derive year/month.", true);
      return;
    }
    const csrf = getCSRFToken();
    try {
      const resp = await fetch("/api/auditor/reports/create/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          ...(csrf ? { [CSRF_HEADER_NAME]: csrf } : {}),
        },
        body: JSON.stringify({ year, month }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.error || `Server error ${resp.status}`);
      }
      showToast("Compliance certification compiled successfully.", false);
      await loadReportTable();
    } catch (err) {
      showToast(err.message || "Failed to compile compliance certification.", true);
    }
  };

  // Allow external callers (websocket helper) to request a dashboard refresh even if refreshAll
  // is not exported to window scope. This listens to the 'auditor:refresh' event dispatched
  // by websocket.js fallback and calls the same refresh handler.
  document.addEventListener('auditor:refresh', function () {
    try {
      if (typeof window.refreshAll === 'function') {
        window.refreshAll();
      } else if (typeof refreshAll === 'function') {
        refreshAll();
      }
    } catch (e) {}
  });

  // Expose module activation for inline handlers (mockup behavior):
  // KPI cards, quick actions, and links call setActiveModule via onclick.
  window.setActiveModule = setActiveModule;

  document.addEventListener("turbo:load", init);
})();
