(function () {
  function generateEmployeeId(fullName) {
    const year = String(new Date().getFullYear()).slice(-2);
    const parts = (fullName || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    const initials = parts
      .map((p) => p.charAt(0).toUpperCase())
      .join("");
    return `EMPL-${year}-${initials}`;
  }

  function initAutoEmployeeId() {
    const nameInput = document.getElementById("prof_name");
    const idInput = document.getElementById("prof_id");
    if (!nameInput || !idInput) return;

    let manualEdit = false;
    idInput.addEventListener("input", function () {
      manualEdit = true;
    });

    nameInput.addEventListener("input", function () {
      if (manualEdit) return;
      idInput.value = generateEmployeeId(nameInput.value);
    });
  }

  document.addEventListener("turbo:load", initAutoEmployeeId);
})();
