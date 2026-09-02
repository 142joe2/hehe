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

  function getStatusBadgeClass(status) {
    const s = (status || "").toUpperCase();
    if (s === "PAID") return "badge-green";
    if (s === "UNDER") return "badge-yellow";
    if (s === "OVER") return "badge-medical-aid";
    if (s === "SKIPPED") return "badge-zero";
    if (s === "EXCLUDED_REQUESTER") return "badge-zero";
    return "badge-red";
  }

  function getStatusLabel(status) {
    const map = {
      PAID: "PAID",
      UNDER: "UNDER",
      OVER: "OVER",
      NOT_PAID: "NOT PAID",
      SKIPPED: "SKIPPED",
      EXCLUDED_REQUESTER: "NOT INCLUDED",
    };
    return map[status] || status || "NOT PAID";
  }

  function getStatusIcon(status) {
    const map = {
      PAID: "\u{1F7E2}",
      UNDER: "\u{1F7E1}",
      OVER: "\u{1F535}",
      NOT_PAID: "\u{1F534}",
      SKIPPED: "\u26AB",
      EXCLUDED_REQUESTER: "\u{1F534}",
    };
    return map[status] || "\u{1F534}";
  }

  let state = {
    posts: [],
    selectedPostId: null,
    members: [],
    selectedContributionIds: new Set(),
    historyPosts: [],
    selectedHistoryPostId: null,
    historyMembers: [],
  };

  var WS_URL = (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/ws/treasurer-dashboard/";
  var ws = null;
  var wsReconnectTimer = null;

  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      scheduleReconnect();
      return;
    }
    ws.onmessage = function (event) {
      try {
        var msg = JSON.parse(event.data);
        handleWsMessage(msg);
      } catch (e) {}
    };
    ws.onclose = function () {
      scheduleReconnect();
    };
    ws.onerror = function () {
      ws.close();
    };
  }

  function scheduleReconnect() {
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
    wsReconnectTimer = setTimeout(connectWebSocket, 5000);
  }

  function handleWsMessage(msg) {
    if (msg.type === "ping" || msg.type === "pong" || msg.type === "connection_established") return;
    if (msg.type === "aid_post_created") {
      loadPosts();
      showToast("New aid: " + formatMoneyPHP(msg.total_expected) + " for " + (msg.member_name || ""), false);
    } else if (msg.type === "contribution_updated") {
      if (state.selectedPostId === msg.post_id) {
        var m = state.members.find(function (x) { return x.contribution_id === msg.contribution_id; });
        if (m) {
          m.status = msg.status;
          m.paid_amount = msg.paid_amount || 0;
        }
        renderMembersTable(state.members);
      }
      var p = state.posts.find(function (x) { return x.post_id === msg.post_id; });
      if (p) {
        p.total_collected = (p.total_collected || 0) + (msg.status === "PAID" ? parseFloat(msg.paid_amount || 0) : 0);
        p.collection_rate = p.total_expected > 0 ? Math.round((p.total_collected / p.total_expected) * 100) : 0;
      }
      renderCards();
      highlightSelectedCard();
    } else if (msg.type === "aid_post_finished") {
      state.posts = state.posts.filter(function (p) { return p.post_id !== msg.post_id; });
      if (state.selectedPostId === msg.post_id) {
        clearRightPanel();
      }
      renderCards();
      updateActiveAidGreenDots(state.posts.length);
      loadHistoryPosts();
      showToast((msg.member_name || "A post") + " has been finished.", false);
      if (typeof window.normalizeNotifDots === "function") window.normalizeNotifDots();
    } else if (msg.type === "aid_post_finish_requested") {
      var fp = state.posts.find(function (x) { return x.post_id === msg.post_id; });
      if (fp) {
        fp.finish_status = msg.stage === "auditor" ? "pending_auditor" : msg.stage === "president" ? "pending_president" : "pending_approval";
      }
      renderCards();
      highlightSelectedCard();
      if (typeof window.normalizeNotifDots === "function") window.normalizeNotifDots();
    } else if (msg.type === "aid_post_release_pending") {
      var rp = state.posts.find(function (x) { return x.post_id === msg.post_id; });
      if (rp) {
        rp.finish_status = "pending_release";
      }
      renderCards();
      highlightSelectedCard();
      showToast((msg.member_name || "A post") + " is ready for fund release.", false);
    } else if (msg.type === "aid_post_finish_rejected") {
      var rp = state.posts.find(function (x) { return x.post_id === msg.post_id; });
      if (rp) {
        rp.finish_status = "rejected";
      }
      renderCards();
      highlightSelectedCard();
      showToast((msg.member_name || "A post") + " finish was rejected." + (msg.remarks ? " Reason: " + msg.remarks : ""), true);
    } else if (msg.type === "pending_queue_updated") {
      showToast((msg.queue_type || "Queue") + ": " + msg.count + " pending.", false);
    } else if (msg.type === "dashboard_refresh") {
      if (msg.section === "all" || msg.section === "aid_tracking") {
        loadPosts();
      }
    }
  }

  function highlightSelectedCard() {
    if (!state.selectedPostId) return;
    var cards = document.querySelectorAll(".aid-post-card");
    cards.forEach(function (c) {
      c.classList.toggle("selected", parseInt(c.dataset.postId) === state.selectedPostId);
    });
  }

  var POSTS_URL = "/api/treasurer/approved-aid-posts/";
  var MEMBERS_URL = "/api/treasurer/aid-post-members/";
  var PAY_URL = "/api/treasurer/aid-post-member-pay/";
  var SKIP_URL = "/api/treasurer/aid-post-member-skip/";
  var FINISH_URL = "/api/treasurer/aid-post-finish/";
  var HISTORY_URL = "/api/treasurer/aid-post-history/";

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

  function renderCard(post) {
    var card = document.createElement("div");
    card.className = "aid-post-card";
    card.dataset.postId = post.post_id;
    card.style.cssText =
      "background:#fff;border:1px solid #dfe9df;border-radius:14px;padding:18px;" +
      "cursor:pointer;transition:all 0.2s ease;box-shadow:0 2px 8px rgba(0,0,0,0.04);";

    var isMedical = post.aid_type === "medical_aid";
    var accentColor = isMedical ? "#2dd4bf" : "#a5b4fc";
    var bgColor = isMedical ? "#ccfbf1" : "#e0e7ff";
    var textColor = isMedical ? "#115e59" : "#4338ca";

    var badgeHtml =
      '<span style="background:' +
      bgColor +
      ";color:" +
      textColor +
      ";border:1px solid " +
      accentColor +
      ";padding:4px 10px;border-radius:6px;font-size:0.72rem;font-weight:600;display:inline-block;'>" +
      escapeHtml(post.aid_label || (isMedical ? "Medical Aid" : "Death Aid")) +
      "</span>";

    var st = post.status || "";
    var statusBadgeColor = "#546e7a";
    var statusBadgeBg = "#eceff1";
    if (statusUtils.isApproved(st)) {
      statusBadgeColor = "#1b5e20";
      statusBadgeBg = "#e8f5e9";
    } else if (statusUtils.isReleased(st)) {
      statusBadgeColor = "#0d47a1";
      statusBadgeBg = "#e3f2fd";
    } else if (statusUtils.isAuditorVerified(st)) {
      statusBadgeColor = "#e65100";
      statusBadgeBg = "#fff3e0";
    }
    var statusBadge =
      '<span style="background:' +
      statusBadgeBg +
      ";color:" +
      statusBadgeColor +
      ";border:1px solid " +
      statusBadgeColor +
      ";padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:500;display:inline-block;margin-left:6px;'>" +
      escapeHtml(st || "Pending") +
      "</span>";

    var rateColor = "#e53935";
    if (post.collection_rate >= 100) rateColor = "#1b5e20";
    else if (post.collection_rate >= 50) rateColor = "#fbc02d";

    var finishStatus = post.finish_status || "";
    var isPendingApproval = finishStatus === "pending_approval";
    var isRejected = finishStatus === "rejected";

    var finishBadgeHtml = "";
    if (isPendingApproval) {
      finishBadgeHtml = '<div style="margin-top:6px;margin-bottom:6px;"><span style="background:#fff8e1;color:#f57c00;border:1px solid #fbc02d;padding:3px 10px;border-radius:6px;font-size:0.68rem;font-weight:600;">⏳ Pending President Approval</span></div>';
    } else if (isRejected) {
      finishBadgeHtml = '<div style="margin-top:6px;margin-bottom:6px;"><span style="background:#ffebee;color:#c62828;border:1px solid #ef5350;padding:3px 10px;border-radius:6px;font-size:0.68rem;font-weight:600;">❌ Finish Rejected</span></div>';
    }

    var canFinish = post.collection_rate >= 70 && !isPendingApproval;
    var finishDisabled = canFinish ? "" : " disabled";
    var finishStyle = canFinish
      ? "opacity:1;cursor:pointer;"
      : "opacity:0.4;cursor:not-allowed;";
    var finishBtnText = isRejected ? "Retry Finish Request" : "Mark as Finished";

    card.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">' +
      "<div>" +
      badgeHtml +
      statusBadge +
      "</div>" +
      '<span style="font-size:0.72rem;color:#90a4ae;">' +
      escapeHtml(post.target_month || "") +
      "</span>" +
      "</div>" +
      '<div style="font-weight:600;font-size:1rem;color:#263238;margin-bottom:8px;">' +
      escapeHtml(post.member_name || "Unknown Member") +
      "</div>" +
      finishBadgeHtml +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:0.82rem;color:#546e7a;margin-bottom:10px;">' +
      "<div><strong>Amount:</strong> " +
      formatMoneyPHP(post.amount) +
      "</div>" +
      "<div><strong>Expected:</strong> " +
      formatMoneyPHP(post.total_expected) +
      "</div>" +
      "</div>" +
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">' +
      '<div style="flex:1;height:6px;background:#eef7ef;border-radius:3px;overflow:hidden;">' +
      '<div style="height:100%;width:' +
      Math.min(post.collection_rate, 100) +
      "%;background:" +
      rateColor +
      ";border-radius:3px;transition:width 0.3s ease;" +
      '"></div></div>' +
      '<span style="font-size:0.78rem;font-weight:600;color:' +
      rateColor +
      ';">' +
      post.collection_rate +
      "%</span>" +
      "</div>" +
      '<div style="font-size:0.72rem;color:#90a4ae;">Collected: ' +
      formatMoneyPHP(post.total_collected) +
      " of " +
      formatMoneyPHP(post.total_expected) +
      "</div>" +
      '<button class="btn-finish-post" data-post-id="' +
      post.post_id +
      '" style="margin-top:10px;padding:4px 12px;font-size:0.7rem;border-radius:8px;border:1px solid #e53935;background:#fff;color:#e53935;font-weight:600;font-family:\'Poppins\',sans-serif;transition:all 0.2s;width:auto;' +
      finishStyle +
      '"' +
      finishDisabled +
      ">" + escapeHtml(finishBtnText) + "</button>";

    card.addEventListener("click", function (e) {
      if (e.target.classList.contains("btn-finish-post")) return;
      selectPost(post.post_id);
    });

    card.addEventListener("mouseenter", function () {
      card.style.borderColor = "#1b5e20";
      card.style.boxShadow = "0 4px 16px rgba(27,94,32,0.12)";
    });
    card.addEventListener("mouseleave", function () {
      card.style.borderColor = "#dfe9df";
      card.style.boxShadow = "0 2px 8px rgba(0,0,0,0.04)";
    });

    return card;
  }

  function renderCards() {
    var container = getEl("unifiedAidPostsContainer");
    if (!container) return;

    container.innerHTML = "";

    if (!state.posts || state.posts.length === 0) {
      container.innerHTML =
        '<div style="text-align:center;padding:40px;color:#90a4ae;font-size:0.9rem;">' +
        "No approved aid posts yet. Once the President approves an aid request, it will appear here." +
        "</div>";
      return;
    }

    state.posts.forEach(function (post) {
      container.appendChild(renderCard(post));
    });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".btn-finish-post");
    if (btn) {
      var postId = parseInt(btn.dataset.postId);
      if (confirm("Mark this post as finished? It will move to History.")) {
        handleFinishPost(postId);
      }
    }
  });

  function filterPosts() {
    var searchVal = (getEl("aidPostSearch") || {}).value || "";
    var typeVal = (getEl("aidTypeFilter") || {}).value || "All";
    var statusVal = (getEl("aidStatusFilter") || {}).value || "All";

    var filtered = state.posts.filter(function (p) {
      var name = (p.member_name || "").toLowerCase();
      var matchesSearch = !searchVal || name.indexOf(searchVal.toLowerCase()) !== -1;
      var matchesType =
        typeVal === "All" ||
        (typeVal === "Medical" && p.aid_type === "medical_aid") ||
        (typeVal === "Death" && p.aid_type === "death_aid");
      var matchesStatus =
        statusVal === "All" || (p.status || "") === statusVal;
      return matchesSearch && matchesType && matchesStatus;
    });

    var container = getEl("unifiedAidPostsContainer");
    if (!container) return;
    container.innerHTML = "";

    if (filtered.length === 0) {
      container.innerHTML =
        '<div style="text-align:center;padding:40px;color:#90a4ae;font-size:0.9rem;">' +
        "No posts match your filter." +
        "</div>";
      return;
    }

    filtered.forEach(function (post) {
      container.appendChild(renderCard(post));
    });
  }

  function updateMemberBatchBar() {
    var bar = getEl("member-batch-bar");
    var countEl = getEl("member-selected-count");
    var count = state.selectedContributionIds.size;
    if (!bar || !countEl) return;
    countEl.textContent = count + " selected";
    bar.style.display = count > 0 ? "flex" : "none";
  }

  function clearMemberSelection() {
    state.selectedContributionIds.clear();
    document.querySelectorAll("#aidMembersChecklistTable .member-row-check").forEach(function (cb) { cb.checked = false; });
    document.querySelectorAll("#aidMembersChecklistTable tbody tr").forEach(function (tr) { tr.classList.remove("selected-row"); });
    var selectAll = getEl("member-select-all");
    if (selectAll) selectAll.checked = false;
    updateMemberBatchBar();
  }

  function clearRightPanel() {
    state.selectedPostId = null;
    state.members = [];
    clearMemberSelection();

    var title = getEl("selectedAidPostTitle");
    if (title) title.innerText = "Member Contribution Ledger";
    var subtitle = getEl("selectedAidPostSubtitle");
    if (subtitle) subtitle.innerText = "No active aid assessment post selected";

    var metrics = getEl("aidPostMetricsBlock");
    if (metrics) metrics.style.display = "none";

    var searchInput = getEl("aidLedgerMemberSearch");
    if (searchInput) {
      searchInput.value = "";
      searchInput.disabled = true;
    }
    var statusFilter = getEl("aidLedgerStatusFilter");
    if (statusFilter) {
      statusFilter.value = "All";
      statusFilter.disabled = true;
    }

    var tbody = getEl("aidMembersTableBody");
    if (tbody) {
      tbody.innerHTML =
        '<tr><td colspan="7" style="text-align:center;color:#90a4ae;padding:30px;">' +
        "Select an assessment record from the left pane to initialize individual tracking checklists." +
        "</td></tr>";
    }
  }

  async function selectPost(postId) {
    state.selectedPostId = postId;

    var post = state.posts.find(function (p) {
      return p.post_id === postId;
    });
    if (!post) return;

    var title = getEl("selectedAidPostTitle");
    if (title)
      title.innerText =
        "Member Contribution Ledger \u2014 " + escapeHtml(post.member_name);

    var subtitle = getEl("selectedAidPostSubtitle");
    if (subtitle)
      subtitle.innerText =
        escapeHtml(post.aid_label || "") +
        " \u2022 " +
        escapeHtml(post.target_month || "");

    try {
      var data = await getJSON(MEMBERS_URL + postId + "/");
      state.members = data.members || [];

      renderMetrics(post, data.post || post);
      renderMembersTable(state.members);
      highlightSelectedCard();

      var searchInput = getEl("aidLedgerMemberSearch");
      if (searchInput) searchInput.disabled = false;
      var statusFilter = getEl("aidLedgerStatusFilter");
      if (statusFilter) statusFilter.disabled = false;
    } catch (e) {
      showToast(e.message || "Failed to load members.", true);
    }
  }

  function renderMetrics(post, postData) {
    var metrics = getEl("aidPostMetricsBlock");
    if (!metrics) return;
    metrics.style.display = "block";

    var typeEl = getEl("aidReadType");
    if (typeEl)
      typeEl.innerText =
        postData.aid_label || post.aid_label || (post.aid_type === "medical_aid" ? "Medical Aid" : "Death Aid");

    var targetEl = getEl("aidReadTotalTarget");
    if (targetEl)
      targetEl.innerText = formatMoneyPHP(postData.total_expected || post.total_expected);

    var quotaEl = getEl("aidReadQuota");
    if (quotaEl) {
      // Exclude EXCLUDED_REQUESTER from count
      var activeCount = state.members.filter(function (m) { return m.status !== "EXCLUDED_REQUESTER"; }).length;
      var expected = parseFloat(postData.total_expected || post.total_expected);
      var perMember = activeCount > 0 ? expected / activeCount : 0;
      quotaEl.innerText = formatMoneyPHP(perMember);
    }

    var countEl = getEl("aidReadActiveCount");
    if (countEl) countEl.innerText = state.members.filter(function (m) { return m.status !== "EXCLUDED_REQUESTER"; }).length;
  }

  function renderMembersTable(members) {
    var tbody = getEl("aidMembersTableBody");
    if (!tbody) return;

    tbody.innerHTML = "";

    // Filter out EXCLUDED_REQUESTER members from display entirely
    var displayMembers = members.filter(function (m) {
      return m.status !== "EXCLUDED_REQUESTER";
    });

    if (!displayMembers || displayMembers.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="7" style="text-align:center;color:#90a4ae;padding:30px;">' +
        "No members found." +
        "</td></tr>";
      return;
    }

    displayMembers.forEach(function (m) {
      var tr = document.createElement("tr");
      var cid = m.contribution_id;
      if (state.selectedContributionIds.has(String(cid))) {
        tr.classList.add("selected-row");
      }
      var statusClass = getStatusBadgeClass(m.status);
      var statusLabel = getStatusLabel(m.status);
      var statusIcon = getStatusIcon(m.status);

      var excludedRequester = m.status === "EXCLUDED_REQUESTER";
      var payBtnDisabled = m.status === "PAID" || m.status === "SKIPPED" || excludedRequester;
      var skipBtnDisabled = m.status === "SKIPPED" || m.status === "PAID" || excludedRequester;

      tr.innerHTML =
        "<td>" +
        '<input type="checkbox" class="member-row-check" value="' + cid + '" ' + (state.selectedContributionIds.has(String(cid)) ? "checked" : "") + (excludedRequester ? " disabled" : "") + ">" +
        "</td>" +
        "<td>" +
        escapeHtml(m.employee_id || "\u2014") +
        "</td>" +
        "<td><strong>" +
        escapeHtml(m.member_name) +
        "</strong></td>" +
        "<td>" +
        escapeHtml(m.department || "\u2014") +
        "</td>" +
        "<td style='font-weight:600;'>" +
        formatMoneyPHP(m.expected_amount) +
        "</td>" +
        "<td>" +
        '<span class="badge-zero ' +
        statusClass +
        '" style="padding:4px 10px;font-size:0.75rem;">' +
        statusIcon +
        " " +
        escapeHtml(statusLabel) +
        "</span>" +
        "</td>" +
        "<td style='text-align:center;white-space:nowrap;'>" +
        '<button class="btn-pay" data-cid="' +
        cid +
        '" ' +
        (payBtnDisabled ? "disabled style='opacity:0.4;cursor:not-allowed;'" : "") +
        ">Pay</button> " +
        '<button class="btn-skip" data-cid="' +
        cid +
        '" ' +
        (skipBtnDisabled ? "disabled style='opacity:0.4;cursor:not-allowed;'" : "") +
        ">Skip</button>" +
        "</td>";

      var cb = tr.querySelector(".member-row-check");
      cb.addEventListener("click", function (e) {
        e.stopPropagation();
        var checked = this.checked;
        if (checked) {
          state.selectedContributionIds.add(String(cid));
        } else {
          state.selectedContributionIds.delete(String(cid));
        }
        tr.classList.toggle("selected-row", checked);
        updateMemberBatchBar();
      });

      if (!excludedRequester) {
        tr.querySelector(".btn-pay").addEventListener("click", function (e) {
          e.stopPropagation();
          handlePay(cid, tr);
        });
        tr.querySelector(".btn-skip").addEventListener("click", function (e) {
          e.stopPropagation();
          handleSkip(cid, tr);
        });
      }
      tbody.appendChild(tr);
    });
    updateMemberBatchBar();
  }

  function disablePaySkipButtons(tr) {
    var payBtn = tr.querySelector(".btn-pay");
    if (payBtn) {
      payBtn.disabled = true;
      payBtn.style.opacity = "0.4";
      payBtn.style.cursor = "not-allowed";
    }
    var skipBtn = tr.querySelector(".btn-skip");
    if (skipBtn) {
      skipBtn.disabled = true;
      skipBtn.style.opacity = "0.4";
      skipBtn.style.cursor = "not-allowed";
    }
  }

  function updatePostProgressFromMembers(postId) {
    if (postId !== state.selectedPostId) return;
    var p = state.posts.find(function (x) { return x.post_id === postId; });
    if (!p || !state.members.length) return;
    var total = 0;
    state.members.forEach(function (m) {
      total += parseFloat(m.paid_amount || 0);
    });
    p.total_collected = total;
    p.collection_rate = p.total_expected > 0 ? Math.round((total / parseFloat(p.total_expected)) * 100) : 0;
    renderCards();
    highlightSelectedCard();
  }

  async function handlePay(contributionId, tr) {
    disablePaySkipButtons(tr);
    try {
      var fd = new FormData();
      fd.append("contribution_id", contributionId);
      var data = await postForm(PAY_URL, fd);

      var m = state.members.find(function (x) { return x.contribution_id === contributionId; });
      if (m) {
        m.status = "PAID";
        m.paid_amount = m.expected_amount;
      }

      var statusCell = tr.querySelector("td:nth-child(6) span");
      if (statusCell) {
        statusCell.className = "badge-zero badge-green";
        statusCell.style.cssText = "padding:4px 10px;font-size:0.75rem;";
        statusCell.innerHTML = "\u{1F7E2} PAID";
      }

      updatePostProgressFromMembers(state.selectedPostId);
      showToast("Member marked as PAID.", false);
    } catch (e) {
      showToast(e.message || "Failed to mark as paid.", true);
    }
  }

  async function handleSkip(contributionId, tr) {
    var m = state.members.find(function (x) { return x.contribution_id === contributionId; });
    var memberName = m ? m.member_name : "this member";
    
    // Add confirmation dialog
    var confirmed = await Swal.fire({
      title: "Skip Payment?",
      html: 'Mark <strong>' + escapeHtml(memberName) + '</strong> as "Won\'t Pay"?<br><br>This will exclude them from the contribution collection.',
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Yes, Skip",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#757575",
      reverseButtons: true,
      customClass: { popup: "swal-custom-animated" },
    }).then(function (result) {
      return result.isConfirmed;
    });
    
    if (!confirmed) return;
    
    disablePaySkipButtons(tr);
    try {
      var fd = new FormData();
      fd.append("contribution_id", contributionId);
      var data = await postForm(SKIP_URL, fd);

      var m = state.members.find(function (x) { return x.contribution_id === contributionId; });
      if (m) {
        m.status = "SKIPPED";
        m.paid_amount = 0;
      }

      var statusCell = tr.querySelector("td:nth-child(6) span");
      if (statusCell) {
        statusCell.className = "badge-zero badge-zero";
        statusCell.style.cssText = "padding:4px 10px;font-size:0.75rem;";
        statusCell.innerHTML = "\u26AB SKIPPED";
      }

      updatePostProgressFromMembers(state.selectedPostId);
      showToast("Member marked as SKIPPED.", false);
    } catch (e) {
      showToast(e.message || "Failed to mark as skipped.", true);
    }
  }

  async function handlePayAll() {
    var ids = Array.from(state.selectedContributionIds);
    if (ids.length === 0) return;
    var swalResult = await Swal.fire({
      title: "Pay " + ids.length + " Contribution(s)?",
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Yes, pay",
      cancelButtonText: "Cancel",
      reverseButtons: true,
    });
    if (!swalResult.isConfirmed) return;
    var done = 0;
    for (var i = 0; i < ids.length; i++) {
      try {
        var fd = new FormData();
        fd.append("contribution_id", ids[i]);
        await postForm(PAY_URL, fd);
        done++;
      } catch (e) {
        showToast("Failed on #" + ids[i] + ": " + e.message, true);
      }
    }
    showToast(done + " of " + ids.length + " marked as PAID.", false);
    if (state.selectedPostId) {
      var data = await getJSON(MEMBERS_URL + state.selectedPostId + "/");
      state.members = data.members || [];
      renderMembersTable(state.members);
      updatePostProgressFromMembers(state.selectedPostId);
    }
    clearMemberSelection();
  }

  async function handleSkipAll() {
    var ids = Array.from(state.selectedContributionIds);
    if (ids.length === 0) return;

    var paidIds = [];
    var skipIds = [];
    ids.forEach(function (id) {
      var m = state.members.find(function (x) { return String(x.contribution_id) === String(id); });
      if (m && (m.status === "PAID" || m.status === "SKIPPED")) {
        paidIds.push(id);
      } else {
        skipIds.push(id);
      }
    });

    if (skipIds.length === 0) {
      showToast("None of the selected items can be skipped (already paid or skipped).", true);
      return;
    }

    var msg = "Skip " + skipIds.length + " contribution(s)?";
    if (paidIds.length > 0) msg += " (" + paidIds.length + " already paid/skipped will be excluded)";
    var swalResult = await Swal.fire({
      title: "Skip Contribution(s)?",
      text: msg,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Yes, skip",
      cancelButtonText: "Cancel",
      reverseButtons: true,
    });
    if (!swalResult.isConfirmed) return;

    var done = 0;
    for (var i = 0; i < skipIds.length; i++) {
      try {
        var fd = new FormData();
        fd.append("contribution_id", skipIds[i]);
        await postForm(SKIP_URL, fd);
        done++;
      } catch (e) {
        showToast("Failed on #" + skipIds[i] + ": " + e.message, true);
      }
    }
    showToast(done + " of " + skipIds.length + " marked as SKIPPED.", false);
    if (state.selectedPostId) {
      var data = await getJSON(MEMBERS_URL + state.selectedPostId + "/");
      state.members = data.members || [];
      renderMembersTable(state.members);
      updatePostProgressFromMembers(state.selectedPostId);
    }
    clearMemberSelection();
  }

  function filterMembers() {
    if (!state.selectedPostId) return;

    var searchVal = (getEl("aidLedgerMemberSearch") || {}).value || "";
    var statusVal = (getEl("aidLedgerStatusFilter") || {}).value || "All";

    var filtered = state.members.filter(function (m) {
      var name = (m.member_name || "").toLowerCase();
      var dept = (m.department || "").toLowerCase();
      var matchesSearch =
        !searchVal ||
        name.indexOf(searchVal.toLowerCase()) !== -1 ||
        dept.indexOf(searchVal.toLowerCase()) !== -1;
      var matchesStatus =
        statusVal === "All" || m.status === statusVal;
      return matchesSearch && matchesStatus;
    });

    renderMembersTable(filtered);
  }

  function bindFilters() {
    var searchInput = getEl("aidPostSearch");
    if (searchInput) {
      searchInput.addEventListener("input", filterPosts);
    }
    var typeFilter = getEl("aidTypeFilter");
    if (typeFilter) {
      typeFilter.addEventListener("change", filterPosts);
    }
    var statusFilter = getEl("aidStatusFilter");
    if (statusFilter) {
      statusFilter.addEventListener("change", filterPosts);
    }

    var memberSearch = getEl("aidLedgerMemberSearch");
    if (memberSearch) {
      memberSearch.addEventListener("input", filterMembers);
    }
    var statusFilter = getEl("aidLedgerStatusFilter");
    if (statusFilter) {
      statusFilter.addEventListener("change", filterMembers);
    }
  }

  async function handleFinishPost(postId) {
    var post = state.posts.find(function (p) { return p.post_id === postId; });
    if (!post) return;

    var skipRemaining = false;

    if (post.collection_rate < 100) {
      var result = await Swal.fire({
        title: "Incomplete Collection",
        text: "Only " + post.collection_rate + "% has been collected. Remaining contributions will be auto-skipped upon President approval. Continue?",
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Yes, submit for approval",
        cancelButtonText: "Cancel",
        reverseButtons: true,
        customClass: {
          popup: "swal-custom-animated",
        },
      });
      if (!result.isConfirmed) return;
      skipRemaining = true;
    }

    try {
      var fd = new FormData();
      fd.append("post_id", postId);
      if (skipRemaining) {
        fd.append("skip_remaining", "true");
      }
      await postForm(FINISH_URL, fd);
      // Treasurer finish now routes to Auditor for verification first
      post.finish_status = "pending_auditor";
      renderCards();
      highlightSelectedCard();
      showToast("Finish request submitted for Auditor verification.", false);
      if (typeof window.normalizeNotifDots === "function") window.normalizeNotifDots();
    } catch (e) {
      showToast(e.message || "Failed to submit finish request.", true);
    }
  }

  function getLatestHistoryPostId() {
    if (!state.historyPosts || state.historyPosts.length === 0) return 0;
    var maxId = 0;
    state.historyPosts.forEach(function (p) {
      if (p.post_id > maxId) maxId = p.post_id;
    });
    return maxId;
  }

  function getStoredHistoryLastViewedId() {
    try { return parseInt(localStorage.getItem("treasurer_history_last_id") || "0", 10); } catch (e) { return 0; }
  }

  function setStoredHistoryLastViewedId(id) {
    try { localStorage.setItem("treasurer_history_last_id", String(id)); } catch (e) {}
  }

  function updateActiveAidGreenDots(count) {
    var folderDot = getEl("aid-claims-green-dot");
    var itemDot = getEl("aid-tracking-green-dot");
    var displayCount = count > 99 ? "99+" : count;
    if (count > 0) {
      if (folderDot) { folderDot.style.display = "inline-flex"; folderDot.textContent = displayCount; }
      if (itemDot) { itemDot.style.display = "inline-flex"; itemDot.textContent = displayCount; }
    } else {
      if (folderDot) folderDot.style.display = "none";
      if (itemDot) itemDot.style.display = "none";
    }
  }

  function updateHistoryNotificationDot() {
    var dot = getEl("history-new-dot");
    if (!dot) return;
    if (!state.historyPosts || state.historyPosts.length === 0) {
      dot.style.display = "none";
      return;
    }
    var latestId = getLatestHistoryPostId();
    var lastViewed = getStoredHistoryLastViewedId();
    var historyTab = getEl("treasurer-aid-history");
    var isActive = historyTab && historyTab.classList.contains("active");

    if (isActive) {
      setStoredHistoryLastViewedId(latestId);
      dot.style.display = "none";
    } else if (latestId > lastViewed) {
      dot.style.display = "inline-flex";
      dot.textContent = "";
    } else {
      dot.style.display = "none";
    }
  }

  async function loadHistoryPosts() {
    try {
      var data = await getJSON(HISTORY_URL);
      state.historyPosts = data.posts || [];
      renderHistoryTable();
      updateHistoryNotificationDot();
    } catch (e) {
      showToast(e.message || "Failed to load history.", true);
    }
  }

  function renderHistoryTable() {
    var tbody = getEl("historyPostsTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    var posts = state.historyPosts;

    if (!posts || posts.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" style="text-align:center;color:#90a4ae;padding:30px;">' +
        "No finished aid tracking posts yet." +
        "</td></tr>";
      return;
    }

    var searchVal = ((getEl("historyPostSearch") || {}).value || "").toLowerCase();
    var typeVal = (getEl("historyTypeFilter") || {}).value || "All";

    var filtered = posts.filter(function (p) {
      var name = (p.member_name || "").toLowerCase();
      var matchesSearch = !searchVal || name.indexOf(searchVal) !== -1;
      var matchesType =
        typeVal === "All" ||
        (typeVal === "Medical" && p.aid_type === "medical_aid") ||
        (typeVal === "Death" && p.aid_type === "death_aid");
      return matchesSearch && matchesType;
    });

    if (filtered.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" style="text-align:center;color:#90a4ae;padding:30px;">' +
        "No posts match your filter." +
        "</td></tr>";
      return;
    }

    filtered.forEach(function (p) {
      var tr = document.createElement("tr");
      tr.style.cursor = "pointer";
      tr.dataset.postId = p.post_id;
      if (state.selectedHistoryPostId === p.post_id) {
        tr.classList.add("selected-row");
      }

      var isMedical = p.aid_type === "medical_aid";
      var typeLabel = isMedical ? "Medical Aid" : "Death Aid";
      var rateColor = "#e53935";
      if (p.collection_rate >= 100) rateColor = "#1b5e20";
      else if (p.collection_rate >= 50) rateColor = "#fbc02d";

      tr.innerHTML =
        "<td><strong>" + escapeHtml(p.member_name || "Unknown") + "</strong></td>" +
        "<td>" + escapeHtml(typeLabel) + "</td>" +
        "<td>" + escapeHtml(p.target_month || "") + "</td>" +
        "<td>" + formatMoneyPHP(p.total_collected) + "</td>" +
        '<td style="font-weight:600;color:' + rateColor + ';">' + p.collection_rate + "%</td>" +
        "<td style='font-size:0.82rem;color:#90a4ae;'>" + escapeHtml(p.updated_at || p.created_at || "") + "</td>";

      tr.addEventListener("click", function () {
        selectHistoryPost(p.post_id);
      });
      tr.addEventListener("mouseenter", function () {
        tr.style.background = "#f0f7f0";
      });
      tr.addEventListener("mouseleave", function () {
        if (state.selectedHistoryPostId !== p.post_id) {
          tr.style.background = "";
        }
      });
      tbody.appendChild(tr);
    });
  }

  async function selectHistoryPost(postId) {
    state.selectedHistoryPostId = postId;

    document.querySelectorAll("#historyPostsTable tbody tr").forEach(function (tr) {
      tr.classList.toggle("selected-row", parseInt(tr.dataset.postId) === postId);
    });

    var post = state.historyPosts.find(function (p) { return p.post_id === postId; });
    if (!post) return;

    var title = getEl("selectedHistoryPostTitle");
    if (title) title.innerText = "Collection Summary \u2014 " + escapeHtml(post.member_name || "");
    var subtitle = getEl("selectedHistoryPostSubtitle");
    if (subtitle) subtitle.innerText = escapeHtml(post.aid_label || "") + " \u2022 " + escapeHtml(post.target_month || "");

    try {
      var data = await getJSON(MEMBERS_URL + postId + "/");
      state.historyMembers = data.members || [];

      renderHistoryMetrics(post, data.post || post);
      renderHistoryMembersTable(state.historyMembers);
    } catch (e) {
      showToast(e.message || "Failed to load post details.", true);
    }
  }

  function renderHistoryMetrics(post, postData) {
    var metrics = getEl("historyPostMetricsBlock");
    if (!metrics) return;
    metrics.style.display = "block";

    var typeEl = getEl("historyReadType");
    if (typeEl) typeEl.innerText = postData.aid_label || post.aid_label || (post.aid_type === "medical_aid" ? "Medical Aid" : "Death Aid");

    var targetEl = getEl("historyReadTotalTarget");
    if (targetEl) targetEl.innerText = formatMoneyPHP(postData.total_expected || post.total_expected);

    var quotaEl = getEl("historyReadQuota");
    if (quotaEl) {
      var count = state.historyMembers.length;
      var expected = parseFloat(postData.total_expected || post.total_expected);
      quotaEl.innerText = count > 0 ? formatMoneyPHP(expected / count) : formatMoneyPHP(0);
    }

    var countEl = getEl("historyReadMemberCount");
    if (countEl) countEl.innerText = state.historyMembers.length;
  }

  function renderHistoryMembersTable(members) {
    var tbody = getEl("historyMembersTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!members || members.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#90a4ae;padding:30px;">' +
        "No members found." +
        "</td></tr>";
      return;
    }

    members.forEach(function (m) {
      var tr = document.createElement("tr");
      var statusClass = getStatusBadgeClass(m.status);
      var statusLabel = getStatusLabel(m.status);
      var statusIcon = getStatusIcon(m.status);

      tr.innerHTML =
        "<td>" + escapeHtml(m.employee_id || "\u2014") + "</td>" +
        "<td><strong>" + escapeHtml(m.member_name) + "</strong></td>" +
        "<td>" + escapeHtml(m.department || "\u2014") + "</td>" +
        "<td style='font-weight:600;'>" + formatMoneyPHP(m.expected_amount) + "</td>" +
        "<td><span class='badge-zero " + statusClass + "' style='padding:4px 10px;font-size:0.75rem;'>" +
        statusIcon + " " + escapeHtml(statusLabel) + "</span></td>";

      tbody.appendChild(tr);
    });
  }

  function filterHistoryPosts() {
    renderHistoryTable();
  }

  function addCardStyles() {
    var styleId = "aid-tracking-dynamic-styles";
    if (getEl(styleId)) return;

    var style = document.createElement("style");
    style.id = styleId;
    style.textContent =
      ".aid-post-card.selected {" +
      "border: 2px solid #1b5e20 !important;" +
      "box-shadow: 0 4px 20px rgba(27,94,32,0.25) !important;" +
      "}" +
      ".btn-pay, .btn-skip, .btn-notify {" +
      "padding: 4px 12px;" +
      "border-radius: 8px;" +
      "border: 1px solid #cfdccc;" +
      "font-size: 0.72rem;" +
      "font-weight: 600;" +
      "cursor: pointer;" +
      "background: #fff;" +
      "transition: all 0.2s;" +
      "font-family: 'Poppins', sans-serif;" +
      "}" +
      ".btn-pay:hover { background: #1b5e20; color: #fff; border-color: #1b5e20; }" +
      ".btn-skip:hover { background: #757575; color: #fff; border-color: #757575; }" +
      ".btn-notify:hover { background: #fbc02d; color: #1b1b1b; border-color: #fbc02d; }" +
      ".btn-pay:disabled:hover, .btn-skip:disabled:hover { background: #fff; color: inherit; }" +
      ".btn-finish-post:hover { background: #e53935 !important; color: #fff !important; }";
    document.head.appendChild(style);
  }

  async function loadPosts() {
    try {
      clearRightPanel();
      var data = await getJSON(POSTS_URL);
      state.posts = data.posts || [];
      renderCards();
      updateActiveAidGreenDots(state.posts.length);
    } catch (e) {
      showToast(e.message || "Failed to load aid posts.", true);
    }
  }

  function init() {
    addCardStyles();
    bindFilters();
    connectWebSocket();
    loadPosts();
    loadHistoryPosts();

    var memberSelectAll = getEl("member-select-all");
    if (memberSelectAll) {
      memberSelectAll.addEventListener("change", function () {
        var checked = this.checked;
        document.querySelectorAll("#aidMembersChecklistTable .member-row-check").forEach(function (cb) {
          cb.checked = checked;
          var cid = cb.value;
          if (checked) state.selectedContributionIds.add(cid);
          else state.selectedContributionIds.delete(cid);
          var row = cb.closest("tr");
          if (row) row.classList.toggle("selected-row", checked);
        });
        updateMemberBatchBar();
      });
    }
    getEl("member-batch-pay")?.addEventListener("click", handlePayAll);
    getEl("member-batch-skip")?.addEventListener("click", handleSkipAll);
    getEl("member-batch-clear")?.addEventListener("click", clearMemberSelection);

    var historySearch = getEl("historyPostSearch");
    if (historySearch) historySearch.addEventListener("input", filterHistoryPosts);
    var historyType = getEl("historyTypeFilter");
    if (historyType) historyType.addEventListener("change", filterHistoryPosts);
  }

  window.AidTracking = {
    init: init,
    loadPosts: loadPosts,
    selectPost: selectPost,
    loadHistoryPosts: loadHistoryPosts,
    selectHistoryPost: selectHistoryPost,
  };

  document.addEventListener("turbo:load", function () {
    addCardStyles();
    bindFilters();
    connectWebSocket();

    var memberSelectAll = getEl("member-select-all");
    if (memberSelectAll) {
      memberSelectAll.addEventListener("change", function () {
        var checked = this.checked;
        document.querySelectorAll("#aidMembersChecklistTable .member-row-check").forEach(function (cb) {
          cb.checked = checked;
          var cid = cb.value;
          if (checked) state.selectedContributionIds.add(cid);
          else state.selectedContributionIds.delete(cid);
          var row = cb.closest("tr");
          if (row) row.classList.toggle("selected-row", checked);
        });
        updateMemberBatchBar();
      });
    }
    getEl("member-batch-pay")?.addEventListener("click", handlePayAll);
    getEl("member-batch-skip")?.addEventListener("click", handleSkipAll);
    getEl("member-batch-clear")?.addEventListener("click", clearMemberSelection);

    var tab = getEl("treasurer-aid-tracking-posts");
    if (tab) {
      if (tab.classList.contains("active")) {
        loadPosts();
      }
      var observer = new MutationObserver(function () {
        if (tab.classList.contains("active")) {
          if (!state.posts || state.posts.length === 0) {
            loadPosts();
          }
        }
      });
      observer.observe(tab, { attributes: true, attributeFilter: ["class"] });
    }

    var historyTab = getEl("treasurer-aid-history");
    if (historyTab) {
      if (historyTab.classList.contains("active")) {
        loadHistoryPosts();
      }
      var historyObserver = new MutationObserver(function () {
        if (historyTab.classList.contains("active")) {
          loadHistoryPosts();
        }
      });
      historyObserver.observe(historyTab, { attributes: true, attributeFilter: ["class"] });
    }

    var historySearch = getEl("historyPostSearch");
    if (historySearch) historySearch.addEventListener("input", filterHistoryPosts);
    var historyType = getEl("historyTypeFilter");
    if (historyType) historyType.addEventListener("change", filterHistoryPosts);

    window._aidObservers = [observer];
    if (historyObserver) window._aidObservers.push(historyObserver);
  });

  document.addEventListener("turbo:before-cache", function () {
    if (window._aidObservers) {
      window._aidObservers.forEach(function (o) { o.disconnect(); });
      window._aidObservers = null;
    }
  });
})();