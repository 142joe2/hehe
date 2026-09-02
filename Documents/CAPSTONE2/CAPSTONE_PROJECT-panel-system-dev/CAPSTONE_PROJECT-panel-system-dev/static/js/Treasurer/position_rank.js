(function () {
  "use strict";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function showToast(message, isError = false) {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = "notification-toast";
    toast.style.cssText = `
      background: ${isError ? "#e53935" : "#1b5e20"};
      color: white;
      padding: 16px 20px;
      border-radius: 8px;
      margin-bottom: 12px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      animation: slideIn 0.3s ease-out;
      display: flex;
      align-items: center;
      gap: 12px;
    `;
    toast.innerHTML = `
      <i class="fa-solid ${isError ? "fa-circle-exclamation" : "fa-circle-check"}"></i>
      <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = "slideOut 0.3s ease-out forwards";
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  async function loadPositionRanks() {
    try {
      // Add cache-busting timestamp to ensure fresh data
      const timestamp = new Date().getTime();
      const response = await fetch(`/api/treasurer/members/position-ranks/list/?t=${timestamp}`);
      const data = await response.json();

      if (data.ok) {
        renderPositionRanksTable(data.ranks);
      } else {
        console.error("Failed to load position ranks:", data.error);
        showToast("Failed to load position ranks", true);
      }
    } catch (error) {
      console.error("Error loading position ranks:", error);
      showToast("Error loading position ranks", true);
    }
  }

  function renderPositionRanksTable(ranks) {
    const tbody = document.querySelector("#positionRanksTable tbody");
    if (!tbody) return;

    if (!ranks || ranks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align:center; color:#757575; padding: 20px;">
            No position ranks found. Click "Add Position" to create one.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = ranks.map((rank) => `
      <tr>
        <td style="padding: 12px 8px; font-weight: 500;">${escapeHtml(rank.name)}</td>
        <td style="padding: 12px 8px;">
          <span style="background: rgba(27, 94, 32, 0.1); color: #1b5e20; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 500;">
            ${escapeHtml(rank.category)}
          </span>
        </td>
        <td style="padding: 12px 8px;">
          <span style="background: ${rank.is_active ? "rgba(67, 160, 71, 0.1)" : "rgba(229, 57, 53, 0.1)"}; color: ${rank.is_active ? "#43a047" : "#e53935"}; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 500;">
            ${rank.is_active ? "Active" : "Inactive"}
          </span>
        </td>
        <td style="padding: 12px 8px; color: #666;">${escapeHtml(rank.created_by)}</td>
        <td style="padding: 12px 8px; color: #666; font-size: 0.85rem;">${escapeHtml(rank.created_at ? new Date(rank.created_at).toLocaleDateString() : "N/A")}</td>
        <td style="padding: 12px 8px;">
          <button class="btn-brand btn-brand-secondary" onclick="editPositionRank(${rank.id})" style="padding: 6px 12px; font-size: 0.8rem; border-radius: 6px; margin-right: 4px;">
            <i class="fa-solid fa-pen"></i> Edit
          </button>
          <button class="btn-brand" style="background: #e53935; padding: 6px 12px; font-size: 0.8rem; border-radius: 6px;" onclick="deletePositionRank(${rank.id}, '${escapeHtml(rank.name)}')">
            <i class="fa-solid fa-trash"></i>
          </button>
        </td>
      </tr>
    `).join("");
  }

  function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function openAddPositionModal() {
    const modal = document.getElementById("positionRankModal");
    const form = document.getElementById("positionRankForm");
    const title = document.getElementById("positionRankModalTitle");
    const activeWrapper = document.getElementById("position_active_wrapper");

    if (modal && form && title) {
      form.reset();
      document.getElementById("position_rank_id").value = "";
      title.textContent = "Add Position / Rank";
      activeWrapper.style.display = "none";
      modal.style.display = "flex";
    }
  }

  function editPositionRank(rankId) {
    const modal = document.getElementById("positionRankModal");
    const form = document.getElementById("positionRankForm");
    const title = document.getElementById("positionRankModalTitle");
    const activeWrapper = document.getElementById("position_active_wrapper");

    if (!modal || !form || !title) return;

    // Find the rank data from the table
    const row = document.querySelector(`button[onclick="editPositionRank(${rankId})"]`).closest("tr");
    if (!row) return;

    const cells = row.querySelectorAll("td");
    const name = cells[0].textContent.trim();
    const category = cells[1].textContent.trim();
    const isActive = cells[2].textContent.trim() === "Active";

    document.getElementById("position_rank_id").value = rankId;
    document.getElementById("position_name").value = name;
    document.getElementById("position_category").value = category;
    document.getElementById("position_active").checked = isActive;
    title.textContent = "Edit Position / Rank";
    activeWrapper.style.display = "block";
    modal.style.display = "flex";
  }

  function closePositionRankModal() {
    const modal = document.getElementById("positionRankModal");
    if (modal) modal.style.display = "none";
  }

  async function handlePositionRankSubmit(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const rankId = document.getElementById("position_rank_id").value;
    const isEdit = !!rankId;

    const data = {
      name: document.getElementById("position_name").value.trim(),
      category: document.getElementById("position_category").value,
    };

    if (isEdit) {
      data.is_active = document.getElementById("position_active").checked;
    }

    const csrf = getCSRFToken();
    const url = isEdit
      ? `/api/treasurer/members/position-ranks/${rankId}/update/`
      : "/api/treasurer/members/position-ranks/add/";

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify(data),
        credentials: "same-origin",
      });

      const result = await response.json();

      if (result.ok) {
        showToast(isEdit ? "Position rank updated successfully" : "Position rank added successfully");
        closePositionRankModal();
        loadPositionRanks();
      } else {
        showToast(result.error || "Failed to save position rank", true);
      }
    } catch (error) {
      console.error("Error saving position rank:", error);
      showToast("Error saving position rank", true);
    }
  }

  async function deletePositionRank(rankId, rankName) {
    if (!confirm(`Are you sure you want to deactivate "${rankName}"? This will prevent it from appearing in dropdowns.`)) {
      return;
    }

    const csrf = getCSRFToken();
    try {
      const response = await fetch(`/api/treasurer/members/position-ranks/${rankId}/delete/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrf,
        },
        credentials: "same-origin",
      });

      const result = await response.json();

      if (result.ok) {
        showToast("Position rank deactivated successfully");
        loadPositionRanks();
      } else {
        showToast(result.error || "Failed to deactivate position rank", true);
      }
    } catch (error) {
      console.error("Error deleting position rank:", error);
      showToast("Error deactivating position rank", true);
    }
  }

  function init() {
    const form = document.getElementById("positionRankForm");
    if (form) {
      form.addEventListener("submit", handlePositionRankSubmit);
    }

    // Expose functions globally for onclick handlers
    window.openAddPositionModal = openAddPositionModal;
    window.closePositionRankModal = closePositionRankModal;
    window.editPositionRank = editPositionRank;
    window.deletePositionRank = deletePositionRank;

    // Load positions immediately if section is visible
    const section = document.getElementById("view-position-ranks");
    if (section) {
      const isVisible = section.style.display !== "none" && section.style.visibility !== "hidden" && !section.classList.contains("hidden");
      if (isVisible) {
        loadPositionRanks();
      }

      // Also load when navigation menu items are clicked
      const menuItems = document.querySelectorAll('.menu-item[data-target="view-position-ranks"]');
      menuItems.forEach(item => {
        item.addEventListener('click', () => {
          setTimeout(loadPositionRanks, 100);
        });
      });

      // Fallback: observe style changes
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.target.id === "view-position-ranks" && mutation.target.style.display !== "none") {
            loadPositionRanks();
          }
        });
      });

      observer.observe(section, { attributes: true, attributeFilter: ["style", "class"] });
    }
  }

  document.addEventListener("turbo:load", init);
})();
