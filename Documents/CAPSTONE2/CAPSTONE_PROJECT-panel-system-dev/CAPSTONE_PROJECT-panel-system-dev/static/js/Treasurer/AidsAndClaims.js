// AidsAndClaims.js - Handles Medical Aid and Death Aid request/claim submission

var medSearchActiveIndex = -1;

function escapeAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatPhone(num) {
  if (!num) return "";
  var cleaned = num.replace(/[^\d]/g, "");
  if (cleaned.length === 11) {
    return cleaned.replace(/(\d{4})(\d{3})(\d{4})/, "$1 $2 $3");
  }
  if (cleaned.length === 7) {
    return cleaned.replace(/(\d{3})(\d{4})/, "$1-$2");
  }
  var match = num.match(/^(\d{3,4})[\s-]?(\d{3})[\s-]?(\d{4})$/);
  if (match) return "(" + match[1] + ") " + match[2] + "-" + match[3];
  return num;
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

async function fetchJson(url, options = {}) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (err) {
    return { ok: false, error: "Network error: " + err.message };
  }
  if (!res.ok) {
    let body;
    try {
      body = await res.json();
    } catch {
      body = {};
    }
    return {
      ok: false,
      error: body.error || body.message || "HTTP " + res.status,
      status: res.status,
    };
  }
  try {
    return await res.json();
  } catch (err) {
    return { ok: false, error: "Invalid response from server." };
  }
}

async function apiAddMedicalAid(formData) {
  return fetchJson("/api/treasurer/medical-aid/add/", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: formData,
  });
}

async function apiListMedicalAids() {
  return fetchJson("/api/treasurer/medical-aids/list/", {
    credentials: "same-origin",
  });
}

async function apiAddMedicalAidBatch(formData) {
  return fetchJson("/api/treasurer/medical-aid/batch-add/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRFToken": getCookie("csrftoken") },
    body: formData,
  });
}

// ---------- Batch Medical Aid state ----------
var medMembers = [];
var MED_MAX_MEMBERS = 5;

// ---------------- Death Aid APIs (Claims) ----------------
async function apiAddDeathAid(formData) {
  return fetchJson("/api/treasurer/death-aid/add/", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: formData,
  });
}

async function apiListDeathAids() {
  return fetchJson("/api/treasurer/death-aids/list/", {
    credentials: "same-origin",
  });
}

function renderMedicalTableFromApi(medicalAids) {
  const tbody = document.querySelector("#medicalTable tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  if (!Array.isArray(medicalAids) || medicalAids.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="3" style="text-align:center;color:#757575;">No medical aid requests found</td></tr>';
    return;
  }

  medicalAids.forEach((m) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${m.name}</td>
      <td>${m.reason} <br><span style="font-size:0.75rem;color:#757575;">At: ${m.hospital} (Bill: ₱${m.bill})</span></td>
      <td style="font-weight:600;">${formatCurrencyPHP(m.reqAmount)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function formatCurrencyPHP(num) {
  const n = Number(num || 0);
  return new Intl.NumberFormat("en-PH", {
    style: "currency",
    currency: "PHP",
  }).format(n);
}

function toggleMedCardHospitalDrawer(idx) {
  var body = document.getElementById("medCardHospitalDrawer_" + idx);
  var chevron = document.getElementById("medCardHospitalChevron_" + idx);
  if (!body || !chevron) return;
  var isOpen = body.style.maxHeight && body.style.maxHeight !== "0px";
  if (isOpen) {
    body.style.maxHeight = "0px";
    chevron.style.transform = "rotate(0deg)";
  } else {
    body.style.maxHeight = body.scrollHeight + "px";
    chevron.style.transform = "rotate(90deg)";
  }
}

function populateMedMemberSelect() {
  var sel = document.getElementById("med_member");
  if (!sel) return;
  sel.innerHTML = '<option value="">Select Associated Member</option>';
  if (typeof db !== "undefined" && Array.isArray(db.members)) {
    for (var i = 0; i < db.members.length; i++) {
      var m = db.members[i];
      var opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.name + " (" + (m.facultyId || m.id) + ")";
      opt.setAttribute("data-contact", m.contact || "");
      opt.setAttribute("data-status", m.status || "");
      sel.appendChild(opt);
    }
  }
}

function filterMedMembers(query) {
  var sel = document.getElementById("med_member");
  var results = document.getElementById("med_member_results");
  if (!sel || !results) return;
  medSearchActiveIndex = -1;
  var q = query.trim();
  if (!q) {
    results.style.display = "none";
    sel.style.display = "";
    return;
  }
  sel.style.display = "none";
  var ql = q.toLowerCase();
  var html = "";
  var count = 0;
  var alreadyIds = {};
  for (var mi = 0; mi < medMembers.length; mi++)
    alreadyIds[medMembers[mi].id] = true;
  for (var i = 0; i < sel.options.length; i++) {
    var opt = sel.options[i];
    if (!opt.value) continue;
    if (opt.textContent.toLowerCase().includes(ql)) {
      var val = opt.value;
      var label = opt.textContent;
      var added = alreadyIds[val];
      html +=
        '<div class="med-result-row" data-value="' +
        val +
        '" style="display:flex;align-items:center;justify-content:space-between;padding:6px 12px;border-bottom:1px solid #f0f0f0;font-size:0.85rem;cursor:pointer;" onmouseover="this.style.background=\'#f5f5f5\'" onmouseout="this.style.background=\'\'">' +
        "<span>" +
        label +
        "</span>" +
        '<span class="med-pick-badge" onclick="event.stopPropagation();addMedMember(\'' +
        val +
        '\')" style="display:inline-flex;align-items:center;gap:4px;padding:4px 14px;background:' +
        (added
          ? "rgba(158,158,158,0.15);color:#757575;border:1px solid rgba(158,158,158,0.3)"
          : "rgba(76,175,80,0.15);color:#2e7d32;border:1px solid rgba(76,175,80,0.3)") +
        ';border-radius:20px;font-size:0.72rem;font-weight:600;cursor:pointer;">' +
        (added ? "Added" : "Add +") +
        "</span>" +
        "</div>";
      count++;
    }
  }
  if (count === 0) {
    html =
      '<div style="padding:8px 12px;color:#999;font-size:0.85rem;">No members found</div>';
  }
  results.innerHTML = html;
  results.style.display = "block";
}

function handleMedSearchKeydown(e) {
  var results = document.getElementById("med_member_results");
  if (!results || results.style.display !== "block") return;
  var items = results.querySelectorAll(".med-result-row");
  if (!items.length) {
    if (e.key === "Enter") {
      e.preventDefault();
    }
    return;
  }
  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      items[
        medSearchActiveIndex >= 0 ? medSearchActiveIndex : 0
      ].classList.remove("med-search-active");
      medSearchActiveIndex = Math.min(
        medSearchActiveIndex + 1,
        items.length - 1,
      );
      items[medSearchActiveIndex].classList.add("med-search-active");
      items[medSearchActiveIndex].scrollIntoView({ block: "nearest" });
      break;
    case "Tab":
      e.preventDefault();
      if (e.shiftKey) {
        items[
          medSearchActiveIndex >= 0 ? medSearchActiveIndex : 0
        ].classList.remove("med-search-active");
        medSearchActiveIndex = Math.max(medSearchActiveIndex - 1, 0);
      } else {
        items[
          medSearchActiveIndex >= 0 ? medSearchActiveIndex : 0
        ].classList.remove("med-search-active");
        medSearchActiveIndex = Math.min(
          medSearchActiveIndex + 1,
          items.length - 1,
        );
      }
      items[medSearchActiveIndex].classList.add("med-search-active");
      items[medSearchActiveIndex].scrollIntoView({ block: "nearest" });
      break;
    case "ArrowUp":
      e.preventDefault();
      items[
        medSearchActiveIndex >= 0 ? medSearchActiveIndex : 0
      ].classList.remove("med-search-active");
      medSearchActiveIndex = Math.max(medSearchActiveIndex - 1, 0);
      items[medSearchActiveIndex].classList.add("med-search-active");
      items[medSearchActiveIndex].scrollIntoView({ block: "nearest" });
      break;
    case "Enter":
      e.preventDefault();
      if (medSearchActiveIndex >= 0 && medSearchActiveIndex < items.length) {
        addMedMember(items[medSearchActiveIndex].getAttribute("data-value"));
      } else {
        var first = items[0];
        if (first) addMedMember(first.getAttribute("data-value"));
      }
      break;
    case "Escape":
      document.getElementById("med_member_search").blur();
      hideMedResults();
      break;
  }
}

function addMedMember(val) {
  if (medMembers.length >= MED_MAX_MEMBERS) {
    showToast("Maximum of " + MED_MAX_MEMBERS + " members per batch.", true);
    return;
  }
  for (var ci = 0; ci < medMembers.length; ci++) {
    if (medMembers[ci].id === val) {
      showToast("Member already added.", true);
      return;
    }
  }
  var sel = document.getElementById("med_member");
  if (!sel) return;
  var memberData = null;
  for (var mi = 0; mi < sel.options.length; mi++) {
    if (sel.options[mi].value === val) {
      var opt = sel.options[mi];
      memberData = {
        id: val,
        name: opt.textContent,
        contact: opt.getAttribute("data-contact") || "",
        status: opt.getAttribute("data-status") || "",
        date: "",
        reason: "",
        hospital: "",
        hospitalDate: "",
        bill: "",
        files: [],
      };
      break;
    }
  }
  if (!memberData) return;
  medMembers.push(memberData);
  var searchInput = document.getElementById("med_member_search");
  if (searchInput) searchInput.value = "";
  hideMedResults();
  renderMedCards();
  filterMedMembers("");
}

function removeMedMember(idx) {
  medMembers.splice(idx, 1);
  // Shift FileQueues so remaining card files keep their correct index
  var stash = {};
  for (var ri = idx; ri < medMembers.length + 1; ri++) {
    stash["med_" + (ri - 1)] = FileQueue.getFiles("med_" + ri).slice();
    FileQueue.clear("med_" + ri);
  }
  renderMedCards();
  for (var si = idx; si < medMembers.length; si++) {
    var saved = stash["med_" + si];
    if (saved && saved.length) FileQueue.pushFiles("med_" + si, saved);
  }
  filterMedMembers("");
}

function renderMedCards() {
  var container = document.getElementById("med_member_cards");
  var counter = document.getElementById("med_member_counter");
  if (!container) return;
  if (counter) counter.textContent = medMembers.length;
  var submitBtn = document.querySelector("#medicalForm button[type=submit]");
  if (submitBtn)
    submitBtn.textContent = "Submit All Requests (" + medMembers.length + ")";
  if (medMembers.length === 0) {
    container.innerHTML = "";
    return;
  }
  var html = "";
  for (var i = 0; i < medMembers.length; i++) {
    var m = medMembers[i];
    html +=
      '<div class="dashboard-panel" style="margin-bottom:14px;padding:14px;border-left:4px solid #2e7d32;" data-card-idx="' +
      i +
      '">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">' +
      '<strong style="color:#1b5e20;">' +
      m.name +
      "</strong>" +
      '<button type="button" onclick="removeMedMember(' +
      i +
      ')" style="background:none;border:none;font-size:1.3rem;cursor:pointer;color:#e53935;padding:0 4px;">&times;</button>' +
      "</div>" +
      '<div class="form-grid-2">' +
      '<div class="form-group"><label for="med_date_' +
      i +
      '">Request Date</label><input type="date" id="med_date_' +
      i +
      '" name="med_date_' +
      i +
      '" value="' +
      (m.date || "") +
      '" oninput="medMembers[' +
      i +
      '].date=this.value" required /></div>' +
      '<div class="form-group"><label for="med_reason_' +
      i +
      '">Reason for Hospitalization</label><input type="text" id="med_reason_' +
      i +
      '" name="med_reason_' +
      i +
      '" placeholder="Type here..." value="' +
      escapeAttr(m.reason || "") +
      '" oninput="medMembers[' +
      i +
      '].reason=this.value" required /></div>' +
      "</div>" +
      '<div class="dashboard-panel" style="margin:10px 0;padding:10px;">' +
      '<div onclick="toggleMedCardHospitalDrawer(' +
      i +
      ')" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none;">' +
      '<h4 style="margin:0;color:#1b5e20;font-size:0.9rem;">&#9656; Hospital Details <span style="font-weight:400;color:#757575;font-size:0.72rem;">(click to expand)</span></h4>' +
      '<span id="medCardHospitalChevron_' +
      i +
      '" style="color:#1b5e20;font-size:0.9rem;transition:transform 0.25s;">&#9656;</span>' +
      "</div>" +
      '<div id="medCardHospitalDrawer_' +
      i +
      '" style="max-height:0;overflow:hidden;transition:max-height 0.3s ease;">' +
      '<div style="padding-top:10px;">' +
      '<div class="form-group"><label for="med_hospital_' +
      i +
      '">Hospital</label><input type="text" id="med_hospital_' +
      i +
      '" name="med_hospital_' +
      i +
      '" placeholder="e.g., Cauayan District Hospital" value="' +
      escapeAttr(m.hospital || "") +
      '" oninput="medMembers[' +
      i +
      '].hospital=this.value" /></div>' +
      '<div class="form-group"><label for="med_hospital_date_' +
      i +
      '">Date of Hospitalization</label><input type="text" id="med_hospital_date_' +
      i +
      '" name="med_hospital_date_' +
      i +
      '" class="flatpickr-range" placeholder="Select admission and discharge dates" value="' +
      escapeAttr(m.hospitalDate || "") +
      '" oninput="medMembers[' +
      i +
      '].hospitalDate=this.value" /></div>' +
      "</div></div></div>" +
      '<div class="form-group">' +
      '<label for="med_bill_' +
      i +
      '">Total Hospital Bill Amount (₱)</label>' +
      '<input type="number" step="0.01" id="med_bill_' +
      i +
      '" name="med_bill_' +
      i +
      '" placeholder="20000 or above" value="' +
      (m.bill || "") +
      '" required oninput="medMembers[' +
      i +
      "].bill=this.value;updateMedCardBillIndicator(" +
      i +
      ')" />' +
      '<div id="med_bill_indicator_' +
      i +
      '" style="margin-top:4px;font-size:0.8rem;font-weight:600;"></div>' +
      "</div>" +
      '<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 12px;background:rgba(27,94,32,0.08);border-radius:8px;margin-bottom:8px;font-size:0.82rem;color:#1b5e20;">' +
      "<span>Aid Benefit:</span>" +
      '<span style="font-weight:700;" id="med_estimate_' +
      i +
      '" data-threshold="' +
      (document.getElementById("med_aid_estimate_data")
        ? document
            .getElementById("med_aid_estimate_data")
            .getAttribute("data-threshold")
        : "20000") +
      '">₱' +
      (document.getElementById("med_aid_estimate_data")
        ? document
            .getElementById("med_aid_estimate_data")
            .getAttribute("data-benefit")
        : "0") +
      " / member</span>" +
      "</div>" +
      '<div class="form-group">' +
      "<label>Supporting Documents(Accepts Photos and PDF)</label>" +
      '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">' +
      '<button type="button" onclick="document.getElementById(\'med_' +
      i +
      '_file_input\').click()" class="file-queue-btn">+ Upload File/Photo</button>' +
      '<input type="file" id="med_' +
      i +
      '_file_input" multiple accept="image/*,.pdf,.docx" style="display:none" onchange="FileQueue.handleInput(\'med_' +
      i +
      "')\" />" +
      '<div id="med_' +
      i +
      '_file_queue" class="file-queue"></div>' +
      "</div></div></div>";
  }
  container.innerHTML = html;
  // Initialize FileQueue for each card + attach flatpickr
  for (var fi = 0; fi < medMembers.length; fi++) {
    if (!FileQueue.getFiles("med_" + fi).length) {
      FileQueue.init("med_" + fi, {
        inputId: "med_" + fi + "_file_input",
        containerId: "med_" + fi + "_file_queue",
        maxFiles: 5,
        accept: "image/*,.pdf,.docx",
      });
    }
    var dp = document.getElementById("med_hospital_date_" + fi);
    if (dp && typeof flatpickr !== "undefined" && !dp._flatpickr) {
      flatpickr(dp, { mode: "range", dateFormat: "Y-m-d" });
    }
  }
}

function updateMedCardBillIndicator(idx) {
  var billInput = document.getElementById("med_bill_" + idx);
  var indicator = document.getElementById("med_bill_indicator_" + idx);
  if (!billInput || !indicator) return;
  var val = parseFloat(billInput.value);
  var estimateEl = document.getElementById("med_estimate_" + idx);
  var threshold = parseFloat(
    estimateEl ? estimateEl.getAttribute("data-threshold") : "20000",
  );
  if (!val || isNaN(val)) {
    indicator.innerHTML = "";
    return;
  }
  if (val > threshold) {
    indicator.innerHTML =
      '<span style="color:#2e7d32;">&#10003; Bill meets the minimum threshold (₱' +
      threshold.toFixed(2) +
      ")</span>";
  } else {
    indicator.innerHTML =
      '<span style="color:#c62828;">&#9888; Bill must exceed ₱' +
      threshold.toFixed(2) +
      " to qualify</span>";
  }
}

function hideMedResults() {
  medSearchActiveIndex = -1;
  var results = document.getElementById("med_member_results");
  var sel = document.getElementById("med_member");
  var searchInput = document.getElementById("med_member_search");
  if (results) results.style.display = "none";
  if (sel) sel.style.display = "";
}

function onMedMemberSelect(sel) {
  var searchInput = document.getElementById("med_member_search");
  if (searchInput && sel.selectedIndex > -1 && sel.value) {
    searchInput.value = sel.options[sel.selectedIndex].textContent;
  }
}

async function bootMedicalAidTable() {
  populateMedMemberSelect();
  try {
    const data = await apiListMedicalAids();
    if (!data || !data.ok) return;
    window.db = window.db || {};
    window.db.medical_aids = data.medical_aids || [];
    renderMedicalTableFromApi(data.medical_aids || []);
  } catch (e) {
    console.error(e);
  }
}

document.addEventListener("turbo:load", bootMedicalAidTable);

function handleMedicalSubmit(event) {
  event.preventDefault();
  if (medMembers.length === 0) {
    showToast("Add at least one member.", true);
    return;
  }
  var formData = new FormData();
  var batch = [];
  for (var i = 0; i < medMembers.length; i++) {
    var date = document.getElementById("med_date_" + i);
    var reason = document.getElementById("med_reason_" + i);
    var hospital = document.getElementById("med_hospital_" + i);
    var hospitalDate = document.getElementById("med_hospital_date_" + i);
    var bill = document.getElementById("med_bill_" + i);
    if (!date || !reason || !bill) {
      showToast(
        "Card " + (i + 1) + ": Date, Reason, and Bill are required.",
        true,
      );
      return;
    }
    var dateVal = date.value;
    var reasonVal = reason.value;
    var hospitalVal = hospital ? hospital.value : "";
    var hospitalDateVal = hospitalDate ? hospitalDate.value : "";
    var billVal = bill.value;
    if (!dateVal || !reasonVal || !billVal) {
      showToast(
        "Card " + (i + 1) + ": Please fill in all required fields.",
        true,
      );
      return;
    }
    var medFiles = FileQueue.getFiles("med_" + i);
    if (medFiles.length === 0) {
      showToast(
        "Card " +
          (i + 1) +
          " (" +
          medMembers[i].name +
          "): At least one supporting document is required.",
        true,
      );
      return;
    }
    batch.push({
      member_id: medMembers[i].id,
      request_date: dateVal,
      reason: reasonVal,
      hospital: hospitalVal,
      hospital_date: hospitalDateVal,
      bill: billVal,
    });
    for (var f = 0; f < medFiles.length; f++) {
      formData.append("med_file_" + i + "_" + f, medFiles[f]);
    }
  }
      formData.append("med_batch_data", JSON.stringify(batch));

  // Prevent duplicate aid-entry submissions from double-clicking submit (I7).
  if (window.__medicalSubmitBusy) return;
  window.__medicalSubmitBusy = true;
  var _submitEl = event.submitter;
  if (_submitEl) _submitEl.disabled = true;

    apiAddMedicalAidBatch(formData)
    .then(function (data) {
      if (!data.ok) {
        var err = data.error || "Failed to submit batch.";
        // Try to show which card failed
        var match = err.match(/Card (\d+)/);
        if (match) err = "Member " + match[1] + ": " + err;
        showToast(err, true);
        return null;
      }
      return apiListMedicalAids();
    })
    .then(function (data) {
      if (!data) return;
      if (!data.ok) {
        showToast(data.error || "Table refresh failed.", true);
        return;
      }
      renderMedicalTableFromApi(data.medical_aids || []);
      showToast(
        medMembers.length + " medical aid request(s) submitted successfully.",
        false,
      );
      medMembers = [];
      renderMedCards();
      var searchInput = document.getElementById("med_member_search");
      if (searchInput) searchInput.value = "";
      var sel = document.getElementById("med_member");
      if (sel) sel.style.display = "";
      var results = document.getElementById("med_member_results");
      if (results) results.style.display = "none";
    })
    .catch(function (err) {
      console.error(err);
      showToast("Network error while submitting.", true);
    })
    .then(function () {
      window.__medicalSubmitBusy = false;
      if (_submitEl) _submitEl.disabled = false;
    });
}

// --- Death Table Filter ---
window.__deathFilterState = { status: [] };

function deathToggleFilter() {
  var card = document.getElementById("deathFilterCard");
  if (!card) return;
  var opening = card.style.display === "none";
  card.style.display = opening ? "block" : "none";
  if (opening) {
    deathFillFilters();
    var handler = function (e) {
      var btn = document.querySelector('[onclick="deathToggleFilter()"]');
      if (card.contains(e.target) || (btn && btn.contains(e.target))) return;
      document.removeEventListener("click", handler);
      card.style.display = "none";
      deathApplyFilter();
    };
    setTimeout(function () {
      document.addEventListener("click", handler);
    }, 0);
  }
}

function deathGetChecked(id) {
  var cbs = document.querySelectorAll(
      "#" + id + " input[type=checkbox]:checked",
    ),
    vals = [];
  for (var i = 0; i < cbs.length; i++) {
    var v = cbs[i].value;
    if (v !== "") vals.push(v);
  }
  return vals;
}

function deathGetAllValues(id) {
  var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]"),
    vals = [];
  for (var i = 0; i < cbs.length; i++) {
    if (cbs[i].value !== "") vals.push(cbs[i].value);
  }
  return vals;
}

function deathToggleAll(containerId, checked) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var cbs = container.querySelectorAll('input[type="checkbox"]');
  for (var i = 0; i < cbs.length; i++) {
    if (cbs[i].value !== "") cbs[i].checked = checked;
  }
  deathApplyFilter();
}

function deathSyncAll(containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var cbs = container.querySelectorAll('input[type="checkbox"]');
  var allBox = cbs.length > 0 ? cbs[0] : null;
  if (!allBox) return;
  var allChecked = true;
  for (var i = 1; i < cbs.length; i++) {
    if (!cbs[i].checked) {
      allChecked = false;
      break;
    }
  }
  allBox.checked = allChecked;
}

function deathApplyFilter() {
  refreshDeathAidTables();
}

function deathFillFilters() {
  var stats = {},
    i,
    d,
    arr =
      (typeof db !== "undefined" && db.death_aids) ||
      window.__deathAidsAll ||
      [];
  for (i = 0; i < arr.length; i++) {
    d = arr[i];
    if (d.status) stats[d.status] = 1;
  }
  var sk = Object.keys(stats).sort();
  var sc = document.getElementById("deathStatusCheckboxes");
  if (sc) {
    sc.innerHTML =
      '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="deathToggleAll(\'deathStatusCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
    for (i = 0; i < sk.length; i++)
      sc.innerHTML +=
        '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' +
        escapeHtml(sk[i]) +
        '" checked onchange="deathSyncAll(\'deathStatusCheckboxes\');deathApplyFilter()"> <span>' +
        escapeHtml(sk[i]) +
        "</span></label>";
  }
}

// Expose handler globally for inline form attribute
function renderDeathTableFromApi(deathAids, tableId) {
  var tbody = document.querySelector("#" + tableId + " tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  var stats =
    tableId === "deathTable" ? deathGetChecked("deathStatusCheckboxes") : [];
  if (tableId === "deathTable" && stats.length === 0) {
    stats = deathGetAllValues("deathStatusCheckboxes");
    deathSyncAll("deathStatusCheckboxes");
  }

  var arr = deathAids || [],
    flt = [],
    i;
  for (i = 0; i < arr.length; i++) {
    var d = arr[i];
    if (stats.length && stats.indexOf(d.status) === -1) continue;
    flt.push(d);
  }

  if (flt.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="7" style="text-align:center;color:#757580;padding:30px;">No death aid claims match current filters.</td></tr>';
    return;
  }

  flt.forEach(function (d) {
    var badgeStyle = "badge-yellow";
    if (d.status === "Released") badgeStyle = "badge-green";
    if (d.status === "Rejection Dispatched") badgeStyle = "badge-red";

    var isMember = d.is_member_deceased === true;
    var scenarioBadge = isMember
      ? '<span style="background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600;">Member Deceased</span>'
      : '<span style="background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600;">Dependent Deceased</span>';

    var rawId = String(d.id || "")
      .replace("DTH-", "")
      .replace("death-", "");
    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td style="font-weight:600;color:#1b5e20;">' +
      d.id +
      "</td>" +
      "<td>" +
      d.claimant +
      ' <br><span style="font-size:0.75rem;color:#757575;">Member: ' +
      d.name +
      "</span></td>" +
      "<td>" +
      scenarioBadge +
      ' <br><span style="font-size:0.85rem;">' +
      d.deceased +
      '</span> <br><span style="font-size:0.75rem;color:#757575;">' +
      (isMember ? "" : "Relationship: " + d.relationship) +
      "</span></td>" +
      '<td style="font-weight:600;">' +
      formatCurrencyPHP(d.benefit_amount) +
      "</td>" +
      "<td>" +
      (d.bill_amount ? formatCurrencyPHP(d.bill_amount) : "—") +
      "</td>" +
      '<td><span class="badge-zero ' +
      badgeStyle +
      '">' +
      d.status +
      "</span></td>";
    tbody.appendChild(tr);
  });
}

// ---------- Death Aid Scenario & Form ----------
const IMMEDIATE_RELATIONS = [
  "husband",
  "father",
  "son",
  "full-blood brother",
  "brother",
  "wife",
  "mother",
  "daughter",
  "full-blood sister",
  "sister",
];

function openDeathAidScenarioPicker() {
  // Reset any in-progress form first
  var formArea = document.getElementById("deathAidFormArea");
  if (formArea && formArea.style.display !== "none") {
    resetDeathAidForm();
  }
  Swal.fire({
    title: "Who is the deceased person?",
    html: [
      '<div style="display:flex;flex-direction:column;gap:12px;margin-top:16px">',
      '<button type="button" class="btn-brand btn-brand-primary" id="swl-death-member" style="width:100%;padding:14px;font-size:1.05rem;border-radius:30px">The Member (Policyholder)</button>',
      '<button type="button" class="btn-brand btn-brand-secondary" id="swl-death-dependent" style="width:100%;padding:14px;font-size:1.05rem;border-radius:30px">A Dependent (Spouse/Child/Parent/etc.)</button>',
      '<button type="button" class="btn-brand" id="swl-death-none" style="width:100%;padding:14px;font-size:1rem;background:#f5f5f5;color:#757575;border-radius:30px">None — Return to Dashboard</button>',
      "</div>",
    ].join(""),
    showConfirmButton: false,
    showCloseButton: true,
    customClass: { popup: "swal-rounded" },
    didOpen: function () {
      document.getElementById("swl-death-member").onclick = function () {
        Swal.close();
        setTimeout(function () {
          pickDeathMember();
        }, 100);
      };
      document.getElementById("swl-death-dependent").onclick = function () {
        Swal.close();
        setTimeout(function () {
          showDeathForm("dependent");
        }, 100);
      };
      document.getElementById("swl-death-none").onclick = function () {
        Swal.close();
        setTimeout(function () {
          setActiveModule("dashboard-overview");
        }, 100);
      };
    },
  });
}

function pickDeathMember() {
  var memberOptions = {};
  if (typeof db !== "undefined" && Array.isArray(db.members)) {
    db.members.forEach(function (m) {
      memberOptions[m.id] = m.name;
    });
  }
  Swal.fire({
    title: "Select the Deceased Member",
    input: "select",
    inputOptions: memberOptions,
    inputPlaceholder: "Select Associated Member",
    showCancelButton: true,
    confirmButtonText: "Continue",
    confirmButtonColor: "#1b5e20",
    customClass: { popup: "swal-rounded" },
    preConfirm: function (val) {
      if (!val) {
        Swal.showValidationMessage("Please select a member");
      }
      return val;
    },
  }).then(function (r) {
    if (r.isConfirmed) showDeathForm("member", r.value);
  });
}

function localDateStr(d) {
  var y = d.getFullYear();
  var m = String(d.getMonth() + 1).padStart(2, "0");
  var day = String(d.getDate()).padStart(2, "0");
  return y + "-" + m + "-" + day;
}

function setDeathDateBounds() {
  var today = localDateStr(new Date());
  var deathDate = document.getElementById("death_date");
  var interDate = document.getElementById("death_interment_date");
  if (deathDate) deathDate.max = today;
  if (interDate) interDate.max = today;
}

function showDeathForm(scenario, memberId) {
  FileQueue.init("death", {
    inputId: "death_file_input",
    containerId: "death_file_queue",
    maxFiles: 10,
  });
  document.getElementById("deathAidScenarioArea").style.display = "none";
  document.getElementById("deathAidFormArea").style.display = "block";

  document.getElementById("death_scenario").value = scenario;
  setDeathDateBounds();

  if (scenario === "member") {
    document.getElementById("deathCard1Member").style.display = "block";
    document.getElementById("deathCard1Dependent").style.display = "none";
    document.getElementById("deathTableMember").style.display = "";
    document.getElementById("deathTableDependent").style.display = "none";
    var member = null;
    if (typeof db !== "undefined" && Array.isArray(db.members)) {
      for (var i = 0; i < db.members.length; i++) {
        if (String(db.members[i].id) === String(memberId)) {
          member = db.members[i];
          break;
        }
      }
    }
    if (member) {
      document.getElementById("death_member_name_display").textContent =
        member.name + " (" + member.id + ")";
      var decInput = document.getElementById("death_deceased");
      if (decInput) decInput.value = member.name;
    }
    document
      .getElementById("death_scenario")
      .setAttribute("data-member-id", memberId || "");
  } else {
    document.getElementById("deathCard1Member").style.display = "none";
    document.getElementById("deathCard1Dependent").style.display = "block";
    document.getElementById("deathTableMember").style.display = "none";
    document.getElementById("deathTableDependent").style.display = "";
    var sel = document.getElementById("death_member_select");
    if (sel) {
      sel.innerHTML = '<option value="">Select Associated Member</option>';
      if (typeof db !== "undefined" && Array.isArray(db.members)) {
        for (var i = 0; i < db.members.length; i++) {
          var m = db.members[i];
          sel.innerHTML +=
            '<option value="' + m.id + '">' + m.name + "</option>";
        }
      }
      sel.onchange = function () {
        var selectedId = this.value;
        var claimantInput = document.getElementById("death_claimant_dep");
        var contactInput = document.getElementById("death_contact_dep");
        if (!selectedId || !claimantInput || !contactInput) return;
        if (typeof db !== "undefined" && Array.isArray(db.members)) {
          for (var i = 0; i < db.members.length; i++) {
            if (db.members[i].id === selectedId) {
              claimantInput.value = db.members[i].name;
              contactInput.value = db.members[i].contact || "";
              break;
            }
          }
        }
        // Claimant is always the member filing the claim for a dependent
        claimantInput.readOnly = true;
        claimantInput.style.background = "#e8f5e9";
        claimantInput.style.fontWeight = "600";
      };
    }
  }

  filterDeathTableByScenario(scenario);
}

function filterDeathTableByScenario(scenario) {
  var all = (typeof db !== "undefined" && db.death_aids) || [];
  var filtered = all;
  var tableId = "deathTable";
  if (scenario === "member") {
    filtered = all.filter(function (d) {
      return d.is_member_deceased === true;
    });
    tableId = "deathTableMember";
  } else if (scenario === "dependent") {
    filtered = all.filter(function (d) {
      return d.is_member_deceased !== true;
    });
    tableId = "deathTableDependent";
  }
  renderDeathTableFromApi(filtered, tableId);
}

function resetDeathAidForm() {
  document.getElementById("deathForm").reset();
  FileQueue.clear("death");
  document.getElementById("deathAidFormArea").style.display = "none";
  document.getElementById("deathAidScenarioArea").style.display = "grid";
  refreshDeathAidTables();
  openDeathAidScenarioPicker();
}

function updateDeathRelOptions() {
  // Only operate on the visible card's elements
  var card1m = document.getElementById("deathCard1Member");
  var card1d = document.getElementById("deathCard1Dependent");
  var visibleCard = null;
  if (card1m && card1m.style.display !== "none") visibleCard = card1m;
  else if (card1d && card1d.style.display !== "none") visibleCard = card1d;
  if (!visibleCard) return;

  var group = visibleCard.querySelector(".death-rel-group");
  var relSelect = visibleCard.querySelector(".death-rel-select");
  var relText = visibleCard.querySelector(".death-rel-text");
  if (!group) return;

  var selectedGroup = group.value;

  if (relSelect) {
    relSelect.style.display = "none";
    relSelect.required = false;
  }
  if (relText) {
    relText.style.display = "none";
    relText.required = false;
  }

  if (selectedGroup === "immediate" && relSelect) {
    relSelect.style.display = "";
    relSelect.required = true;
    relSelect.innerHTML =
      '<option value="" disabled selected>Select relationship</option>';
    for (var j = 0; j < IMMEDIATE_RELATIONS.length; j++) {
      var r = IMMEDIATE_RELATIONS[j];
      relSelect.innerHTML +=
        '<option value="' +
        r +
        '">' +
        r.charAt(0).toUpperCase() +
        r.slice(1) +
        "</option>";
    }
    if (relText) relText.value = "";
  } else if (selectedGroup === "extended" && relText) {
    relText.style.display = "";
    relText.required = true;
    if (relSelect) relSelect.value = "";
  }
}

const DEATH_REL_MAP = {
  husband: "husband",
  wife: "wife",
  father: "father",
  mother: "mother",
  son: "son",
  daughter: "daughter",
  "full-blood brother": "full-blood brother",
  "full-blood sister": "full-blood sister",
  brother: "brother",
  sister: "sister",
};

// ---------- Multi-file management for Death Aid ----------
async function bootDeathAidTable() {
  try {
    var data = await apiListDeathAids();
    if (!data || !data.ok) return;
    window.db = window.db || {};
    window.db.death_aids = data.death_aids || [];
    renderDeathTableFromApi(window.db.death_aids, "deathTable");
  } catch (e) {
    console.error(e);
  }
}
function refreshDeathAidTables() {
  var all = (typeof db !== "undefined" && db.death_aids) || [];
  renderDeathTableFromApi(all, "deathTable");
  renderDeathTableFromApi(
    all.filter(function (d) {
      return d.is_member_deceased === true;
    }),
    "deathTableMember",
  );
  renderDeathTableFromApi(
    all.filter(function (d) {
      return d.is_member_deceased !== true;
    }),
    "deathTableDependent",
  );
}

function handleDeathSubmit(event) {
  event.preventDefault();
  var form = event.target;
  var formData = new FormData(form);

  var scenario = document.getElementById("death_scenario").value;
  var visibleCard = null;
  if (document.getElementById("deathCard1Member").style.display !== "none")
    visibleCard = document.getElementById("deathCard1Member");
  else if (
    document.getElementById("deathCard1Dependent").style.display !== "none"
  )
    visibleCard = document.getElementById("deathCard1Dependent");

  // Resolve member ID
  var memberId = "";
  if (scenario === "member") {
    memberId =
      document
        .getElementById("death_scenario")
        .getAttribute("data-member-id") || "";
  } else if (visibleCard) {
    var memberSelect = visibleCard.querySelector(
      "#death_member_select, select[id^='death_member']",
    );
    if (memberSelect) memberId = memberSelect.value;
  }
  if (!memberId) {
    showToast("Please select a member.", true);
    return;
  }

  // Resolve relationship value from 2-part dropdown
  var relGroup = visibleCard
    ? visibleCard.querySelector(".death-rel-group")
    : null;
  var relSelect = visibleCard
    ? visibleCard.querySelector(".death-rel-select")
    : null;
  var relText = visibleCard
    ? visibleCard.querySelector(".death-rel-text")
    : null;
  var relValue = "";
  if (relGroup && relGroup.value === "immediate" && relSelect) {
    relValue = relSelect.value;
  } else if (relGroup && relGroup.value === "extended" && relText) {
    relValue = relText.value.trim();
  }
  if (!relValue) {
    showToast("Please select or specify the relationship.", true);
    return;
  }

  var todayStr = localDateStr(new Date());
  var deathDateInput = document.getElementById("death_date");
  if (deathDateInput && !deathDateInput.value) {
    showToast("Date of death is required.", true);
    return;
  }
  if (deathDateInput && deathDateInput.value > todayStr) {
    showToast("The date of death cannot be a future date.", true);
    return;
  }
  var interDateInput = document.getElementById("death_interment_date");
  if (interDateInput && interDateInput.value && interDateInput.value > todayStr) {
    showToast("The interment date cannot be a future date.", true);
    return;
  }

  // Override visible-card fields to avoid duplicate-named hidden inputs corrupting POST
  if (visibleCard) {
    var clmInput = visibleCard.querySelector("[name='death_claimant']");
    if (clmInput) formData.set("death_claimant", clmInput.value);
    var cntInput = visibleCard.querySelector("[name='death_contact']");
    if (cntInput) formData.set("death_contact", cntInput.value);
  }
  formData.append("death_member", memberId);
  formData.append("death_rel", relValue);
  var relGroupEl = visibleCard
    ? visibleCard.querySelector(".death-rel-group")
    : null;
  formData.append("death_rel_group", relGroupEl ? relGroupEl.value : "");

  var deathQueue = FileQueue.getFiles("death");
  if (deathQueue.length === 0) {
    showToast(
      "At least one supporting document (Death Certificate or equivalent) is required.",
      true,
    );
    return;
  }
  for (var fi = 0; fi < deathQueue.length; fi++) {
    formData.append("death_photo_files", deathQueue[fi]);
  }

  // Prevent duplicate death-aid submissions from double-clicking submit (I7).
  if (window.__deathSubmitBusy) return;
  window.__deathSubmitBusy = true;
  var _submitEl = event.submitter;
  if (_submitEl) _submitEl.disabled = true;

  apiAddDeathAid(formData)
    .then(function (data) {
      if (!data.ok) {
        showToast(data.error || "Failed to submit death aid claim.", true);
        return null;
      }
      return apiListDeathAids();
    })
    .then(function (data) {
      if (!data) return;
      if (!data.ok) {
        showToast(data.error || "Death Aid table refresh failed.", true);
        return;
      }
      window.db = window.db || {};
      window.db.death_aids = data.death_aids || [];
      refreshDeathAidTables();
      showToast("Death Aid claim submitted successfully.", false);
      form.reset();
      FileQueue.clear("death");
    })
    ["catch"](function (err) {
      console.error(err);
      showToast("Network error while submitting.", true);
    })
    .then(function () {
      window.__deathSubmitBusy = false;
      if (_submitEl) _submitEl.disabled = false;
    });
}

// Toggle collapsible Funeral & Interment drawer
function toggleFuneralDrawer() {
  var body = document.getElementById("funeralDrawerBody");
  var chevron = document.getElementById("funeralChevron");
  if (!body || !chevron) return;
  var isOpen = body.style.maxHeight && body.style.maxHeight !== "0px";
  if (isOpen) {
    body.style.maxHeight = "0px";
    chevron.style.transform = "rotate(0deg)";
  } else {
    body.style.maxHeight = body.scrollHeight + "px";
    chevron.style.transform = "rotate(90deg)";
  }
}
window.toggleFuneralDrawer = toggleFuneralDrawer;

// Expose functions globally
window.updateDeathRelOptions = updateDeathRelOptions;
window.resetDeathAidForm = resetDeathAidForm;
window.openDeathAidScenarioPicker = openDeathAidScenarioPicker;
window.showDeathForm = showDeathForm;

document.addEventListener("turbo:load", bootDeathAidTable);

// Expose handlers globally for inline form attribute
window.handleMedicalSubmit = handleMedicalSubmit;
window.handleDeathSubmit = handleDeathSubmit;
window.filterMedMembers = filterMedMembers;
window.onMedMemberSelect = onMedMemberSelect;
window.hideMedResults = hideMedResults;
window.handleMedSearchKeydown = handleMedSearchKeydown;
window.addMedMember = addMedMember;
window.removeMedMember = removeMedMember;
window.updateMedCardBillIndicator = updateMedCardBillIndicator;
window.toggleMedCardHospitalDrawer = toggleMedCardHospitalDrawer;
