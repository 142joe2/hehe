(function () {
  "use strict";

  const CSRF_HEADER_NAME = "X-CSRFToken";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function formatMoneyPHP(num) {
    const n = typeof num === "number" ? num : parseFloat(num || "0");
    return new Intl.NumberFormat("en-PH", {
      style: "currency",
      currency: "PHP",
    }).format(n);
  }

  function postForm(url, fd) {
    const csrf = getCSRFToken();
    const headers = {};
    if (csrf) {
      headers[CSRF_HEADER_NAME] = csrf;
    }
    return fetch(url, {
      method: "POST",
      body: fd,
      headers: headers,
      credentials: "same-origin",
    })
      .then(function (resp) {
        return resp.json().catch(function () {
          return {};
        });
      })
      .then(function (data) {
        // Return data even if not ok, so caller can handle errors properly
        return data;
      });
  }

  var MEDICAL_AID_FIELDS = [
    {
      key: "aid_type",
      label: "Claim Type",
      icon: "",
      value: function (item) {
        return item.aid_type || item.type || "Medical Aid";
      },
    },
    {
      key: "request_date",
      label: "Request Date",
      icon: "",
      value: function (item) {
        return item.request_date || item.date || "—";
      },
    },
    {
      key: "medical_case",
      label: "Reason / Medical Case",
      icon: "",
      value: function (item) {
        return item.medical_case || item.reason || "—";
      },
    },
    {
      key: "validated_aid_amount",
      label: "Assigned Contribution Amount",
      icon: "",
      value: function (item) {
        return (
          formatMoneyPHP(
            item.assigned_amount ||
              item.validated_aid_amount ||
              item.reqAmount ||
              item.requested_amount ||
              0,
          ) + " /per member"
        );
      },
    },
    {
      key: "hospital",
      label: "Hospital / Clinic Name",
      icon: "",
      value: function (item) {
        if (item.hospital) return item.hospital;
        if (
          item.member &&
          item.member.member_name &&
          item.hospital === undefined
        ) {
          return item.member.member_name;
        }
        return item.hospital || "\u2014";
      },
    },
    {
      key: "hospital_date",
      label: "Date range of Admission to Discharge",
      icon: "",
      value: function (item) {
        const a = item.admission_date;
        const d = item.discharge_date;
        if (a && d) return a + " → " + d;
        if (a) return a + " → ?";
        if (d) return "? → " + d;
        return item.hospital_date || "\u2014";
      },
    },
    {
      key: "total_hospital_bill",
      label: "Total Hospital Bill",
      icon: "",
      value: function (item) {
        return formatMoneyPHP(item.total_hospital_bill || item.bill || 0);
      },
    },
  ];

  var DEATH_AID_FIELDS = [
    {
      key: "aid_type",
      label: "Claim Type",
      icon: "",
      value: function (item) {
        return item.aid_type || item.type || "Death Aid";
      },
    },
    {
      key: "claim_date",
      label: "Claim Submission Date",
      icon: "",
      value: function (item) {
        return item.claim_date || item.date || "—";
      },
    },
    {
      key: "claim_type",
      label: "Death Claim Type Category",
      icon: "",
      value: function (item) {
        var g = String(item.relationshipGroup || "").toLowerCase();
        var catMap = {
          member: "Member",
          spouse: "Spouse",
          parent_child: "Parent/Child",
          sibling: "Full-Blood / Half Sibling",
        };
        return (
          catMap[g] ||
          item.claim_type ||
          item.claimType ||
          "—"
        );
      },
    },
    {
      key: "deceased_name",
      label: "Deceased Person's Name",
      icon: "",
      value: function (item) {
        return item.deceased_name || item.deceased || "—";
      },
    },
    {
      key: "relationship",
      label: "Relationship to Member",
      icon: "",
      value: function (item) {
        return item.relationship || "—";
      },
    },
    {
      key: "claimant_name",
      label: "Claimant Legal Name",
      icon: "",
      value: function (item) {
        return item.claimant_name || item.claimantName || "—";
      },
    },
    {
      key: "claimant_contact",
      label: "Claimant Contact Info",
      icon: "",
      value: function (item) {
        return (
          item.claimant_contact ||
          item.claimantContact ||
          (item.member && item.member.contact) ||
          "—"
        );
      },
    },
    {
      key: "bill_amount",
      label: "Total Bill Amount",
      icon: "",
      value: function (item) {
        return formatMoneyPHP(item.bill_amount || 0);
      },
    },
    {
      key: "benefit_amount",
      label: "Assigned Contribution Amount",
      icon: "",
      value: function (item) {
        return (
          formatMoneyPHP(
            item.assigned_amount ||
              item.benefit_amount ||
              item.benefit ||
              0,
          ) + " /per member"
        );
      },
    },
    {
      key: "date_of_death",
      label: "Official Date of Death",
      icon: "",
      value: function (item) {
        return item.date_of_death || item.dateOfDeath || item.date || "—";
      },
    },
  ];

  var AID_REQUIRED_FIELDS = {
    medical_aid: [
      "request_date",
      "medical_case",
      "hospital",
      "total_hospital_bill",
    ],
    death_aid: [
      "deceased_name",
      "date_of_death",
      "claimant_name",
      "claim_type",
    ],
  };

  function detectAidType(item) {
    var isMedical =
      item.aid_type === "Medical Aid Request" ||
      item.aid_type === "medical_aid" ||
      item.type === "Medical Aid Request" ||
      !!item.reqAmount ||
      !!item.requested_amount ||
      !!item.hospital ||
      !!item.medical_case ||
      !!item.bill;
    if (isMedical) return "medical_aid";
    return "death_aid";
  }

  function buildAidDataContainer() {
    var fieldsContainerId = "aidInspectionFields";
    var existing = getEl(fieldsContainerId);
    if (existing) return existing;

    var container = document.createElement("div");
    container.id = fieldsContainerId;
    container.style.display = "block";
    container.className = "inspection-data-block";

    var title = document.createElement("div");
    title.className = "inspection-data-title";
    title.id = "aidInspectionTitle";
    title.innerText = "Claim Inspection";

    var grid = document.createElement("div");
    grid.className = "readonly-grid";
    grid.id = "aidInspectionGrid";

    container.appendChild(title);
    container.appendChild(grid);
    return container;
  }

  function renderAidInspectionFields(item, screenId) {
    var aidType = detectAidType(item);
    var fields =
      aidType === "medical_aid" ? MEDICAL_AID_FIELDS : DEATH_AID_FIELDS;
    var requiredFields =
      AID_REQUIRED_FIELDS[aidType] ||
      DEATH_AID_FIELDS.map(function (f) {
        return f.key;
      });

    if (!item._aidTypeForUI) item._aidTypeForUI = aidType;

    var aidHeader = getEl("aidInspectionTypeLabel");
    if (aidHeader) {
      aidHeader.innerText =
        aidType === "medical_aid" ? "Medical Aid" : "Death Aid";
    }

    var title = getEl("aidInspectionTitle");
    if (title) {
      title.innerText =
        aidType === "medical_aid"
          ? "Medical Aid Request Details"
          : "Death Claim Details";
    }

    var fieldsContainer = buildAidDataContainer();
    var grid = getEl("aidInspectionGrid");
    if (!grid) return fieldsContainer;

    grid.innerHTML = "";

    fields.forEach(function (field) {
      var rawValue = field.value(item);
      var displayValue = rawValue;
      var isMissing = rawValue === "\u2014";
      if (!isMissing) {
        try {
          var suffix = "";
          var clean = rawValue;
          var parts = rawValue.split(" /per member");
          if (parts.length > 1) {
            clean = parts[0];
            suffix = " /per member";
          }
          var asNum = parseFloat(clean.replace(/[^0-9.\-]/g, ""));
          if (
            (field.key.indexOf("amount") !== -1 ||
              field.key.indexOf("bill") !== -1) &&
            !isNaN(asNum)
          ) {
            displayValue = formatMoneyPHP(asNum) + suffix;
          }
        } catch (e) {
          displayValue = rawValue;
        }
      }

      var fieldDiv = document.createElement("div");
      fieldDiv.className = "readonly-field";
      fieldDiv.setAttribute("data-field-key", field.key);
      fieldDiv.setAttribute("data-required", String(!!requiredFields));

      var isRequired = requiredFields.indexOf(field.key) !== -1;
      if (isMissing && isRequired) {
        fieldDiv.classList.add("missing-data");
      }

      var labelEl = document.createElement("label");
      labelEl.innerHTML = (field.icon || "") + " " + field.label;
      var valueEl = document.createElement("div");
      valueEl.innerText = displayValue;

      fieldDiv.appendChild(labelEl);
      fieldDiv.appendChild(valueEl);
      grid.appendChild(fieldDiv);
    });

    var missingSummary;
    var missingCount = 0;
    fields.forEach(function (field) {
      if (
        field.value(item) === "\u2014" &&
        requiredFields.indexOf(field.key) !== -1
      ) {
        missingCount++;
      }
    });

    if (missingCount > 0) {
      missingSummary = document.createElement("div");
      missingSummary.className = "missing-data-banner";
      missingSummary.style.cssText =
        "margin-top:8px;padding:8px 12px;border-radius:8px;background:rgba(229,57,53,0.08);border:1px solid rgba(229,57,53,0.25);font-size:0.78rem;color:#b71c1c;";
      missingSummary.innerHTML =
        "WARNING: " +
        missingCount +
        " required field" +
        (missingCount > 1 ? "s" : "") +
        " not provided. Review uploads in the Evidence Viewer below.";
      grid.parentNode.insertBefore(missingSummary, grid.nextSibling);
    }

    var evBlock = getEl("aidEvidenceScreen");
    if (evBlock && evBlock.parentNode) {
      var isAlone = evBlock.previousElementSibling === fieldsContainer;
      if (!isAlone && evBlock.parentNode.contains(fieldsContainer)) {
        container.insertBefore(evBlock, fieldsContainer.nextSibling);
      }
    }

    return fieldsContainer;
  }

  function clearAidInspectionUI() {
    var medBlock = getEl("inspectionMedicalBlock");
    var deathBlock = getEl("inspectionDeathBlock");
    if (medBlock) medBlock.style.display = "none";
    if (deathBlock) deathBlock.style.display = "none";

    var fieldsContainer = getEl("aidInspectionFields");
    if (fieldsContainer) {
      fieldsContainer.style.display = "none";
      var grid = getEl("aidInspectionGrid");
      if (grid) grid.innerHTML = "";
      removeBanner(fieldsContainer);
    }

    var header = getEl("aidInspectionTypeLabel");
    if (header) header.innerText = "";

    var title = getEl("aidInspectionTitle");
    if (title) title.innerText = "Claim Inspection";

    var aidHeader = getEl("selectedAidHeader");
    if (aidHeader) aidHeader.innerText = "No claim file selected";

    var evScreen = getEl("aidEvidenceScreen");
    if (evScreen && window.renderEmptyState) {
      window.renderEmptyState("aidEvidenceScreen");
    } else if (evScreen) {
      evScreen.style.borderColor = "";
    }

    var auditId = getEl("aAuditID");
    if (auditId) auditId.value = "";
    var auditType = getEl("aAuditType");
    if (auditType) auditType.value = "";
    var auditDate = getEl("aAuditDate");
    if (auditDate) auditDate.value = "";
    var form = getEl("aidVerificationForm");
    if (form) form.reset();

    var preview = getEl("a_findings_preview");
    if (preview) preview.style.display = "none";

    if (window.toggleAidAuditEvidenceRequirement) {
      window.toggleAidAuditEvidenceRequirement();
    }
  }

  function removeBanner(container) {
    if (!container) return;
    var banners = container.querySelectorAll(".missing-data-banner");
    banners.forEach(function (b) {
      b.remove();
    });
  }

  async function handleAidSubmit(e) {
    if (e) e.preventDefault();

    var auditTargetId = (getEl("aAuditID") || {}).value;
    if (!auditTargetId) {
      showToast(
        "Please select an active claim record from the inbox first.",
        true,
      );
      return false;
    }

    var auditResult = (getEl("aAuditResult") || {}).value || "";
    if (!auditResult) {
      showToast("Please select a verification result (Verified or Returned).", true);
      return false;
    }

    // Get the table name from the aid type if available
    var aidTypeField = getEl("aAuditType");
    var tableName = aidTypeField ? aidTypeField.value : "";
    
    var fd = new FormData();
    fd.append("aAuditID", auditTargetId);
    fd.append("aAuditRemarks", (getEl("aAuditRemarks") || {}).value || "");
    fd.append("aAuditResult", auditResult);
    
    // Add table_name for consistency with bulk verification
    if (tableName) {
      fd.append("table_name", tableName);
    }

    var fileInput = getEl("a_findings_file");
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
        clearAidInspectionUI();
        if (typeof window.refreshAll === "function") {
          await window.refreshAll();
        }
      } else {
        if (data.error && data.error.includes("already been acted upon")) {
          showToast("This record has already been verified. Refreshing the list...", true);
          if (typeof window.refreshAll === "function") {
            await window.refreshAll();
          }
          clearAidInspectionUI();
        } else {
          showToast(data.error || "Failed submitting aid audit.", true);
        }
      }
    } catch (err) {
      console.error("Verification error:", err);
      showToast(err.message || "Failed submitting aid audit.", true);
    }
    return false;
  }

  function bindAidPanelForms() {
    window.submitAidVerification = handleAidSubmit;

    var aidForm = getEl("aidVerificationForm");
    if (aidForm) {
      aidForm.onsubmit = handleAidSubmit;
      aidForm.addEventListener("submit", handleAidSubmit);
    }

    window.clearAidVerificationSelection = function () {
      clearAidInspectionUI();
    };

    var aidBtn = getEl("btnReturnAidForCorrection");
    if (aidBtn) {
      aidBtn.addEventListener("click", function () {
        if (aidBtn.dataset.submitting === "1") return;
        aidBtn.dataset.submitting = "1";
        aidBtn.disabled = true;

        var resultSelect = getEl("aAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        if (window.toggleAidAuditEvidenceRequirement) {
          window.toggleAidAuditEvidenceRequirement();
        }
        var form = getEl("aidVerificationForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }
  }

  window.renderAidInspectionFields = renderAidInspectionFields;
  window.clearAidInspectionUI = clearAidInspectionUI;
  window.detectAidType = detectAidType;
  window.handleAidSubmit = handleAidSubmit;
  window.bindAidPanelForms = bindAidPanelForms;

  document.addEventListener("turbo:load", function () {
    var fieldsContainer = getEl("aidInspectionFields");
    if (fieldsContainer && !getEl("aidInspectionGrid")) {
      var grid = buildAidDataContainer().querySelector("#aidInspectionGrid");
      if (grid && grid.parentNode !== fieldsContainer) {
        fieldsContainer.appendChild(grid.parentNode || grid);
      }
    }
  });
})();
