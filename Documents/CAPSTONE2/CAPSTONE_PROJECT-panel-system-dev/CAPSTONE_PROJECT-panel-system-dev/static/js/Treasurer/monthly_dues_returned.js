(function () {
  "use strict";

  const MENU_TARGET_ID = "view-monthly-dues-returned";

  const FORM_ID = "monthlyDuesReturnedEditForm";
  const SELECT_RECORD_ID = "monthly_dues_returned_record_id";

  const INPUT_MONTH_COVERED = "md_returned_month";
  const INPUT_PAYMENT_DATE = "md_returned_date";
  const INPUT_AMOUNT = "md_returned_amount";
  const INPUT_PAYMENT_METHOD = "md_returned_method";
  const INPUT_RECEIPT_NUMBER_OTC = "md_returned_ref";
  const INPUT_RECEIPT_NUMBER_SALARY = "md_returned_ref_salary";
  const INPUT_REMITTANCE_REFERENCE = "md_returned_remittance";
  const INPUT_DEDUCTION_BATCH_REFERENCE = "md_returned_summary";

  const CSRF_HEADER_NAME = "X-CSRFToken";

  let isSubmitting = false;
  let currentReturnedSource = "Unknown";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getDuesSourceMethod(record) {
    const method = String(record.payment_method || "").trim().toLowerCase();
    // Handle Salary Deduction
    if (method.includes("salary") || method.includes("deduction")) return "Salary Deduction";
    // Handle OTC Payment (including Bank Transfer variants)
    if (method.includes("otc") || method.includes("over-the-counter") || 
        method.includes("counter") || method.includes("bank transfer") || 
        method.includes("bank") || method.includes("transfer")) return "OTC Payment";
    // Return Unknown only if method is truly empty, otherwise show the actual method
    return method ? method.charAt(0).toUpperCase() + method.slice(1) : "Unknown";
  }

  function getDuesSourceBadge(method) {
    switch (method) {
      case "Salary Deduction":
        return '<span class="badge-zero badge-green" style="font-size:0.75rem;white-space:nowrap;display:inline-block;">Salary Deduction</span>';
      case "OTC Payment":
        return '<span class="badge-zero badge-yellow" style="font-size:0.75rem;white-space:nowrap;display:inline-block;">OTC Payment</span>';
      case "Unknown":
        return '<span class="badge-zero badge-red" style="font-size:0.75rem;white-space:nowrap;display:inline-block;">Unknown</span>';
      default:
        // For other payment methods, use a neutral badge
        return '<span class="badge-zero" style="font-size:0.75rem;white-space:nowrap;display:inline-block;background:#f5f5f5;color:#666;">' + escapeHtml(method) + '</span>';
    }
  }

  function extractRejectionDetails(text) {
    if (!text) return [];
    const match = text.match(/"rejection_details"\s*:\s*(\[.*?\])/s);
    if (match) {
      try {
        return JSON.parse(match[1]);
      } catch (e) {
        return [];
      }
    }
    return [];
  }

  function cleanRejectionReason(text) {
    if (!text) return "";
    const idx = text.indexOf('{"rejection_details"');
    if (idx !== -1) return text.substring(0, idx).trim();
    return text.trim();
  }

  function getRejectionDetails(record) {
    if (record.rejection_details && record.rejection_details.length > 0) {
      return record.rejection_details;
    }
    return extractRejectionDetails(record.rejection_reason);
  }

  function normalizeCoveredMonth(value) {
    const trimmed = String(value || "").trim();
    const fullMatch = trimmed.match(/^(\d{4})-(0[1-9]|1[0-2])-(\d{2})$/);
    if (fullMatch) return `${fullMatch[1]}-${fullMatch[2]}`;
    const ymMatch = trimmed.match(/^(\d{4})-(0[1-9]|1[0-2])$/);
    if (ymMatch) return `${ymMatch[1]}-${ymMatch[2]}`;
    const parsed = new Date(trimmed);
    if (!Number.isNaN(parsed.getTime())) {
      const y = parsed.getFullYear();
      const m = String(parsed.getMonth() + 1).padStart(2, "0");
      return `${y}-${m}`;
    }
    return trimmed;
  }

  function normalizeDate(value) {
    if (!value) return "";
    const trimmed = String(value).trim();
    const match = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (match) return `${match[1]}-${match[2]}-${match[3]}`;
    const parsed = new Date(trimmed);
    if (!Number.isNaN(parsed.getTime())) {
      const y = parsed.getFullYear();
      const m = String(parsed.getMonth() + 1).padStart(2, "0");
      const d = String(parsed.getDate()).padStart(2, "0");
      return `${y}-${m}-${d}`;
    }
    return "";
  }

  async function fetchReturnedMonthlyDues() {
    const resp = await fetch("/api/treasurer/monthly-dues/returned/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json();
    if (!resp.ok || !data || !data.ok)
      throw new Error(
        (data && data.error) || "Failed to load returned monthly dues.",
      );
    return data.records || [];
  }

  function mdReturnedGetChecked(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]:checked"), vals = [];
    for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v !== "") vals.push(v); }
    return vals;
  }

  function mdReturnedGetAllValues(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]"), vals = [];
    for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") vals.push(cbs[i].value); }
    return vals;
  }

  function mdReturnedToggleAll(containerId, checked) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") cbs[i].checked = checked; }
    mdReturnedApplyFilter();
  }

  function mdReturnedSyncAll(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    var allBox = cbs.length > 0 ? cbs[0] : null;
    if (!allBox) return;
    var allChecked = true;
    for (var i = 1; i < cbs.length; i++) { if (!cbs[i].checked) { allChecked = false; break; } }
    allBox.checked = allChecked;
  }

  function mdReturnedApplyFilter() {
    window.__renderReturnedMonthlyDuesList(window.__returnedMonthlyDuesRecords);
  }

  function mdReturnedToggleFilter() {
    var card = document.getElementById("mdReturnedFilterCard");
    if (!card) return;
    var opening = card.style.display === "none";
    card.style.display = opening ? "block" : "none";
    if (opening) {
      mdReturnedFillFilters();
      var handler = function(e) {
        var btn = document.querySelector('[onclick="mdReturnedToggleFilter()"]');
        if (card.contains(e.target) || (btn && btn.contains(e.target))) return;
        document.removeEventListener("click", handler);
        card.style.display = "none";
        mdReturnedApplyFilter();
      };
      setTimeout(function() { document.addEventListener("click", handler); }, 0);
    }
  }

  function mdReturnedFillFilters() {
    var stats = {}, sources = {}, i, r, arr = window.__returnedMonthlyDuesRecords || [];
    for (i = 0; i < arr.length; i++) {
      r = arr[i];
      if (r.payment_status) stats[r.payment_status] = 1;
      var s = getDuesSourceMethod(r);
      if (s) sources[s] = 1;
    }
    var sk = Object.keys(stats).sort(), srk = Object.keys(sources).sort();
    var sc = document.getElementById("mdReturnedStatusCheckboxes");
    if (sc) {
      sc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="mdReturnedToggleAll(\'mdReturnedStatusCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
      for (i = 0; i < sk.length; i++) sc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' + escapeHtml(sk[i]) + '" checked onchange="mdReturnedSyncAll(\'mdReturnedStatusCheckboxes\');mdReturnedApplyFilter()"> <span>' + escapeHtml(sk[i]) + '</span></label>';
    }
    var src = document.getElementById("mdReturnedSourceCheckboxes");
    if (src) {
      src.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="mdReturnedToggleAll(\'mdReturnedSourceCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
      for (i = 0; i < srk.length; i++) src.innerHTML += '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' + escapeHtml(srk[i]) + '" checked onchange="mdReturnedSyncAll(\'mdReturnedSourceCheckboxes\');mdReturnedApplyFilter()"> <span>' + escapeHtml(srk[i]) + '</span></label>';
    }
  }

  window.mdReturnedGetChecked = mdReturnedGetChecked;
  window.mdReturnedGetAllValues = mdReturnedGetAllValues;
  window.mdReturnedToggleAll = mdReturnedToggleAll;
  window.mdReturnedSyncAll = mdReturnedSyncAll;
  window.mdReturnedApplyFilter = mdReturnedApplyFilter;
  window.mdReturnedToggleFilter = mdReturnedToggleFilter;

  function renderReturnedRecords(records) {
    const tbody = document.querySelector("#monthlyDuesReturnedTable tbody");
    if (!tbody) return;

    var stats = mdReturnedGetChecked("mdReturnedStatusCheckboxes");
    if (stats.length === 0) { stats = mdReturnedGetAllValues("mdReturnedStatusCheckboxes"); mdReturnedSyncAll("mdReturnedStatusCheckboxes"); }
    var sources = mdReturnedGetChecked("mdReturnedSourceCheckboxes");
    if (sources.length === 0) { sources = mdReturnedGetAllValues("mdReturnedSourceCheckboxes"); mdReturnedSyncAll("mdReturnedSourceCheckboxes"); }

    var arr = records || [], flt = [], i, r;
    for (i = 0; i < arr.length; i++) {
      r = arr[i];
      if (stats.length && stats.indexOf(r.payment_status) === -1) continue;
      var s = getDuesSourceMethod(r);
      if (sources.length && sources.indexOf(s) === -1) continue;
      flt.push(r);
    }

    tbody.innerHTML = "";
    if (!records || records.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="8" style="text-align:center;color:#757575;">No returned monthly dues entries</td></tr>';
      return;
    }
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      return;
    }

    flt.forEach((r) => {
      const tr = document.createElement("tr");
      const sourceMethod = getDuesSourceMethod(r);
      const sourceBadge = getDuesSourceBadge(sourceMethod);
      tr.dataset.recordId = String(r.dues_id_PK);
      tr.innerHTML = [
        '<td style="padding:12px 8px;vertical-align:middle;">',
        escapeHtml(r.member_name || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">Code: ',
        escapeHtml(r.member_id_PK || ""),
        '</span></td>',
        '<td style="font-weight:600;padding:12px 8px;vertical-align:middle;">',
        escapeHtml(r.month_covered || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">Date: ',
        escapeHtml(r.payment_date || ""),
        '</span></td>',
        '<td style="font-weight:600;padding:12px 8px;vertical-align:middle;">',
        escapeHtml(r.amount || "0"),
        '</td>',
        '<td style="padding:12px 8px;vertical-align:middle;">',
        escapeHtml(r.payment_status || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">',
        escapeHtml(r.payment_method || ""),
        '</span></td>',
        '<td style="padding:12px 8px;vertical-align:middle;">',
        escapeHtml(r.receipt_number || r.remittance_reference || ""),
        '</td>',
        '<td style="padding:12px 8px;vertical-align:middle;text-align:center;">',
        sourceBadge,
        '</td>',
        '<td style="padding:12px 8px;vertical-align:middle;">',
        escapeHtml(cleanRejectionReason(r.rejection_reason || "")) || "—",
        '</td>',
        '<td style="padding:12px 8px;vertical-align:middle;text-align:center;">',
        '<button type="button" class="btn-brand btn-brand-secondary" style="padding:4px 10px;font-size:0.75rem;border-radius:6px;" onclick="window.__selectReturnedMonthlyDues(\'', r.dues_id_PK, '\')">Edit</button>',
        '</td>',
      ].join("");
      tbody.appendChild(tr);
    });
  }

  function transformFormForSource(source) {
    const titleEl = document.getElementById("returnedFormTitle");
    const submitBtn = document.getElementById("returnedSubmitBtn");
    const salaryFields = document.querySelectorAll(".salary-only");
    const otcFields = document.querySelectorAll(".otc-only");

    if (source === "Salary Deduction") {
      if (titleEl) titleEl.textContent = "Correct Salary Deduction";
      if (submitBtn) submitBtn.textContent = "Resubmit Salary Deduction";
      salaryFields.forEach((el) => (el.style.display = ""));
      otcFields.forEach((el) => (el.style.display = "none"));
    } else if (source === "OTC Payment") {
      if (titleEl) titleEl.textContent = "Correct OTC Payment";
      if (submitBtn) submitBtn.textContent = "Resubmit OTC Payment";
      otcFields.forEach((el) => (el.style.display = ""));
      salaryFields.forEach((el) => (el.style.display = "none"));
    } else {
      if (titleEl) titleEl.textContent = "Correct & Resubmit Monthly Dues";
      if (submitBtn) submitBtn.textContent = "Resubmit Corrected Monthly Dues";
      salaryFields.forEach((el) => (el.style.display = "none"));
      otcFields.forEach((el) => (el.style.display = "none"));
    }
  }

  function renderRejectionDetails(containerId, record) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";
    const details = getRejectionDetails(record);
    if (details.length === 0) {
      container.style.display = "none";
    } else {
      container.style.display = "block";
      details.forEach(function (d) {
        const fieldLabel = d.field || "Unknown field";
        const remark = d.remarks || "";
        const item = document.createElement("div");
        item.style.cssText = "border:1px solid #e53935;border-radius:8px;padding:10px 12px;margin-bottom:8px;background:#fff5f5;";
        item.innerHTML =
          '<div style="font-weight:600;font-size:0.82rem;color:#e53935;margin-bottom:4px;">' +
          escapeHtml(fieldLabel) +
          "</div>" +
          (remark
            ? '<div style="font-size:0.8rem;color:#546e7a;line-height:1.4;">' +
              escapeHtml(remark) +
              "</div>"
            : "");
        container.appendChild(item);
      });
    }
  }

  function setPhotoPreview(prefix, record) {
    const thumbnailContainer = document.getElementById(`${prefix}_thumbnail_container`);
    const thumbnailImg = document.getElementById(`${prefix}_thumbnail`);
    const thumbnailLink = document.getElementById(`${prefix}_thumbnail_link`);
    if (thumbnailContainer && thumbnailImg && thumbnailLink) {
      if (record.proof_url) {
        thumbnailImg.src = record.proof_url;
        thumbnailLink.href = record.proof_url;
        thumbnailContainer.style.display = "block";
      } else {
        thumbnailContainer.style.display = "none";
        thumbnailImg.src = "";
        thumbnailLink.href = "";
      }
    }

    const indicator = document.getElementById(`${prefix}_preview`);
    if (indicator) {
      if (record.proof_url) {
        indicator.innerHTML = `
          <img src="${escapeHtml(record.proof_url)}" style="max-height:140px;border-radius:8px;margin-top:8px;border:1px solid #cfdccc;" />
          <div style="font-size:0.8rem;color:#757575;margin-top:4px;">Existing attachment on record</div>
        `;
        indicator.style.display = "block";
      } else {
        indicator.innerHTML = "✓ Receipt Document Attached!";
        indicator.style.display = "none";
      }
    }
  }

  function clearForm() {
    FileQueue.clear("md_ret");
    const form = getEl(FORM_ID);
    if (form) form.reset();
    const rej = document.getElementById("md_rejection_reason_display");
    if (rej) rej.textContent = "Select a record to view rejection reason";
    const container = document.getElementById("md_rejection_details_container");
    if (container) {
      container.innerHTML = "";
      container.style.display = "none";
    }
    transformFormForSource("Unknown");
    currentReturnedSource = "Unknown";
  }

  function fillForm(record) {
    FileQueue.clear("md_ret");
    const recordId = getEl(SELECT_RECORD_ID);
    if (recordId) recordId.value = record.dues_id_PK;

    const setVal = (id, v) => {
      const el = getEl(id);
      if (el) el.value = v ?? "";
    };

    setVal(INPUT_MONTH_COVERED, normalizeCoveredMonth(record.month_covered || ""));
    setVal(INPUT_PAYMENT_DATE, normalizeDate(record.payment_date || ""));
    setVal(INPUT_AMOUNT, record.amount || "");

    const source = getDuesSourceMethod(record);
    currentReturnedSource = source;
    if (source === "Salary Deduction") {
      setVal(INPUT_RECEIPT_NUMBER_OTC, record.receipt_number || record.remittance_reference || "");
    } else if (source === "OTC Payment") {
      setVal(INPUT_RECEIPT_NUMBER_OTC, record.receipt_number || "");
      const methodSelect = getEl(INPUT_PAYMENT_METHOD);
      if (methodSelect) methodSelect.value = record.payment_method || "Cash OTC";
    }

    const rej = document.getElementById("md_rejection_reason_display");
    if (rej) rej.textContent = cleanRejectionReason(record.rejection_reason) || "No rejection reason on file.";

    renderRejectionDetails("md_rejection_details_container", record);
    setPhotoPreview("md_returned", record);
    transformFormForSource(source);
  }

  async function submitCorrection(e) {
    e.preventDefault();
    if (isSubmitting) return;

    const recordId = getEl(SELECT_RECORD_ID)?.value;
    if (!recordId) {
      showToast("Select a returned entry to edit.", true);
      return;
    }

    const month_covered = normalizeCoveredMonth(getEl(INPUT_MONTH_COVERED)?.value || "");
    const payment_date = getEl(INPUT_PAYMENT_DATE)?.value;
    const amount = getEl(INPUT_AMOUNT)?.value;
    const methodSelect = getEl(INPUT_PAYMENT_METHOD);
    const payment_method = currentReturnedSource === "Salary Deduction"
      ? "Salary Deduction"
      : (methodSelect ? methodSelect.value : "");
    const receipt_number = getEl(INPUT_RECEIPT_NUMBER_OTC)?.value || "";
    const remittance_reference = payment_method === "Salary Deduction" ? receipt_number : "";
    const deduction_batch_reference = getEl(INPUT_DEDUCTION_BATCH_REFERENCE)?.value || "";

    if (!payment_date) {
      showToast("Payment date is required.", true);
      return;
    }
    if (!month_covered || !/^\d{4}-(0[1-9]|1[0-2])$/.test(month_covered)) {
      showToast("Month covered must be YYYY-MM.", true);
      return;
    }
    if (!amount) {
      showToast("Amount is required.", true);
      return;
    }
    if (!payment_method) {
      showToast("Payment method is required.", true);
      return;
    }
    if (!receipt_number) {
      showToast("Receipt/Reference number is required.", true);
      return;
    }

    const fd = new FormData();
    fd.append("month_covered", month_covered);
    fd.append("payment_date", payment_date);
    fd.append("amount", amount);
    fd.append("payment_method", payment_method);
    fd.append("receipt_number", receipt_number);
    fd.append("remittance_reference", remittance_reference);
    fd.append("deduction_batch_reference", deduction_batch_reference);

    const mdSameAuditor = document.getElementById("md_same_auditor");
    fd.append("same_auditor", mdSameAuditor ? mdSameAuditor.checked : false);

    var mdRetFiles = FileQueue.getFiles("md_ret");
    if (mdRetFiles.length > 0) fd.append("md_returned_photo_file", mdRetFiles[0]);

    try {
      isSubmitting = true;
      const csrf = getCSRFToken();
      const resp = await fetch(
        `/api/treasurer/resubmit/monthly_dues/${recordId}/`,
        {
          method: "POST",
          body: fd,
          headers: csrf ? { [CSRF_HEADER_NAME]: csrf } : {},
          credentials: "same-origin",
        },
      );

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) {
        isSubmitting = false;
        showToast((data && data.error) || "Failed to submit correction.", true);
        return;
      }

      showToast("Returned monthly dues entry updated and resubmitted.");

      const records = await fetchReturnedMonthlyDues();
      window.__renderReturnedMonthlyDuesList(records);
      isSubmitting = false;
      clearForm();
    } catch (err) {
      isSubmitting = false;
      showToast("Network/server error while submitting correction.", true);
    }
  }

  function wireUp() {
    FileQueue.init("md_ret", { inputId: "md_ret_file_input", containerId: "md_ret_file_queue", maxFiles: 1 });

    const form = getEl(FORM_ID);
    if (form) {
      form.addEventListener("submit", submitCorrection);
    }

    window.__selectReturnedMonthlyDues = function (duesId) {
      const rec = window.__returnedMonthlyDuesRecords?.find(
        (r) => String(r.dues_id_PK) === String(duesId),
      );
      if (!rec) return;
      fillForm(rec);
    };

    window.__renderReturnedMonthlyDuesList = function (records) {
      renderReturnedRecords(records);
      window.__returnedMonthlyDuesRecords = records;
    };

    window.__refreshReturnedMonthlyDues = async function () {
      try {
        const records = await fetchReturnedMonthlyDues();
        window.__renderReturnedMonthlyDuesList(records);
      } catch (e) {
        console.error(e);
      }
    };
  }

  async function init() {
    wireUp();

    try {
      const records = await fetchReturnedMonthlyDues();
      window.__renderReturnedMonthlyDuesList(records);
    } catch (e) {
      console.error(e);
      renderReturnedRecords([]);
      window.__returnedMonthlyDuesRecords = [];
      clearForm();
    }
  }

  window.addEventListener("turbo:load", init);
})();
