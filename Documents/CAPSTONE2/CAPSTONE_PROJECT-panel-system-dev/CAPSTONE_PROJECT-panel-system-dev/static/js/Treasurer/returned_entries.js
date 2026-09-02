(function () {
  "use strict";

  const MENU_TARGET_ID = "view-returned-entries";

  const FORM_ID = "returnedEditForm";
  const SELECT_RECORD_ID = "returned_record_id";

  // Field ids to edit MembershipFee
  const INPUT_FEE_AMOUNT = "re_fee_amount";
  const INPUT_PAYMENT_METHOD = "re_fee_method";
  const INPUT_PAYMENT_STATUS = "re_fee_status";
  const INPUT_PAYMENT_DATE = "re_fee_date";
  const INPUT_RECEIPT_NUMBER = "re_fee_ref";
  const INPUT_DEPOSIT_REFERENCE = "re_fee_encoder";

  const INPUT_PARTIAL_AMOUNT = "re_fee_partial_amount";
  const FULL_AMOUNT_GROUP_ID = "re_fullAmountGroup";
  const PARTIAL_AMOUNT_GROUP_ID = "re_partialAmountGroup";

  const STATUS_SELECT_ID = INPUT_PAYMENT_STATUS;

  const CSRF_HEADER_NAME = "X-CSRFToken";

  let isSubmitting = false;

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

  function cleanRejectionReason(text) {
    if (!text) return "";
    const idx = text.indexOf('{"rejection_details"');
    if (idx !== -1) return text.substring(0, idx).trim();
    return text.trim();
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

  function getRejectionDetails(record) {
    if (record.rejection_details && record.rejection_details.length > 0) {
      return record.rejection_details;
    }
    return extractRejectionDetails(record.rejection_reason);
  }

  function syncStatusMode() {
    const statusSelect = getEl(STATUS_SELECT_ID);
    const fullGroup = getEl(FULL_AMOUNT_GROUP_ID);
    const partialGroup = getEl(PARTIAL_AMOUNT_GROUP_ID);
    const amountInput = getEl(INPUT_FEE_AMOUNT);
    const partialInput = getEl(INPUT_PARTIAL_AMOUNT);

    if (!statusSelect || !fullGroup || !partialGroup) return;

    const isPartial = statusSelect.value === "Partial";

    if (isPartial) {
      fullGroup.style.display = "none";
      partialGroup.style.display = "";
      if (amountInput) amountInput.removeAttribute("required");
      if (partialInput) partialInput.setAttribute("required", "required");
    } else {
      fullGroup.style.display = "";
      partialGroup.style.display = "none";
      if (amountInput) amountInput.setAttribute("required", "required");
      if (partialInput) partialInput.removeAttribute("required");
    }
  }

  async function fetchReturnedMembershipFees() {
    const resp = await fetch("/api/treasurer/membership-fees/returned/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json();
    if (!resp.ok || !data || !data.ok)
      throw new Error(
        (data && data.error) || "Failed to load returned entries.",
      );
    return data.records || [];
  }

  var returnedFeeFilterState = { status: [] };

  function returnedFeeGetChecked(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]:checked"), vals = [];
    for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v !== "") vals.push(v); }
    return vals;
  }

  function returnedFeeGetAllValues(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]"), vals = [];
    for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") vals.push(cbs[i].value); }
    return vals;
  }

  function returnedFeeToggleAll(containerId, checked) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") cbs[i].checked = checked; }
    returnedFeeApplyFilter();
  }

  function returnedFeeSyncAll(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    var allBox = cbs.length > 0 ? cbs[0] : null;
    if (!allBox) return;
    var allChecked = true;
    for (var i = 1; i < cbs.length; i++) { if (!cbs[i].checked) { allChecked = false; break; } }
    allBox.checked = allChecked;
  }

  function returnedFeeApplyFilter() {
    window.__renderReturnedFeeList(window.__returnedFeeRecords);
  }

  function returnedFeeToggleFilter() {
    var card = document.getElementById("returnedFeeFilterCard");
    if (!card) return;
    var opening = card.style.display === "none";
    card.style.display = opening ? "block" : "none";
    if (opening) {
      returnedFeeFillFilters();
      var handler = function(e) {
        var btn = document.querySelector('[onclick="returnedFeeToggleFilter()"]');
        if (card.contains(e.target) || (btn && btn.contains(e.target))) return;
        document.removeEventListener("click", handler);
        card.style.display = "none";
        returnedFeeApplyFilter();
      };
      setTimeout(function() { document.addEventListener("click", handler); }, 0);
    }
  }

  function returnedFeeFillFilters() {
    var stats = {}, i, r, arr = window.__returnedFeeRecords || [];
    for (i = 0; i < arr.length; i++) { r = arr[i]; if (r.payment_status) stats[r.payment_status] = 1; }
    var sk = Object.keys(stats).sort();
    var sc = document.getElementById("returnedFeeStatusCheckboxes");
    if (sc) {
      sc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="window.returnedFeeToggleAll(\'returnedFeeStatusCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
      for (i = 0; i < sk.length; i++) sc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' + escapeHtml(sk[i]) + '" checked onchange="window.returnedFeeSyncAll(\'returnedFeeStatusCheckboxes\');window.returnedFeeApplyFilter()"> <span>' + escapeHtml(sk[i]) + '</span></label>';
    }
  }

  window.returnedFeeGetChecked = returnedFeeGetChecked;
  window.returnedFeeGetAllValues = returnedFeeGetAllValues;
  window.returnedFeeToggleAll = returnedFeeToggleAll;
  window.returnedFeeSyncAll = returnedFeeSyncAll;
  window.returnedFeeApplyFilter = returnedFeeApplyFilter;
  window.returnedFeeToggleFilter = returnedFeeToggleFilter;

  function renderReturnedRecords(records) {
    const tbody = document.querySelector("#returnedFeesTable tbody");
    if (!tbody) return;

    var stats = returnedFeeGetChecked("returnedFeeStatusCheckboxes");
    if (stats.length === 0) { stats = returnedFeeGetAllValues("returnedFeeStatusCheckboxes"); returnedFeeSyncAll("returnedFeeStatusCheckboxes"); }

    var arr = records || [], flt = [], i, r;
    for (i = 0; i < arr.length; i++) {
      r = arr[i];
      if (stats.length && stats.indexOf(r.payment_status) === -1) continue;
      flt.push(r);
    }

    tbody.innerHTML = "";
    if (!records || records.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="7" style="text-align:center;color:#757575;">No returned entries to correct</td></tr>';
      return;
    }
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      return;
    }

    flt.forEach((r) => {
      const tr = document.createElement("tr");
      tr.dataset.recordId = String(r.fee_id_PK);
      tr.dataset.receipt = String(r.receipt_number || "");
      tr.innerHTML = [
        '<td style="font-weight:600;color:#1b5e20;">',
        escapeHtml(r.receipt_number || ""),
        '</td>',
        '<td>',
        escapeHtml(r.member_name || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">Code: ',
        escapeHtml(r.member_id_PK || ""),
        '</span></td>',
        '<td style="font-weight:600;">',
        escapeHtml(r.amount || "0"),
        '</td>',
        '<td>',
        '<span style="font-size:0.75rem;color:#757575;">Date: ',
        escapeHtml(r.payment_date || ""),
        '</span></td>',
        '<td>',
        escapeHtml(r.payment_status || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">Method: ',
        escapeHtml(r.payment_method || ""),
        '</span></td>',
        '<td>',
        escapeHtml(cleanRejectionReason(r.rejection_reason || "")) || "—",
        '</td>',
        '<td>',
        '<button type="button" class="btn-brand btn-brand-secondary" style="padding:4px 10px;font-size:0.75rem;border-radius:6px;" onclick="window.__selectReturnedFee(\'', r.fee_id_PK, '\')">Edit</button>',
        '</td>',
      ].join("");
      tbody.appendChild(tr);
    });
  }

  function fillEditForm(record) {
    const sel = getEl(SELECT_RECORD_ID);
    if (sel) sel.value = record.fee_id_PK;

    const setVal = (id, v) => {
      const el = getEl(id);
      if (el) el.value = v ?? "";
    };

    setVal(INPUT_FEE_AMOUNT, record.amount || "");
    setVal(INPUT_PARTIAL_AMOUNT, record.partial_amount || "");
    setVal(INPUT_PAYMENT_METHOD, record.payment_method || "");
    setVal(INPUT_PAYMENT_STATUS, record.payment_status || "Full Payment");
    setVal(INPUT_PAYMENT_DATE, record.payment_date || "");
    setVal(INPUT_RECEIPT_NUMBER, record.receipt_number || "");
    setVal(INPUT_DEPOSIT_REFERENCE, record.deposit_reference || "");

    const rej = document.getElementById("rejection_reason_display");
    if (rej) rej.textContent = cleanRejectionReason(record.rejection_reason) || "No rejection reason on file.";

    const container = document.getElementById("rejection_details_container");
    if (container) {
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

    const slot = document.querySelector(".photo-upload-slot");
    const existingIndicator = document.getElementById("re_fee_preview");
    if (slot && existingIndicator) {
      if (record.proof_url) {
        existingIndicator.innerHTML = `
          <img src="${record.proof_url}" style="max-height:140px;border-radius:8px;margin-top:8px;border:1px solid #cfdccc;" />
          <div style="font-size:0.8rem;color:#757575;margin-top:4px;">Existing attachment on record</div>
        `;
        existingIndicator.style.display = "block";
      } else {
        existingIndicator.innerHTML = "✓ Receipt Document Attached!";
        existingIndicator.style.display = "none";
      }
    }

    FileQueue.clear("re_fee");

    const thumbnailContainer = document.getElementById("re_fee_thumbnail_container");
    const thumbnailImg = document.getElementById("re_fee_thumbnail");
    const thumbnailLink = document.getElementById("re_fee_thumbnail_link");
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

    syncStatusMode();
  }

  function clearEditForm() {
    FileQueue.clear("re_fee");
    const sel = getEl(SELECT_RECORD_ID);
    if (sel) sel.value = "";
    syncStatusMode();
    const rej = document.getElementById("rejection_reason_display");
    if (rej) rej.textContent = "Select a record to view rejection reason";
    const container = document.getElementById("rejection_details_container");
    if (container) {
      container.innerHTML = "";
      container.style.display = "none";
    }
  }

  async function submitCorrection(e) {
    e.preventDefault();
    if (isSubmitting) return;

    const recordId = getEl(SELECT_RECORD_ID)?.value;
    if (!recordId) {
      showToast("Select a returned entry to edit.", true);
      return;
    }

    const status = getEl(STATUS_SELECT_ID)?.value;
    const fee_date = getEl(INPUT_PAYMENT_DATE)?.value;
    const fee_ref = getEl(INPUT_RECEIPT_NUMBER)?.value;
    const fee_encoder = getEl(INPUT_DEPOSIT_REFERENCE)?.value;
    const fee_method = getEl(INPUT_PAYMENT_METHOD)?.value;

    if (!fee_date) {
      showToast("Payment date is required.", true);
      return;
    }
    if (!fee_ref) {
      showToast("Receipt/Reference number is required.", true);
      return;
    }
    if (!fee_method) {
      showToast("Payment method is required.", true);
      return;
    }

    const partialAmount = getEl(INPUT_PARTIAL_AMOUNT)?.value;
    const fullAmount = getEl(INPUT_FEE_AMOUNT)?.value;
    const isPartial = status === "Partial";

    if (isPartial && !partialAmount) {
      showToast("Partial amount is required when status is Partial.", true);
      return;
    }
    if (!isPartial && !fullAmount) {
      showToast("Amount paid is required.", true);
      return;
    }

    const form = getEl(FORM_ID);
    if (!form) return;

    const fd = new FormData();
    fd.append("fee_status", status);
    fd.append("fee_date", fee_date);
    fd.append("fee_ref", fee_ref);
    fd.append("fee_encoder", fee_encoder);
    fd.append("fee_method", fee_method);

    if (isPartial) {
      fd.append("fee_amount", partialAmount);
      fd.append("fee_partial_amount", partialAmount);
    } else {
      fd.append("fee_amount", fullAmount);
      fd.append("fee_partial_amount", "");
    }

    const mfSameAuditor = document.getElementById("mf_same_auditor");
    fd.append("same_auditor", mfSameAuditor ? mfSameAuditor.checked : false);

    // Attach photo file if selected
    var reFeeFiles = FileQueue.getFiles("re_fee");
    if (reFeeFiles.length > 0) fd.append("fee_photo_file", reFeeFiles[0]);

    try {
      isSubmitting = true;
      const csrf = getCSRFToken();
      const resp = await fetch(
        `/api/treasurer/resubmit/membership_fee/${recordId}/`,
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

      showToast("Returned entry updated and resubmitted.");

      // refresh list
      const records = await fetchReturnedMembershipFees();
      window.__renderReturnedFeeList(records);
      isSubmitting = false;
      clearEditForm();
    } catch (err) {
      isSubmitting = false;
      showToast("Network/server error while submitting correction.", true);
    }
  }

  function wireUp() {
    FileQueue.init("re_fee", { inputId: "re_fee_file_input", containerId: "re_fee_file_queue", maxFiles: 1 });

    const statusSel = getEl(STATUS_SELECT_ID);
    if (statusSel) {
      statusSel.addEventListener("change", syncStatusMode);
    }

    const form = getEl(FORM_ID);
    if (form) {
      form.addEventListener("submit", submitCorrection);
    }

    window.__selectReturnedFee = function (feeId) {
      const rec = window.__returnedFeeRecords?.find(
        (r) => String(r.fee_id_PK) === String(feeId),
      );
      if (!rec) return;
      fillEditForm(rec);
    };

    window.__renderReturnedFeeList = function (records) {
      renderReturnedRecords(records);
      window.__returnedFeeRecords = records;
    };

    window.__refreshReturnedEntries = async function () {
      try {
        const records = await fetchReturnedMembershipFees();
        window.__renderReturnedFeeList(records);
      } catch (e) {
        console.error(e);
      }
    };
  }

  async function init() {
    wireUp();
    syncStatusMode();

    try {
      const records = await fetchReturnedMembershipFees();
      window.__renderReturnedFeeList(records);
    } catch (e) {
      console.error(e);
      renderReturnedRecords([]);
      window.__returnedFeeRecords = [];
      clearEditForm();
    }
  }

  window.addEventListener("turbo:load", init);
})();
