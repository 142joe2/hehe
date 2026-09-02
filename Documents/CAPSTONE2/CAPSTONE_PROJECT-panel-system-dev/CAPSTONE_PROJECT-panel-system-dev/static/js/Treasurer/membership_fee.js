(function () {
  "use strict";

  const FORM_ID = "feePaymentForm";
  const SELECT_MEMBER_ID = "fee_member";
  const TABLE_BODY_ID = "feePaymentTable";
  const STATUS_SELECT_ID = "fee_status";
  const FULL_AMOUNT_GROUP_ID = "fullAmountGroup";
  const PARTIAL_AMOUNT_GROUP_ID = "partialAmountGroup";
  const AMOUNT_INPUT_ID = "fee_amount";
  const PARTIAL_AMOUNT_INPUT_ID = "fee_partial_amount";
  const CSRF_HEADER_NAME = "X-CSRFToken";
  let isSubmitting = false;

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function getInputValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : "";
  }

  function padMonth(month) {
    return String(month).padStart(2, "0");
  }

  function formatMonthFromDate(date) {
    if (!date || Number.isNaN(date.getTime())) return "";
    return `${date.getFullYear()}-${padMonth(date.getMonth() + 1)}`;
  }

  function normalizeCoveredMonth(value) {
    const trimmed = String(value || "").trim();
    const dateMatch = trimmed.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
    if (dateMatch) {
      const month = Number(dateMatch[2]);
      if (month >= 1 && month <= 12) {
        return `${dateMatch[1]}-${padMonth(month)}`;
      }
    }

    const monthMatch = trimmed.match(/^(\d{4})[-/](\d{1,2})$/);
    if (monthMatch) {
      const month = Number(monthMatch[2]);
      if (month >= 1 && month <= 12) {
        return `${monthMatch[1]}-${padMonth(month)}`;
      }
    }

    const monthFirstMatch = trimmed.match(/^(\d{1,2})[-/](\d{4})$/);
    if (monthFirstMatch) {
      const month = Number(monthFirstMatch[1]);
      if (month >= 1 && month <= 12) {
        return `${monthFirstMatch[2]}-${padMonth(month)}`;
      }
    }

    const mdyMatch = trimmed.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    if (mdyMatch) {
      const first = Number(mdyMatch[1]);
      const second = Number(mdyMatch[2]);
      const month = first >= 1 && first <= 12 ? first : second;
      if (month >= 1 && month <= 12) {
        return `${mdyMatch[3]}-${padMonth(month)}`;
      }
    }

    const monthNameMap = {
      january: 1,
      february: 2,
      march: 3,
      april: 4,
      may: 5,
      june: 6,
      july: 7,
      august: 8,
      september: 9,
      october: 10,
      november: 11,
      december: 12,
      jan: 1,
      feb: 2,
      mar: 3,
      apr: 4,
      jun: 6,
      jul: 7,
      aug: 8,
      sep: 9,
      sept: 9,
      oct: 10,
      nov: 11,
      dec: 12,
    };
    const namedMonthMatch = trimmed.match(/^([A-Za-z]+)\s*,?\s*(\d{4})$/);
    if (namedMonthMatch) {
      const month = monthNameMap[namedMonthMatch[1].toLowerCase()];
      if (month) {
        return `${namedMonthMatch[2]}-${padMonth(month)}`;
      }
    }

    const parsed = new Date(trimmed);
    if (!Number.isNaN(parsed.getTime())) {
      return formatMonthFromDate(parsed);
    }

    return trimmed;
  }

  function getCoveredMonthValue() {
    const input = document.getElementById("fee_month");
    if (!input) return "";

    const rawValue = input.value || input.getAttribute("value") || "";
    const parsedFromValue = normalizeCoveredMonth(rawValue);
    if (/^\d{4}-(0[1-9]|1[0-2])$/.test(parsedFromValue)) {
      input.dataset.coveredMonth = parsedFromValue;
      return parsedFromValue;
    }

    const parsedFromDate = formatMonthFromDate(input.valueAsDate);
    if (parsedFromDate) {
      input.dataset.coveredMonth = parsedFromDate;
      return parsedFromDate;
    }

    return input.dataset.coveredMonth || "";
  }

  function setCoveredMonthInputValue(input, value) {
    if (input.type === "month") {
      input.value = value;
      return;
    }

    input.setAttribute("value", value);
  }

  function attachCoveredMonthHandler() {
    const input = document.getElementById("fee_month");
    if (!input) return;

    ["input", "change", "blur"].forEach((eventName) => {
      input.addEventListener(eventName, () => {
        const parsed = normalizeCoveredMonth(
          input.value || input.getAttribute("value") || "",
        );
        if (/^\d{4}-(0[1-9]|1[0-2])$/.test(parsed)) {
          input.dataset.coveredMonth = parsed;
          setCoveredMonthInputValue(input, parsed);
        }
      });
    });
  }

  function moneyToPHP(num) {
    const n = typeof num === "number" ? num : parseFloat(num || "0");
    return new Intl.NumberFormat("en-PH", {
      style: "currency",
      currency: "PHP",
    }).format(n);
  }

function getMemberOptionLabel(m) {
    return `${m.full_name}`;
}

  async function fetchMembers() {
    const resp = await fetch("/api/treasurer/members/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Failed to load members.");
    }
    return data.members || [];
  }

  function renderMembersDropdown(members) {
    const sel = document.getElementById(SELECT_MEMBER_ID);
    if (!sel) return;

    sel.innerHTML = "";
    sel.innerHTML = '<option value="">Select Associated Member</option>';

    members.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.member_id;
      opt.textContent = getMemberOptionLabel(m);
      sel.appendChild(opt);
    });
  }

  async function fetchMembershipFees() {
    const resp = await fetch("/api/treasurer/membership-fees/list/", {
      method: "GET",
      credentials: "same-origin",
    });

    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      throw new Error(
        (data && data.error) || "Failed to load membership fees.",
      );
    }
    return data.fees || [];
  }

  function renderFeeTableRows(fees) {
    const tbody = document.querySelector(`#${TABLE_BODY_ID} tbody`);
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!fees || fees.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#757575;">No membership fee payments recorded</td></tr>';
      return;
    }

    fees.forEach((f) => {
      const tr = document.createElement("tr");
      const statusLabel = f.payment_status || "";
      const methodLabel = f.payment_method ? ` (${f.payment_method})` : "";
      tr.innerHTML = `
        <td style="font-weight:600;color:#1b5e20;">${f.ref || ""}</td>
        <td>${f.member_name || ""} <br><span style="font-size:0.75rem;color:#757575;">Code: ${f.member_id || ""}</span></td>
        <td style="font-weight:600;">${moneyToPHP(f.amount)}</td>
        <td>${statusLabel}${methodLabel} <br><span style="font-size:0.75rem;color:#757575;">Date: ${f.payment_date || ""}</span></td>
        <td>${f.encoded_by || ""}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function syncFeeStatusMode() {
    const statusSelect = document.getElementById(STATUS_SELECT_ID);
    const fullGroup = document.getElementById(FULL_AMOUNT_GROUP_ID);
    const partialGroup = document.getElementById(PARTIAL_AMOUNT_GROUP_ID);
    const amountInput = document.getElementById(AMOUNT_INPUT_ID);
    const partialInput = document.getElementById(PARTIAL_AMOUNT_INPUT_ID);

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

  async function handleMembershipFeeApiSubmit(e) {
    console.log("[membership_fee] submit handler fired");
    e.preventDefault();

    const form = document.getElementById(FORM_ID);
    if (!form) {
      console.error("[membership_fee] form not found");
      return;
    }

    const fee_member = getInputValue("fee_member");
    const fee_status = getInputValue("fee_status");
    const fee_method = getInputValue("fee_method");
    const fee_date = getInputValue("fee_date");
    const fee_month = getCoveredMonthValue();
    const fee_ref = getInputValue("fee_ref");
    const fee_encoder = getInputValue("fee_encoder");

    if (!fee_member)
      return showToast("Associated Member ID is required.", true);
    if (!fee_date) return showToast("Payment Date is required.", true);
    if (!fee_month)
      return showToast("Deduction Month / Covered Period is required.", true);
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(fee_month))
      return showToast(
        "Deduction Month / Covered Period must use YYYY-MM.",
        true,
      );
    if (!fee_ref)
      return showToast("Receipt / Reference Number is required.", true);

    const partialAmount = getInputValue(PARTIAL_AMOUNT_INPUT_ID);
    const isPartial = fee_status === "Partial";

    if (isPartial) {
      if (!partialAmount)
        return showToast(
          "Partial Payment Amount is required when status is Partial.",
          true,
        );
    }

    const fd = new FormData(form);
    fd.set("fee_member", fee_member);
    fd.set("fee_status", fee_status);
    fd.set("fee_method", fee_method);
    if (isPartial && partialAmount) {
      fd.set("fee_amount", partialAmount);
    } else {
      const fee_amount = getInputValue(AMOUNT_INPUT_ID);
      if (!fee_amount) return showToast("Amount Paid is required.", true);
      fd.set("fee_amount", fee_amount);
    }
    fd.set("fee_date", fee_date);
    fd.set("fee_month", fee_month);
    fd.set("fee_ref", fee_ref);
    fd.set("fee_encoder", fee_encoder);
    var feeFiles = FileQueue.getFiles("fee");
    if (feeFiles.length > 0) fd.set("fee_photo_file", feeFiles[0]);

    const csrf = getCSRFToken();

    const submitBtn = form.querySelector("button[type='submit']");
    let originalBtnHTML = "";
    if (submitBtn) {
      originalBtnHTML = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing...';
    }

    try {
      if (isSubmitting) return;
      isSubmitting = true;
      const resp = await fetch("/api/treasurer/membership-fees/add/", {
        method: "POST",
        body: fd,
        headers: csrf ? { [CSRF_HEADER_NAME]: csrf } : {},
        credentials: "same-origin",
      });

      const data = await resp.json().catch(() => ({}));

      if (!resp.ok || !data.ok) {
        isSubmitting = false;
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHTML;
        }
        return showToast(
          (data && data.error) || "Failed to log membership fee entry.",
          true,
        );
      }

      form.reset();
      FileQueue.clear("fee");
      syncFeeStatusMode();
      const preview = document.getElementById("fee_preview");
      if (preview) preview.style.display = "none";

      const fees = await fetchMembershipFees();
      renderFeeTableRows(fees);

      // Trigger global component rendering to update KPI cards and other tables
      if (typeof window.renderAllComponents === "function") {
        window.renderAllComponents();
      } else if (typeof renderAllComponents === "function") {
        renderAllComponents();
      }

      isSubmitting = false;
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnHTML;
      }

      Swal.fire({
        title: "Fee Recorded",
        text: "Membership fee payment has been successfully recorded and logged.",
        icon: "success",
        confirmButtonColor: "#1b5e20"
      });
    } catch (err) {
      isSubmitting = false;
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnHTML;
      }
      showToast("Network/server error while logging membership fee.", true);
    }
  }

  function init() {
    FileQueue.init("fee", { inputId: "fee_file_input", containerId: "fee_file_queue", maxFiles: 1 });

    attachCoveredMonthHandler();

    const statusSelect = document.getElementById(STATUS_SELECT_ID);
    if (statusSelect) {
      statusSelect.addEventListener("change", syncFeeStatusMode);
      syncFeeStatusMode();
    }

    const form = document.getElementById(FORM_ID);
    if (form) {
      form.addEventListener("submit", handleMembershipFeeApiSubmit);
    }

    const memberSelect = document.getElementById(SELECT_MEMBER_ID);
    if (memberSelect) {
      memberSelect.addEventListener("change", function () {
        if (this.value === "__add_option__") {
          this.value = "";
          const enrollSection = document.getElementById("view-member-profile");
          if (enrollSection) {
            enrollSection.classList.add("active");
          }
          const feeSection = document.getElementById("view-fee-payment");
          if (feeSection) {
            feeSection.classList.remove("active");
          }
        }
      });
    }

    (async function load() {
      try {
        const members = await fetchMembers();
        renderMembersDropdown(members);

        const fees = await fetchMembershipFees();
        renderFeeTableRows(fees);
      } catch (e) {
        console.error(e);
      }
    })();
  }

  document.addEventListener("turbo:load", init);
})();
