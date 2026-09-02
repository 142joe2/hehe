(function () {
  "use strict";

  const MENU_TARGET_ID = "view-medical-aid-returned";

  const FORM_ID = "medicalAidReturnedEditForm";
  const SELECT_RECORD_ID = "medical_aid_returned_record_id";

  const INPUT_REQUEST_DATE = "ma_returned_request_date";
  const INPUT_REQUESTED_AMOUNT = "ma_returned_requested_amount";
  const INPUT_HOSPITAL_NAME = "ma_returned_hospital";
  const INPUT_HOSPITAL_DATE = "ma_returned_hospital_date";
  const INPUT_HOSPITAL_BILL = "ma_returned_hospital_bill";
  const INPUT_CLAIM_YEAR = "ma_returned_claim_year";
  const INPUT_DOCUMENT_STATUS = "ma_returned_document_status";
  const INPUT_STATUS = "ma_returned_status";
  const INPUT_VALIDATED_AMOUNT = "ma_returned_validated_amount";

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

  async function fetchReturnedMedicalAids() {
    const resp = await fetch("/api/treasurer/medical-aid/returned/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json();
    if (!resp.ok || !data || !data.ok)
      throw new Error(
        (data && data.error) || "Failed to load returned medical aid entries.",
      );
    return data.records || [];
  }

  function renderReturnedRecords(records) {
    const tbody = document.querySelector("#medicalAidReturnedTable tbody");
    if (!tbody) return;

    tbody.innerHTML = "";
    if (!records || records.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" style="text-align:center;color:#757575;">No returned medical aid entries to correct</td></tr>';
      return;
    }

    records.forEach((r) => {
      const tr = document.createElement("tr");
      tr.dataset.recordId = String(r.record_id);
      tr.innerHTML = [
        '<td style="font-weight:600;color:#1b5e20;">',
        escapeHtml(r.display_id || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">',
        escapeHtml(r.request_date || ""),
        '</span></td>',
        '<td>',
        escapeHtml(r.member_name || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">Code: ',
        escapeHtml(r.member_id_PK || ""),
        '</span></td>',
        '<td style="font-weight:600;">',
        escapeHtml(r.requested_amount || "0"),
        '</td>',
        '<td>',
        escapeHtml(r.hospital_name || "—"),
        '<br><span style="font-size:0.75rem;color:#757575;">Admitted: ',
        escapeHtml(r.hospital_date || "—"),
        ' | Bill: ',
        escapeHtml(r.hospital_bill_amount || ""),
        '</span></td>',
        '<td>',
        escapeHtml(cleanRejectionReason(r.rejection_reason || "")) || "—",
        '</td>',
        '<td>',
        '<button type="button" class="btn-brand btn-brand-secondary" style="padding:4px 10px;font-size:0.75rem;border-radius:6px;" onclick="window.__selectReturnedMedicalAid(\'', r.record_id, '\')">Edit</button>',
        '</td>',
      ].join("");
      tbody.appendChild(tr);
    });
  }

  function initFlatpickrRange() {
    var el = getEl(INPUT_HOSPITAL_DATE);
    if (el && typeof flatpickr !== "undefined" && !el._flatpickr) {
      flatpickr(el, { mode: "range", dateFormat: "Y-m-d" });
    }
  }

  function fillEditForm(record) {
    FileQueue.clear("ma_ret");
    const sel = getEl(SELECT_RECORD_ID);
    if (sel) sel.value = record.record_id;

    const setVal = (id, v) => {
      const el = getEl(id);
      if (el) el.value = v ?? "";
    };

    setVal(INPUT_REQUEST_DATE, record.request_date || "");
    setVal(INPUT_REQUESTED_AMOUNT, record.requested_amount || "");
    setVal(INPUT_HOSPITAL_NAME, record.hospital_name || "");
    var fpEl = getEl(INPUT_HOSPITAL_DATE);
    if (fpEl && fpEl._flatpickr) {
      fpEl._flatpickr.setDate(record.hospital_date || "");
    } else {
      setVal(INPUT_HOSPITAL_DATE, record.hospital_date || "");
    }
    setVal(INPUT_HOSPITAL_BILL, record.hospital_bill_amount || "");
    setVal(INPUT_CLAIM_YEAR, record.claim_year || "");
    setVal(INPUT_DOCUMENT_STATUS, record.document_status || "");
    setVal(INPUT_STATUS, record.status || "");
    setVal(INPUT_VALIDATED_AMOUNT, record.validated_aid_amount || "");

    const rej = document.getElementById("ma_rejection_reason_display");
    if (rej) rej.textContent = cleanRejectionReason(record.rejection_reason) || "No rejection reason on file.";

    const container = document.getElementById("ma_rejection_details_container");
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

    const thumbnailContainer = document.getElementById("ma_returned_thumbnail_container");
    const thumbnailImg = document.getElementById("ma_returned_thumbnail");
    const thumbnailLink = document.getElementById("ma_returned_thumbnail_link");
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

    const indicator = document.getElementById("ma_returned_preview");
    if (indicator) {
      if (record.proof_url) {
        indicator.innerHTML = `
          <img src="${record.proof_url}" style="max-height:140px;border-radius:8px;margin-top:8px;border:1px solid #cfdccc;" />
          <div style="font-size:0.8rem;color:#757575;margin-top:4px;">Existing attachment on record</div>
        `;
        indicator.style.display = "block";
      } else {
        indicator.innerHTML = "Document Attached!";
        indicator.style.display = "none";
      }
    }
  }

  function clearEditForm() {
    FileQueue.clear("ma_ret");
    const sel = getEl(SELECT_RECORD_ID);
    if (sel) sel.value = "";
    const form = getEl(FORM_ID);
    if (form) form.reset();
    const fp = getEl(INPUT_HOSPITAL_DATE);
    if (fp && fp._flatpickr) fp._flatpickr.clear();
    const rej = document.getElementById("ma_rejection_reason_display");
    if (rej) rej.textContent = "Select a record to view rejection reason";
    const container = document.getElementById("ma_rejection_details_container");
    if (container) {
      container.innerHTML = "";
      container.style.display = "none";
    }
    const thumbContainer = document.getElementById("ma_returned_thumbnail_container");
    if (thumbContainer) thumbContainer.style.display = "none";
    const thumbImg = document.getElementById("ma_returned_thumbnail");
    if (thumbImg) thumbImg.src = "";
    const thumbLink = document.getElementById("ma_returned_thumbnail_link");
    if (thumbLink) thumbLink.href = "";
    const indicator = document.getElementById("ma_returned_preview");
    if (indicator) {
      indicator.innerHTML = "";
      indicator.style.display = "none";
    }
  }

  function updateReturnedDot(count) {
    const el = document.getElementById("medical-aid-returned-dot");
    if (!el) return;
    if (count > 0) {
      el.textContent = count;
      el.style.display = "inline-flex";
    } else {
      el.textContent = "";
      el.style.display = "none";
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

    const request_date = getEl(INPUT_REQUEST_DATE)?.value;
    const requested_amount = getEl(INPUT_REQUESTED_AMOUNT)?.value;
    const hospital_name = getEl(INPUT_HOSPITAL_NAME)?.value;
    const hospital_date = getEl(INPUT_HOSPITAL_DATE)?.value;
    const hospital_bill_amount = getEl(INPUT_HOSPITAL_BILL)?.value;
    const claim_year = getEl(INPUT_CLAIM_YEAR)?.value;
    const document_status = getEl(INPUT_DOCUMENT_STATUS)?.value;
    const status = getEl(INPUT_STATUS)?.value;
    const validated_aid_amount = getEl(INPUT_VALIDATED_AMOUNT)?.value;

    if (!request_date) {
      showToast("Request date is required.", true);
      return;
    }
    if (!requested_amount) {
      showToast("Requested amount is required.", true);
      return;
    }
    if (!hospital_bill_amount) {
      showToast("Hospital bill amount is required.", true);
      return;
    }

    const fd = new FormData();
    fd.append("request_date", request_date);
    fd.append("requested_amount", requested_amount);
    fd.append("hospital_name", hospital_name);
    fd.append("hospital_date", hospital_date);
    fd.append("hospital_bill_amount", hospital_bill_amount);
    fd.append("claim_year", claim_year);
    fd.append("document_status", document_status);
    fd.append("status", status);
    fd.append("validated_aid_amount", validated_aid_amount);

    const maSameAuditor = document.getElementById("ma_same_auditor");
    fd.append("same_auditor", maSameAuditor ? maSameAuditor.checked : false);

    var maRetFiles = FileQueue.getFiles("ma_ret");
    if (maRetFiles.length > 0) fd.append("ma_returned_photo_file", maRetFiles[0]);

    try {
      isSubmitting = true;
      const csrf = getCSRFToken();
      const resp = await fetch(
        `/api/treasurer/resubmit/medical_aid/${recordId}/`,
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

      showToast("Returned medical aid entry updated and resubmitted.");

      const records = await fetchReturnedMedicalAids();
      window.__renderReturnedMedicalAidList(records);
      isSubmitting = false;
      clearEditForm();
    } catch (err) {
      isSubmitting = false;
      showToast("Network/server error while submitting correction.", true);
    }
  }

  function wireUp() {
    initFlatpickrRange();
    FileQueue.init("ma_ret", { inputId: "ma_ret_file_input", containerId: "ma_ret_file_queue", maxFiles: 1 });

    const form = getEl(FORM_ID);
    if (form) {
      form.addEventListener("submit", submitCorrection);
    }

    window.__selectReturnedMedicalAid = function (recordId) {
      const rec = window.__returnedMedicalAidRecords?.find(
        (r) => String(r.record_id) === String(recordId),
      );
      if (!rec) return;
      fillEditForm(rec);
    };

    window.__renderReturnedMedicalAidList = function (records) {
      renderReturnedRecords(records);
      window.__returnedMedicalAidRecords = records;
      updateReturnedDot(records.length);
    };
  }

  async function init() {
    wireUp();

    try {
      const records = await fetchReturnedMedicalAids();
      window.__renderReturnedMedicalAidList(records);
    } catch (e) {
      console.error(e);
      renderReturnedRecords([]);
      window.__returnedMedicalAidRecords = [];
      clearEditForm();
    }
  }

  window.addEventListener("turbo:load", init);
})();
