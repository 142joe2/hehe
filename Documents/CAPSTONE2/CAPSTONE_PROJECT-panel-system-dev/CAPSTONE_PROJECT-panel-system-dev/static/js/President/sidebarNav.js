function setupCollapsibleSidebar() {
  const sidebar = document.getElementById("appSidebar");
  const headerToggle = document.getElementById("headerSidebarToggle");
  const headerToggleIcon = document.getElementById("headerSidebarToggleIcon");

  // Restore persisted collapsed state (mockup behavior)
  try {
    if (localStorage.getItem("sidebar_collapsed") === "1") {
      sidebar.classList.add("collapsed");
      if (headerToggleIcon) {
        headerToggleIcon.classList.remove("fa-bars");
        headerToggleIcon.classList.add("fa-chevron-left");
      }
      if (headerToggle) headerToggle.setAttribute("title", "Expand Sidebar");
    }
  } catch (e) {}

  if (headerToggle) {
    headerToggle.addEventListener("click", () => {
      const isMobile = window.matchMedia("(max-width: 1200px)").matches;
      if (isMobile) {
        sidebar.classList.toggle("open-mobile");
      } else {
        sidebar.classList.toggle("collapsed");
      }
      const collapsed = sidebar.classList.contains("collapsed");
      const isOpen = sidebar.classList.contains("open-mobile");
      try { localStorage.setItem("sidebar_collapsed", collapsed ? "1" : "0"); } catch (e) {}
      if (headerToggleIcon) {
        if (collapsed || isOpen) {
          headerToggleIcon.classList.remove("fa-bars");
          headerToggleIcon.classList.add("fa-chevron-left");
        } else {
          headerToggleIcon.classList.remove("fa-chevron-left");
          headerToggleIcon.classList.add("fa-bars");
        }
      }
      headerToggle.setAttribute("title", collapsed || isOpen ? "Close Sidebar" : "Open Sidebar");
    });
  }

  // Mockup behavior: clicking a group title collapses/expands its section
  document.querySelectorAll(".sidebar .nav-group-title").forEach((title) => {
    title.style.cursor = "pointer";
    title.style.userSelect = "none";
    title.setAttribute("title", "Toggle section");
    title.addEventListener("click", () => {
      const hidden = title.classList.toggle("collapsed");
      let el = title.nextElementSibling;
      while (el && !el.classList.contains("nav-group-title")) {
        if (el.classList.contains("menu-item") || el.classList.contains("nested-folder")) {
          el.style.display = hidden ? "none" : "";
        }
        el = el.nextElementSibling;
      }
      try { localStorage.setItem("sb_group_" + (title.textContent || "").trim().toLowerCase(), hidden ? "1" : "0"); } catch (e) {}
    });
    // Restore persisted section state
    try {
      var wasCollapsed = localStorage.getItem("sb_group_" + (title.textContent || "").trim().toLowerCase()) === "1";
      if (wasCollapsed) {
        title.classList.add("collapsed");
        let el2 = title.nextElementSibling;
        while (el2 && !el2.classList.contains("nav-group-title")) {
          if (el2.classList.contains("menu-item") || el2.classList.contains("nested-folder")) {
            el2.style.display = "none";
          }
          el2 = el2.nextElementSibling;
        }
      }
    } catch (e) {}
  });
}

function setupFolders() {
  const activeLink = document.querySelector(".menu-item.active");
  if (activeLink) {
    const parentFolder = activeLink.closest(".nested-folder");
    if (parentFolder) {
      const contents = parentFolder.querySelector(".folder-contents");
      const header = parentFolder.querySelector(".folder-header");
      contents.classList.add("open");
      const chevron = header.querySelector(".chevron-icon");
      if (chevron) chevron.style.transform = "rotate(180deg)";
    }
  }
}

function toggleFolder(folderId, headerElement) {
  const sidebar = document.getElementById("appSidebar");
  const hdrIcon = document.getElementById("headerSidebarToggleIcon");
  if (sidebar && sidebar.classList.contains("collapsed")) {
    sidebar.classList.remove("collapsed");
    try { localStorage.setItem("sidebar_collapsed", "0"); } catch (e) {}
    if (hdrIcon) {
      hdrIcon.classList.remove("fa-chevron-left");
      hdrIcon.classList.add("fa-bars");
    }
  }
  // On mobile, ensure sidebar is visible when interacting with folders
  if (sidebar && !sidebar.classList.contains("open-mobile")) {
    const isMobile = window.matchMedia("(max-width: 1200px)").matches;
    if (isMobile) {
      sidebar.classList.add("open-mobile");
      if (hdrIcon) {
        hdrIcon.classList.remove("fa-bars");
        hdrIcon.classList.add("fa-chevron-left");
      }
    }
  }

  const contents = document.getElementById(folderId);
  if (!contents) return;
  const isOpen = contents.classList.contains("open");

  document.querySelectorAll(".folder-contents").forEach((el) => {
    el.classList.remove("open");
    const parentHeader = el.parentElement.querySelector(".chevron-icon");
    if (parentHeader) parentHeader.style.transform = "rotate(0deg)";
  });

  if (!isOpen) {
    contents.classList.add("open");
    const chevron = headerElement.querySelector(".chevron-icon");
    if (chevron) chevron.style.transform = "rotate(180deg)";
  }
}

function restorePersistedModule() {
  let savedTab = "dashboard-overview";
  try {
    savedTab = localStorage.getItem("president_active_tab") || "dashboard-overview";
  } catch (e) {}

  const savedItem = document.querySelector(
    `.menu-item[data-target="${savedTab}"]`,
  );
  if (!savedItem) {
    savedTab = "dashboard-overview";
  }

  setActiveModule(savedTab);

  const parentContents = savedItem
    ? savedItem.closest(".folder-contents")
    : null;
  if (parentContents && !parentContents.classList.contains("open")) {
    const folderHeader =
      parentContents.parentElement &&
      parentContents.parentElement.querySelector(".folder-header");
    if (folderHeader) toggleFolder(parentContents.id, folderHeader);
  }
}

function setActiveModule(target) {
  if (!target) return;

  document.querySelectorAll(".menu-item").forEach((mi) => {
    mi.classList.remove("active");
    if (mi.getAttribute("data-target") === target) {
      mi.classList.add("active");
    }
  });

  document.querySelectorAll(".dashboard-module").forEach((mod) => {
    mod.classList.remove("active");
    if (mod.id === target) {
      mod.classList.add("active");
    }
  });

  const sidebarEl = document.getElementById("appSidebar");
  if (sidebarEl) sidebarEl.classList.remove("open-mobile");

  const activeItem = document.querySelector(
    `.menu-item[data-target="${target}"]`,
  );
  if (activeItem) {
    const titleEl = activeItem.querySelector(".menu-text");
    const titleTarget = document.getElementById("currentModuleTitle");
    if (titleEl && titleTarget) {
      titleTarget.innerText = titleEl.innerText;
    }
  }

  // Fire module init hooks (mockup parity data loaders)
  try {
    if (window.nxModuleInit) window.nxModuleInit(target);
  } catch (e) {}

  try {
    localStorage.setItem("president_active_tab", target);
  } catch (e) {}
}

function setupNavigation() {
  const menuItems = document.querySelectorAll(".menu-item");
  menuItems.forEach((item) => {
    item.addEventListener("click", () => {
      const target = item.getAttribute("data-target");
      if (!target) return;

      setActiveModule(target);

      const parentContents = item.closest(".folder-contents");
      if (parentContents && !parentContents.classList.contains("open")) {
        const folderHeader =
          parentContents.parentElement &&
          parentContents.parentElement.querySelector(".folder-header");
        if (folderHeader) toggleFolder(parentContents.id, folderHeader);
      }
    });
  });

  const mobileToggle = document.getElementById("mobileSidebarToggle");
  if (mobileToggle) {
    mobileToggle.addEventListener("click", () => {
      const sidebarEl = document.getElementById("appSidebar");
      if (sidebarEl) sidebarEl.classList.add("open-mobile");
    });
  }

  restorePersistedModule();
}

// Add event listener to handle reports folder navigation
document.addEventListener("DOMContentLoaded", () => {
  const reportsItems = document.querySelectorAll('[data-target^="reports-"]');
  reportsItems.forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const target = item.getAttribute("data-target");

      setActiveModule(target);
    });
  });
});
