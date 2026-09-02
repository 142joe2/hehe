/**
 * Universal Profile Engine Strategy
 * Manages configuration values across Treasurer, Auditor, and President views.
 */
(function initializeUniversalProfileEngine() {
  const profileContainer = document.querySelector(".universal-profile-wrapper");
  if (!profileContainer) return;

  // Determine current layout space role perspective
  const currentRole =
    profileContainer.getAttribute("data-role") || "system_user";

  // Core Document Object Tree Bindings
  const elements = {
    form: document.getElementById("universal-profile-form"),
    avatarInput: document.getElementById("avatar-file-input"),
    avatarDisplay: document.getElementById("profile-avatar-display"),
    displayName: document.getElementById("profile-display-name"),
    title: document.getElementById("profile-title"),
    instructorId: document.getElementById("profile-instructor-id"),
    rank: document.getElementById("profile-rank"),
    college: document.getElementById("profile-college"),
    saveBtn: document.getElementById("save-profile-btn"),
    metaName: document.getElementById("meta-display-name-anchor"),
    metaBadge: document.getElementById("meta-role-badge"),
    metaId: document.getElementById("meta-instructor-id-anchor"),
    syncStatus: document.getElementById("profile-sync-status"),
  };

  // Mock initial storage cache keys matched to role context paths
  const cacheKey = `cauffa_profile_state_${currentRole}`;

  /**
   * Loads saved attributes out of memory context paths
   */
  function loadProfileState() {
    const defaultNames = {
      treasurer: "Prof. Marcus Vance",
      auditor: "Dr. Elena Rostova",
      president: "Dr. Arthur Pendleton",
    };

    const defaultIds = {
      treasurer: "INST-TR-1022",
      auditor: "INST-AUD-4409",
      president: "INST-PRES-0001",
    };

    const savedData = localStorage.getItem(cacheKey);

    if (savedData) {
      const data = JSON.parse(savedData);
      elements.displayName.value = data.displayName || "";
      elements.title.value = data.title || "";
      elements.instructorId.value = data.instructorId || "";
      elements.rank.value = data.rank || "";
      elements.college.value = data.college || "";
      if (data.avatarData) elements.avatarDisplay.src = data.avatarData;
    } else {
      // Apply default structural parameters if clear
      elements.displayName.value =
        defaultNames[currentRole] || "New Faculty User";
      elements.instructorId.value = defaultIds[currentRole] || "INST-2026-XXXX";
      elements.title.value = currentRole === "president" ? "PhD MIT" : "MSc";
      elements.rank.value =
        currentRole === "president" ? "Full Professor" : "Instructor 1";
      elements.college.value =
        "College of Computing Studies (Information Technology)";
    }

    updateUiMetadata();
  }

  /**
   * Mirrors working configurations directly to visual elements
   */
  function updateUiMetadata() {
    const displayValue = elements.displayName.value.trim();
    const titleValue = elements.title.value.trim();

    elements.metaName.textContent = titleValue
      ? `${displayValue}, ${titleValue}`
      : displayValue;
    elements.metaId.textContent = elements.instructorId.value || "---";
    elements.metaBadge.textContent = `${currentRole.toUpperCase()} SCOPE`;
  }

  /**
   * Processes file parameters dynamically to display images instantly
   */
  function handleAvatarProcessing(event) {
    const targetFile = event.target.files[0];
    if (!targetFile) return;

    // Ensure target is valid image structure
    if (!targetFile.type.startsWith("image/")) {
      alert(
        "Security Halt: Target item must be a valid image file formatting pattern.",
      );
      return;
    }

    const systemReader = new FileReader();
    systemReader.onload = function (e) {
      elements.avatarDisplay.src = e.target.result;
      elements.syncStatus.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Photo modified. Awaiting memory save...`;
    };
    systemReader.readAsDataURL(targetFile);
  }

  /**
   * Persists attributes out to localized cache fields
   */
  function saveProfileState() {
    if (!elements.form.checkValidity()) {
      elements.form.reportValidity();
      return;
    }

    const packageData = {
      displayName: elements.displayName.value,
      title: elements.title.value,
      instructorId: elements.instructorId.value,
      rank: elements.rank.value,
      college: elements.college.value,
      avatarData: elements.avatarDisplay.src,
    };

    localStorage.setItem(cacheKey, JSON.stringify(packageData));
    updateUiMetadata();

    // Flash temporary UI validation alert
    elements.syncStatus.innerHTML = `<i class="fa-solid fa-circle-check" style="color: #16a34a;"></i> Configuration saved securely.`;
    elements.syncStatus.style.opacity = "1";

    setTimeout(() => {
      elements.syncStatus.innerHTML = `<i class="fa-solid fa-cloud-check"></i> Profile configuration unified locally.`;
    }, 3000);

    // Structural UI hook matching global app alert architectures
    const systemAlert = document.getElementById("alert-container");
    if (systemAlert) {
      const msg = document.getElementById("alert-message");
      const box = document.getElementById("alert-box");
      if (msg && box) {
        msg.textContent = "Profile modifications successfully stored.";
        box.style.background = "#16a34a";
        systemAlert.style.display = "block";
        setTimeout(() => (systemAlert.style.display = "none"), 2500);
      }
    } else {
      alert("Profile configuration synchronized successfully.");
    }
  }

  // Connect event binding arrays
  elements.avatarInput.addEventListener("change", handleAvatarProcessing);
  elements.saveBtn.addEventListener("click", saveProfileState);

  // Initial Bootstrap Execution Run
  loadProfileState();
})();
