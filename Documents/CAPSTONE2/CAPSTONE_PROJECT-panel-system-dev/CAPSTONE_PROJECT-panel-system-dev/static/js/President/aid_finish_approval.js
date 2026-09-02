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

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  var FINISH_REQUESTS_URL = "/api/president/aid-post-finish-requests/";
  var APPROVE_URL = "/api/president/aid-post-finish-approve/";
  var REJECT_URL = "/api/president/aid-post-finish-reject/";

  async function getJSON(url) {
    const resp = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json().catch(function () {
      return {};
    });
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Request failed: " + url);
    }
    return data;
  }

  async function postForm(url, fd) {
    const csrf = getCSRFToken();
    var headers = {};
    if (csrf) {
      headers[CSRF_HEADER_NAME] = csrf;
    }
    var resp = await fetch(url, {
      method: "POST",
      body: fd,
      headers: headers,
      credentials: "same-origin",
    });
    var data = await resp.json().catch(function () {
      return {};
    });
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Server error.");
    }
    return data;
  }

  async function loadRequests() {
    try {
      var data = await getJSON(FINISH_REQUESTS_URL);
      renderRequests(data.posts || []);
      updateNotificationDot((data.posts || []).length);
      if (typeof window.normalizeNotifDots === "function") window.normalizeNotifDots();
    } catch (e) {
      showToast(e.message || "Failed to load finish requests.", true);
    }
  }

  function updateNotificationDot(count) {
    window.__finishApprovalCount = count;
    var dot = getEl("pres-finish-dot");
    if (dot) {
      if (count > 0) {
        dot.style.display = "inline-flex";
        dot.textContent = count > 99 ? "99+" : count;
      } else {
        dot.style.display = "none";
      }
    }
    if (typeof updatePresidentNotifDots === "function") {
      updatePresidentNotifDots();
    }
    if (typeof window.normalizeNotifDots === "function") window.normalizeNotifDots();
  }

  function faGetChecked(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]:checked"), vals = [];
    for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v !== "") vals.push(v); }
    return vals;
  }
  function faGetAllValues(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]"), vals = [];
    for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") vals.push(cbs[i].value); }
    return vals;
  }
  function faToggleAll(containerId, checked) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") cbs[i].checked = checked; }
    loadRequests();
  }
  function faSyncAll(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    var allBox = cbs.length > 0 ? cbs[0] : null;
    if (!allBox) return;
    var allChecked = true;
    for (var i = 1; i < cbs.length; i++) { if (!cbs[i].checked) { allChecked = false; break; } }
    allBox.checked = allChecked;
  }
  function faToggleFilter() {
    var card = document.getElementById("faFilterCard");
    if (!card) return;
    var opening = card.style.display === "none";
    card.style.display = opening ? "block" : "none";
    if (opening) {
      faFillFilters();
      var handler = function(e) {
        var btn = document.querySelector('[onclick="faToggleFilter()"]');
        if (card.contains(e.target) || (btn && btn.contains(e.target))) return;
        document.removeEventListener("click", handler);
        card.style.display = "none";
        loadRequests();
      };
      setTimeout(function() { document.addEventListener("click", handler); }, 0);
    }
  }
  function faFillFilters() {
    var types = {}, i, p, arr = window.__finishPosts || [];
    for (i = 0; i < arr.length; i++) { p = arr[i]; if (p.aid_label) types[p.aid_label] = 1; }
    var tk = Object.keys(types).sort();
    var tc = document.getElementById("faTypeCheckboxes");
    if (tc) {
      tc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="faToggleAll(\'faTypeCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
      for (i = 0; i < tk.length; i++) tc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' + escapeHtml(tk[i]) + '" checked onchange="faSyncAll(\'faTypeCheckboxes\');loadRequests()"> <span>' + escapeHtml(tk[i]) + '</span></label>';
    }
  }
  window.faToggleFilter = faToggleFilter;
  window.faApplyFilter = function() { loadRequests(); };

  var __finishAllPosts = [];

  function renderRequests(posts) {
    var tbody = getEl("finishApprovalTableBody");
    if (!tbody) return;
    __finishAllPosts = posts || [];
    window.__finishPosts = __finishAllPosts;

    var types = faGetChecked("faTypeCheckboxes");
    if (types.length === 0) { types = faGetAllValues("faTypeCheckboxes"); faSyncAll("faTypeCheckboxes"); }

    var arr = posts || [], flt = [], i, p;
    for (i = 0; i < arr.length; i++) {
      p = arr[i];
      if (types.length && types.indexOf(p.aid_label) === -1) continue;
      flt.push(p);
    }

    tbody.innerHTML = "";
    if (!posts || posts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#90a4ae;padding:30px;">No pending finish requests.</td></tr>';
      return;
    }
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      return;
    }

    flt.forEach(function (p) {
      var tr = document.createElement("tr");

      var rateColor = "#e53935";
      if (p.collection_rate >= 100) rateColor = "#1b5e20";
      else if (p.collection_rate >= 50) rateColor = "#fbc02d";

      var skipLabel = p.skip_remaining ? "Yes (auto-skip unpaid)" : "No";

      tr.innerHTML =
        "<td><strong>" + escapeHtml(p.member_name || "Unknown") + "</strong>" + (p.verified_by_auditor ? ' <span style="background:#e8f5e9;color:#2e7d32;padding:1px 6px;border-radius:8px;font-size:0.65rem;font-weight:600;margin-left:4px;">Auditor Verified</span>' : '') + "</td>" +
        "<td>" + escapeHtml(p.aid_label || "") + "</td>" +
        "<td>" + formatMoneyPHP(p.total_expected) + "</td>" +
        "<td>" + formatMoneyPHP(p.total_collected) + "</td>" +
        '<td style="font-weight:600;color:' + rateColor + ';">' + p.collection_rate + "%</td>" +
        "<td>" + escapeHtml(skipLabel) + "</td>" +
        "<td style='font-size:0.82rem;color:#90a4ae;'>" + escapeHtml(p.created_by || "") + "<br><small>" + escapeHtml(p.created_at || "") + "</small></td>" +
        '<td style="white-space:nowrap;text-align:right;">' +
        '<button class="btn-approve-finish" data-post-id="' + p.post_id + '" style="padding:3px 8px;font-size:0.72rem;margin:0 2px;min-width:60px;border:none;border-radius:20px;color:#fff;cursor:pointer;background:rgba(27,94,32,0.7);">Approve</button>' +
        '<button class="btn-details-finish" data-post-id="' + p.post_id + '" style="padding:3px 8px;font-size:0.72rem;margin:0 2px;min-width:60px;border:none;border-radius:20px;color:#fff;cursor:pointer;background:rgba(21,101,192,0.7);">Details</button>' +
        "</td>";

      tr.querySelector(".btn-approve-finish").addEventListener("click", function () {
        handleApprove(p.post_id, p.member_name);
      });
      tr.querySelector(".btn-details-finish").addEventListener("click", function () {
        handleViewDetails(p.post_id);
      });

      tbody.appendChild(tr);
    });
  }

  async function handleApprove(postId, memberName) {
    var result = await Swal.fire({
      title: "Approve Finish?",
      text: "This will mark " + (memberName || "this post") + " as finished and move it to history.",
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Yes, approve",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#1b5e20",
      reverseButtons: true,
    });
    if (!result.isConfirmed) return;

    try {
      var fd = new FormData();
      fd.append("post_id", postId);
      await postForm(APPROVE_URL, fd);
      showToast("Finish request approved. Post moved to history.", false);
      loadRequests();
    } catch (e) {
      showToast(e.message || "Failed to approve finish request.", true);
    }
  }

  async function handleReject(postId, memberName) {
    var result = await Swal.fire({
      title: "Reject Finish?",
      text: "The post will return to active state for " + (memberName || "this member") + ".",
      icon: "warning",
      input: "textarea",
      inputPlaceholder: "Reason for rejection (optional)...",
      showCancelButton: true,
      confirmButtonText: "Yes, reject",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#c62828",
      reverseButtons: true,
    });
    if (!result.isConfirmed) return;

    try {
      var fd = new FormData();
      fd.append("post_id", postId);
      var remarks = (result.value || "").trim();
      if (remarks) {
        fd.append("remarks", remarks);
      }
      await postForm(REJECT_URL, fd);
      showToast("Finish request rejected. Post returned to active state.", false);
      loadRequests();
    } catch (e) {
      showToast(e.message || "Failed to reject finish request.", true);
    }
  }

  async function handleViewDetails(postId) {
    try {
      var res = await fetch("/api/president/finish-request-details/?post_id=" + postId, { credentials: "same-origin" });
      var data = await res.json();
      if (!data.ok) { showToast(data.error || "Failed.", true); return; }
      var paidStatuses = ["PAID", "RECORDED", "PENDING_VERIFICATION"];
      var rows = data.details.map(function (c) {
        var isPaid = paidStatuses.indexOf(c.status) !== -1;
        var statusIcon = isPaid ? '<i class="fas fa-check-circle" style="color:#2e7d32;"></i>' : '<i class="fas fa-times-circle" style="color:#9e9e9e;"></i>';
        var statusLabel = c.status === "RECORDED" ? "Recorded" : c.status === "PENDING_VERIFICATION" ? "Paid - Pending Verification" : c.status;
        return '<tr>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #eee;">' + escapeHtml(c.member_name) + '</td>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #eee;">' + escapeHtml(statusLabel) + ' ' + statusIcon + '</td>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:right;">₱' + c.expected_amount.toFixed(2) + '</td>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:right;font-weight:' + (isPaid ? "600" : "400") + ';">' + (isPaid ? "₱" + c.paid_amount.toFixed(2) : "—") + '</td>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:center;">' + (c.payment_date ? escapeHtml(c.payment_date) : "—") + '</td>' +
          '</tr>';
      }).join("");
      var totalRow = data.paid_count > 0 ? '<tr style="font-weight:700;background:#f5f5f5;"><td colspan="2" style="padding:8px;text-align:right;">Total Paid:</td><td style="padding:8px;text-align:right;color:#2e7d32;">₱' + data.total_paid.toFixed(2) + '</td><td colspan="2" style="padding:8px;"></td></tr>' : '';
      Swal.fire({
        title: 'Finish Details — ' + escapeHtml(data.target_month),
        html:
          '<p style="margin:0 0 6px;font-size:0.85rem;color:#666;">' + data.paid_count + ' / ' + data.total_count + ' members paid | Expected: ₱' + data.total_expected.toFixed(2) + '</p>' +
          '<div style="max-height:360px;overflow-y:auto;border:1px solid #ddd;border-radius:6px;">' +
          '<table style="width:100%;border-collapse:collapse;font-size:0.82rem;">' +
          '<thead><tr style="background:#1565c0;color:#fff;"><th style="padding:7px 8px;text-align:left;">Member</th><th style="padding:7px 8px;text-align:left;">Status</th><th style="padding:7px 8px;text-align:right;">Expected</th><th style="padding:7px 8px;text-align:right;">Paid</th><th style="padding:7px 8px;text-align:center;">Date</th></tr></thead>' +
          '<tbody>' + rows + '</tbody>' +
          (totalRow ? '<tfoot>' + totalRow + '</tfoot>' : '') +
          '</table></div>',
        width: 720,
        confirmButtonText: "Close",
        confirmButtonColor: "#1565c0",
      });
    } catch (e) { showToast(e.message || "Failed to load details.", true); }
  }

  window.AidFinishApproval = {
    loadRequests: loadRequests,
  };

  var _observer = null;

  document.addEventListener("turbo:load", function () {
    // Populate the Finish Approvals list and notification dot up-front so the
    // badge renders before the tab is ever opened.
    loadRequests();

    var tab = getEl("president-finish-approvals");
    if (tab) {
      _observer = new MutationObserver(function () {
        if (tab.classList.contains("active")) {
          loadRequests();
        }
      });
      _observer.observe(tab, { attributes: true, attributeFilter: ["class"] });
    }
  });

  document.addEventListener("turbo:before-cache", function () {
    if (_observer) { _observer.disconnect(); _observer = null; }
  });
})();
