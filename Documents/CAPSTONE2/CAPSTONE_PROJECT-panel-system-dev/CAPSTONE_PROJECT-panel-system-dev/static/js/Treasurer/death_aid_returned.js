(function () {
  "use strict";

  const MENU_TARGET_ID = "view-death-aid-returned";

  const FORM_ID = "deathAidReturnedEditForm";
  const SELECT_RECORD_ID = "death_aid_returned_record_id";

  const INPUT_CLAIM_DATE = "da_returned_claim_date";
  const INPUT_CLAIM_TYPE = "da_returned_claim_type";
  const INPUT_DECEASED_NAME = "da_returned_deceased";
  const INPUT_RELATIONSHIP = "da_returned_relationship";
  const INPUT_BENEFIT_AMOUNT = "da_returned_benefit_amount";
  const INPUT_BILL_AMOUNT = "da_returned_bill_amount";
  const INPUT_DOCUMENT_STATUS = "da_returned_document_status";
  const INPUT_STATUS = "da_returned_status";

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

  async function fetchReturnedDeathAids() {
    const resp = await fetch("/api/treasurer/death-aid/returned/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json();
    if (!resp.ok || !data || !data.ok)
      throw new Error(
        (data && data.error) || "Failed to load returned death aid entries.",
      );
    return data.records || [];
  }

  function renderReturnedRecords(records) {
    const tbody = document.querySelector("#deathAidReturnedTable tbody");
    if (!tbody) return;

    tbody.innerHTML = "";
    if (!records || records.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="8" style="text-align:center;color:#757575;">No returned death aid entries to correct</td></tr>';
      return;
    }

    records.forEach((r) => {
      const tr = document.createElement("tr");
      tr.dataset.recordId = String(r.record_id);
      tr.innerHTML = [
        '<td style="font-weight:600;color:#1b5e20;">',
        escapeHtml(r.display_id || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">',
        escapeHtml(r.claim_date || ""),
        '</span></td>',
        '<td>',
        escapeHtml(r.member_name || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">Code: ',
        escapeHtml(r.member_id_PK || ""),
        '</span></td>',
        '<td>',
        escapeHtml(r.deceased_name || "—"),
        '<br><span style="font-size:0.75rem;color:#757575;">',
        escapeHtml(r.relationship_to_member || ""),
        '</span></td>',
        '<td style="font-weight:600;">',
        escapeHtml(r.benefit_amount || "0"),
        '</td>',
        '<td>',
        escapeHtml(r.bill_amount || "—"),
        '</td>',
        '<td>',
        escapeHtml(r.claim_date || ""),
        '<br><span style="font-size:0.75rem;color:#757575;">',
        escapeHtml(r.claim_type || ""),
        '</span></td>',
        '<td>',
        escapeHtml(cleanRejectionReason(r.rejection_reason || "")) || "—",
        '</td>',
        '<td>',
        '<button type="button" class="btn-brand btn-brand-secondary" style="padding:4px 10px;font-size:0.75rem;border-radius:6px;" onclick="window.__selectReturnedDeathAid(\'', r.record_id, '\')">Edit</button>',
        '</td>',
      ].join("");
      tbody.appendChild(tr);
    });
  }

  function fillEditForm(record) {
    FileQueue.clear("da_ret");
    const sel = getEl(SELECT_RECORD_ID);
    if (sel) sel.value = record.record_id;

    const setVal = (id, v) => {
      const el = getEl(id);
      if (el) el.value = v ?? "";
    };

    setVal(INPUT_CLAIM_DATE, record.claim_date || "");
    setVal(INPUT_CLAIM_TYPE, record.claim_type || "");
    setVal(INPUT_DECEASED_NAME, record.deceased_name || "");
    setVal(INPUT_RELATIONSHIP, record.relationship_to_member || "");
    setVal(INPUT_BENEFIT_AMOUNT, record.benefit_amount || "");
    setVal(INPUT_BILL_AMOUNT, record.bill_amount || "");
    setVal(INPUT_DOCUMENT_STATUS, record.document_status || "");
    setVal(INPUT_STATUS, record.status || "");

    const rej = document.getElementById("da_rejection_reason_display");
    if (rej) rej.textContent = cleanRejectionReason(record.rejection_reason) || "No rejection reason on file.";

    const container = document.getElementById("da_rejection_details_container");
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

    const thumbnailContainer = document.getElementById("da_returned_thumbnail_container");
    const thumbnailImg = document.getElementById("da_returned_thumbnail");
    const thumbnailLink = document.getElementById("da_returned_thumbnail_link");
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

    const indicator = document.getElementById("da_returned_preview");
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
    FileQueue.clear("da_ret");
    const sel = getEl(SELECT_RECORD_ID);
    if (sel) sel.value = "";
    const form = getEl(FORM_ID);
    if (form) form.reset();
    const rej = document.getElementById("da_rejection_reason_display");
    if (rej) rej.textContent = "Select a record to view rejection reason";
    const container = document.getElementById("da_rejection_details_container");
    if (container) {
      container.innerHTML = "";
      container.style.display = "none";
    }
    const thumbContainer = document.getElementById("da_returned_thumbnail_container");
    if (thumbContainer) thumbContainer.style.display = "none";
    const thumbImg = document.getElementById("da_returned_thumbnail");
    if (thumbImg) thumbImg.src = "";
    const thumbLink = document.getElementById("da_returned_thumbnail_link");
    if (thumbLink) thumbLink.href = "";
    const indicator = document.getElementById("da_returned_preview");
    if (indicator) {
      indicator.innerHTML = "";
      indicator.style.display = "none";
    }
  }

  function updateReturnedDot(count) {
    const el = document.getElementById("death-aid-returned-dot");
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

    const claim_date = getEl(INPUT_CLAIM_DATE)?.value;
    const claim_type = getEl(INPUT_CLAIM_TYPE)?.value;
    const deceased_name = getEl(INPUT_DECEASED_NAME)?.value;
    const relationship_to_member = getEl(INPUT_RELATIONSHIP)?.value;
    const benefit_amount = getEl(INPUT_BENEFIT_AMOUNT)?.value;
    const document_status = getEl(INPUT_DOCUMENT_STATUS)?.value;
    const status = getEl(INPUT_STATUS)?.value;

    if (!claim_date) {
      showToast("Claim date is required.", true);
      return;
    }
    if (!benefit_amount) {
      showToast("Benefit amount is required.", true);
      return;
    }

    const fd = new FormData();
    fd.append("claim_date", claim_date);
    fd.append("claim_type", claim_type);
    fd.append("deceased_name", deceased_name);
    fd.append("relationship_to_member", relationship_to_member);
    fd.append("benefit_amount", benefit_amount);
    fd.append("document_status", document_status);
    fd.append("status", status);

    const daSameAuditor = document.getElementById("da_same_auditor");
    fd.append("same_auditor", daSameAuditor ? daSameAuditor.checked : false);

    var daRetFiles = FileQueue.getFiles("da_ret");
    if (daRetFiles.length > 0) fd.append("da_returned_photo_file", daRetFiles[0]);

    try {
      isSubmitting = true;
      const csrf = getCSRFToken();
      const resp = await fetch(
        `/api/treasurer/resubmit/death_aid/${recordId}/`,
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

      showToast("Returned death aid entry updated and resubmitted.");

      const records = await fetchReturnedDeathAids();
      window.__renderReturnedDeathAidList(records);
      isSubmitting = false;
      clearEditForm();
    } catch (err) {
      isSubmitting = false;
      showToast("Network/server error while submitting correction.", true);
    }
  }

  function wireUp() {
    FileQueue.init("da_ret", { inputId: "da_ret_file_input", containerId: "da_ret_file_queue", maxFiles: 1 });

    const form = getEl(FORM_ID);
    if (form) {
      form.addEventListener("submit", submitCorrection);
    }

    window.__selectReturnedDeathAid = function (recordId) {
      const rec = window.__returnedDeathAidRecords?.find(
        (r) => String(r.record_id) === String(recordId),
      );
      if (!rec) return;
      fillEditForm(rec);
    };

    window.__renderReturnedDeathAidList = function (records) {
      renderReturnedRecords(records);
      window.__returnedDeathAidRecords = records;
      updateReturnedDot(records.length);
    };
  }

  async function init() {
    wireUp();

    try {
      const records = await fetchReturnedDeathAids();
      window.__renderReturnedDeathAidList(records);
    } catch (e) {
      console.error(e);
      renderReturnedRecords([]);
      window.__returnedDeathAidRecords = [];
      clearEditForm();
    }
  }

  window.addEventListener("turbo:load", init);
})();
