let _popStateHandler = null;

document.addEventListener("turbo:load", () => {
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("sidebar-toggle-btn");
  const folderTrigger = document.getElementById("folder-trigger");
  const folderLinks = document.getElementById("folder-links");
  const menuItems = document.querySelectorAll(".menu-item");
  const viewport = document.getElementById("module-viewport");
  const viewTitle = document.getElementById("view-title");

  // ==========================================================================
  // DYNAMIC ROLE PREFIX RESOLUTION ENGINE
  // ==========================================================================
  // Looks at your URL path to automatically detect who is logged in.
  // Works perfectly for: /treasurer/..., /auditor/..., and /president/...
  const currentPath = window.location.pathname.toLowerCase();
  let rolePrefix = "/get-treasurer-module"; // Safe fallback default

  if (currentPath.includes("/auditor")) {
    rolePrefix = "/get-auditor-module";
  } else if (currentPath.includes("/president")) {
    rolePrefix = "/get-president-module";
  }

  // ==========================================================================
  // SIDEBAR INTERACTION CONTROLS
  // ==========================================================================
  // Initial state: collapsed (icons visible). Expand on hamburger click.
  if (sidebar) sidebar.classList.add("collapsed");

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");

      // Ensure folder dropdown is hidden when collapsing.
      if (sidebar.classList.contains("collapsed") && folderLinks) {
        folderLinks.classList.remove("open");
      }
    });
  }

  // Subfolder Nav Dropdown Link Matrix Toggle
  if (folderTrigger && folderLinks && sidebar) {
    folderTrigger.addEventListener("click", () => {
      if (sidebar.classList.contains("collapsed")) return;
      folderLinks.classList.toggle("open");
    });
  }

  // Auto-expand sidebar if clicking folder icon while collapsed
  const folderOpenIcon = document.querySelector(
    ".folder-title-wrapper i.fa-folder-open",
  );
  if (folderOpenIcon && folderTrigger && folderLinks && sidebar) {
    folderOpenIcon.addEventListener("click", (e) => {
      e.preventDefault();
      sidebar.classList.remove("collapsed");
      folderLinks.classList.toggle("open");
    });
  }

  // ==========================================================================
  // MODULE PERSISTENCE & RESTORE ENGINE
  // ==========================================================================
  const STORAGE_KEY = "caufa_treasurer_module";
  const allMenuItems = document.querySelectorAll(".menu-item[data-target]");

  function persistModule(moduleName) {
    sessionStorage.setItem(STORAGE_KEY, moduleName);
    if (history.replaceState) {
      history.replaceState({ module: moduleName }, "", `#${moduleName}`);
    }
  }

  function getPersistedModule() {
    const hash = window.location.hash.replace("#", "");
    const stored = sessionStorage.getItem(STORAGE_KEY);
    return hash || stored || "home";
  }

  function setActiveMenuItem(targetModule) {
    allMenuItems.forEach((item) => {
      item.classList.toggle(
        "active",
        item.getAttribute("data-target") === targetModule,
      );
    });
  }

  function updateViewTitle(moduleName) {
    if (!viewTitle) return;
    const menuItem = document.querySelector(
      `.menu-item[data-target="${moduleName}"]`,
    );
    if (menuItem) {
      const text = menuItem.querySelector(".menu-text");
      if (text) viewTitle.textContent = text.textContent.trim();
    }
  }

  function loadModule(moduleName, pushState = true) {
    if (!moduleName || moduleName === currentModule) return;
    currentModule = moduleName;
    persistModule(moduleName);
    setActiveMenuItem(moduleName);

    fetch(`${rolePrefix}/${moduleName}/`)
      .then((response) => {
        if (!response.ok)
          throw new Error(
            "Could not find requested subfolder module components.",
          );
        return response.text();
      })
      .then((htmlContent) => {
        if (viewport) {
          viewport.innerHTML = htmlContent;

          // Re-bind module-specific behaviors after injecting HTML fragments.
          // Inline <script> tags inside fragments are not reliable when using innerHTML.
          // If a fragment defines a known init function, call it here.
          try {
            if (
              moduleName === "medical_aid_request" &&
              window.initMedicalAidRequestModule
            ) {
              window.initMedicalAidRequestModule();
            }
          } catch (e) {
            console.error("Module init hook failed:", e);
          }
        }
        updateViewTitle(moduleName);
      })
      .catch((err) => {
        console.error(err);
        if (viewport)
          viewport.innerHTML =
            '<p style="color: red; padding: 20px;">Routing Error: Module layout swap failed.</p>';
      });
  }

  // ==========================================================================
  // INIT: RESTORE PERSISTED MODULE OR DEFAULT TO HOME
  // ==========================================================================
  const initialModule = getPersistedModule();
  let currentModule = null;
  loadModule(initialModule, false);

  // ==========================================================================
  // SINGLE PAGE FRAGMENT CONTENT FETCH ROUTER ENGINE
  // ==========================================================================
  allMenuItems.forEach((item) => {
    item.addEventListener("click", function (e) {
      const targetModule = this.getAttribute("data-target");

      if (!targetModule) return;

      e.preventDefault();
      loadModule(targetModule, true);
    });
  });

  // Handle browser back/forward buttons
  if (_popStateHandler) window.removeEventListener("popstate", _popStateHandler);
  _popStateHandler = function (e) {
    const module = e.state && e.state.module ? e.state.module : getPersistedModule();
    currentModule = null;
    loadModule(module, false);
  };
  window.addEventListener("popstate", _popStateHandler);
});

// ==========================================================================
// SYSTEM-WIDE TOAST NOTIFICATION MATRIX
// ==========================================================================
function showNotification(message, type = "info") {
  const container = document.getElementById("alert-container");
  const box = document.getElementById("alert-box");
  const msgSpan = document.getElementById("alert-message");
  const iconSpan = document.getElementById("alert-icon");

  if (!container || !box || !msgSpan || !iconSpan) return;

  msgSpan.textContent = message;

  if (type === "success") {
    box.style.backgroundColor = "#16a34a"; // Emerald green
    iconSpan.innerHTML = '<i class="fa-solid fa-circle-check"></i>';
  } else if (type === "error") {
    box.style.backgroundColor = "#dc2626"; // Deep warning red
    iconSpan.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
  } else {
    box.style.backgroundColor = "#2563eb"; // Corporate Info Blue
    iconSpan.innerHTML = '<i class="fa-solid fa-circle-info"></i>';
  }

  container.style.display = "block";

  // Auto clearance execution routine
  setTimeout(() => {
    container.style.display = "none";
  }, 4500);
}
