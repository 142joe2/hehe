(function () {
  "use strict";

  const ACTION_COLORS = {
    CREATED: "#2e7d32",
    RESUBMITTED: "#f9a825",
    VERIFIED: "#1565c0",
    RETURNED: "#c62828",
    APPROVED: "#2e7d32",
    REJECTED: "#c62828",
    RELEASED: "#558b2f",
  };

  function csrfToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function diffObject(oldObj, newObj) {
    if (!oldObj || !newObj) return "";
    const changed = [];
    const allKeys = new Set([
      ...Object.keys(oldObj || {}),
      ...Object.keys(newObj || {}),
    ]);
    allKeys.forEach((key) => {
      if (key === "id") return;
      const o = oldObj[key];
      const n = newObj[key];
      if (String(o) !== String(n)) {
        changed.push(
          `<div style="margin:2px 0;"><span style="color:#666;">${escapeHtml(key)}:</span> ${escapeHtml(String(o ?? "null"))} &rarr; ${escapeHtml(String(n ?? "null"))}</div>`
        );
      }
    });
    return changed.join("");
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderDiffCell(action, oldValues, newValues) {
    if (action === "CREATED") {
      if (!newValues) return "—";
      const keys = Object.keys(newValues).filter((k) => k !== "id").slice(0, 6);
      return keys
        .map((k) => `<div>${escapeHtml(k)}: ${escapeHtml(String(newValues[k] ?? "null"))}</div>`)
        .join("");
    }
    if (action === "RESUBMITTED") {
      return diffObject(oldValues, newValues) || "No field changes detected.";
    }
    if (action === "RETURNED" || action === "REJECTED") {
      if (!newValues) return "—";
      const keys = Object.keys(newValues).filter((k) => k !== "id").slice(0, 6);
      return keys
        .map((k) => `<div>${escapeHtml(k)}: ${escapeHtml(String(newValues[k] ?? "null"))}</div>`)
        .join("");
    }
    if (action === "APPROVED" || action === "VERIFIED") {
      if (!newValues) return "—";
      const keys = Object.keys(newValues).filter((k) => k !== "id").slice(0, 6);
      return keys
        .map((k) => `<div>${escapeHtml(k)}: ${escapeHtml(String(newValues[k] ?? "null"))}</div>`)
        .join("");
    }
    return "—";
  }

  function renderTimeline(entries) {
    const tbody = document.getElementById("auditTrailBody");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!entries || entries.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#757575;padding:20px;">No audit trail entries found.</td></tr>';
      return;
    }

    entries.forEach((entry) => {
      const color = ACTION_COLORS[entry.action] || "#666";
      const timestamp = entry.timestamp
        ? new Date(entry.timestamp).toLocaleString()
        : "—";
      const notes = escapeHtml(entry.notes || "—");
      const diff = renderDiffCell(entry.action, entry.old_values, entry.new_values);

      const tr = document.createElement("tr");
      tr.style.borderBottom = "1px solid #e0e0e0";
      tr.innerHTML = `
        <td style="padding:10px;vertical-align:top;white-space:nowrap;">${timestamp}</td>
        <td style="padding:10px;vertical-align:top;">
          <span style="display:inline-flex;align-items:center;gap:6px;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};"></span>
            <span style="font-weight:600;color:${color};">${escapeHtml(entry.action)}</span>
          </span>
        </td>
        <td style="padding:10px;vertical-align:top;">${escapeHtml(entry.actor_name || "—")}<br><span style="font-size:0.75rem;color:#757575;">${escapeHtml(entry.actor_type || "")}</span></td>
        <td style="padding:10px;vertical-align:top;max-width:200px;">${notes}</td>
        <td style="padding:10px;vertical-align:top;font-size:0.85rem;">${diff}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  async function openAuditTrail(tableName, recordId) {
    const modal = document.getElementById("auditTrailModal");
    const tbody = document.getElementById("auditTrailBody");
    if (!modal || !tbody) return;

    modal.style.display = "flex";
    tbody.innerHTML =
      '<tr><td colspan="5" style="text-align:center;padding:20px;">Loading audit trail...</td></tr>';

    try {
      const resp = await fetch(
        `/api/audit/trail/${encodeURIComponent(tableName)}/${encodeURIComponent(recordId)}/`,
        {
          method: "GET",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": csrfToken(),
          },
        }
      );
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        tbody.innerHTML =
          '<tr><td colspan="5" style="text-align:center;color:#c62828;">Failed to load audit trail.</td></tr>';
        return;
      }
      renderTimeline(data.entries || []);
    } catch (err) {
      tbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#c62828;">Network error while loading audit trail.</td></tr>';
    }
  }

  function closeModal() {
    const modal = document.getElementById("auditTrailModal");
    if (modal) modal.style.display = "none";
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".btn-audit-trail");
    if (!btn) return;

    const tableName = btn.dataset.auditTable;
    const recordId = btn.dataset.auditRecordId;
    if (tableName && recordId) {
      openAuditTrail(tableName, recordId);
    }
  });

  const closeBtn = document.getElementById("closeAuditModal");
  if (closeBtn) {
    closeBtn.addEventListener("click", closeModal);
  }

  const modal = document.getElementById("auditTrailModal");
  if (modal) {
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeModal();
  });
})();
