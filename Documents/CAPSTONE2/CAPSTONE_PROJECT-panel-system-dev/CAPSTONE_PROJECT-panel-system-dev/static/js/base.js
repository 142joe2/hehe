// Shared sidebar behavior for Treasurer/Auditor/President
// - hamburger toggles collapsed/expanded
// - when collapsed, clicking a top-level icon opens the sidebar and opens its subfolder
// - modules continue to be handled by dashboard.js

document.addEventListener("turbo:load", () => {
  // Dynamic Philippine System Date (updates every load)
  // Looks for any element whose text contains "System Date:".
  const tz = "Asia/Manila";
  const updateSystemDate = () => {
    const els = document.querySelectorAll(".system-date");
    if (!els || els.length === 0) return;

    const now = new Date();
    const formatter = new Intl.DateTimeFormat("en-PH", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    const parts = formatter.formatToParts(now);
    const getPart = (type) => parts.find((p) => p.type === type)?.value;
    const yyyy = getPart("year");
    const mm = getPart("month");
    const dd = getPart("day");

    const phDate = `${yyyy}-${mm}-${dd}`;
    els.forEach((el) => {
      el.textContent = `System Date: ${phDate}`;
    });
  };

  updateSystemDate();

  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  const toggleBtn = document.getElementById("sidebar-toggle-btn");

  // Add initial collapsed state if not already specified
  if (!sidebar.classList.contains("collapsed")) {
    sidebar.classList.add("collapsed");
  }

  // Hamburger
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");

      // Close all open folders when collapsing
      if (sidebar.classList.contains("collapsed")) {
        document
          .querySelectorAll(".folder-contents.open")
          .forEach((el) => el.classList.remove("open"));
      }
    });
  }

  let closeTimer = null;

  function closeSidebarWithDelay(delayMs = 180) {
    if (closeTimer) window.clearTimeout(closeTimer);
    closeTimer = window.setTimeout(() => {
      sidebar.classList.add("collapsed");
      document
        .querySelectorAll(".folder-contents.open")
        .forEach((el) => el.classList.remove("open"));
    }, delayMs);
  }

  function cancelClose() {
    if (closeTimer) window.clearTimeout(closeTimer);
    closeTimer = null;
  }

  // Auto-open on hover anywhere inside the sidebar.
  sidebar.addEventListener("mouseenter", () => {
    cancelClose();
    sidebar.classList.remove("collapsed");
  });

  // Auto-close on click outside with slight delay.
  document.addEventListener("click", (e) => {
    const isInside = sidebar.contains(e.target);
    const isToggle = toggleBtn && toggleBtn.contains(e.target);

    if (!isInside && !isToggle) {
      closeSidebarWithDelay(180);
    }
  });

  // Auto-close when mouse fully leaves sidebar with slight delay.
  sidebar.addEventListener("mouseleave", () => {
    closeSidebarWithDelay(180);
  });

  // Folder toggles (works both expanded/collapsed)
  document
    .querySelectorAll(".nested-folder .folder-header")
    .forEach((header) => {
      header.addEventListener("click", () => {
        const contentId = header.getAttribute("data-content-id");
        const chevronId = header.getAttribute("data-chevron-id");
        const contentEl = contentId ? document.getElementById(contentId) : null;
        const chevronEl = chevronId ? document.getElementById(chevronId) : null;

        // If sidebar collapsed, expand first
        if (sidebar.classList.contains("collapsed")) {
          sidebar.classList.remove("collapsed");
        }

        // Toggle the correct folder dropdown
        if (contentEl) {
          const willOpen = !contentEl.classList.contains("open");
          document
            .querySelectorAll(".nested-folder .folder-contents.open")
            .forEach((el) => {
              if (el !== contentEl) el.classList.remove("open");
            });

          if (willOpen) {
            contentEl.classList.add("open");
          } else {
            contentEl.classList.remove("open");
          }
        }

        if (chevronEl) {
          const isOpen = contentEl
            ? contentEl.classList.contains("open")
            : false;
          chevronEl.style.transform = isOpen
            ? "rotate(180deg)"
            : "rotate(0deg)";
        }
      });
    });

  // When sidebar is collapsed, clicking any menu item with a nested-folder parent should
  // expand sidebar so the corresponding folder can be used.
  // (Handled by the folder-header click above.)

  // Normalize notification dot visibility across the app.
  function normalizeNotifDots() {
    try {
      document.querySelectorAll('.notif-dot, .bell-dot').forEach(function (el) {
        if (!el) return;
        var txt = (el.textContent || '').trim();
        // Treat empty, zero or purely whitespace as no-notification
        if (!txt || txt === '0') {
          el.style.display = 'none';
          el.textContent = '';
        } else {
          // If numeric, cap at 99+
          var n = parseInt(txt, 10);
          if (!isNaN(n)) {
            el.textContent = n > 99 ? '99+' : String(n);
          } else {
            // keep non-numeric text as-is
            el.textContent = txt;
          }
          // ensure it's visible
          el.style.display = 'inline-flex';
        }
      });
    } catch (e) {
      // fail silently
      console.error('normalizeNotifDots error', e);
    }
  }

  // Expose so modules can call after updating counts
  window.normalizeNotifDots = normalizeNotifDots;

  // Run once on load to hide any zero-count badges rendered server-side
  normalizeNotifDots();

});
