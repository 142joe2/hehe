(function () {
  "use strict";

  const BULK_COUNT = 5;

  const DEPT_OPTIONS = `
    <option value="">-- Select Department / College --</option>
    <option value="College of Education">College of Education</option>
    <option value="College of Agriculture">College of Agriculture</option>
    <option value="College of Information Technology">Information Technology</option>
    <option value="College of Criminology">Criminology</option>
    <option value="College of Business Management">Business Management</option>
    <option value="Add Option">Add Option</option>
  `;

  async function loadPositionRanks() {
    try {
      const response = await fetch("/api/treasurer/members/position-ranks/options/");
      const data = await response.json();
      if (data.ok && data.ranks) {
        return data.ranks.map(r => `<option value="${r.name}">${r.name}</option>`).join("");
      }
    } catch (error) {
      console.error("Failed to load position ranks:", error);
    }
    return "";
  }

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function generateEmployeeId(fullName) {
    const year = String(new Date().getFullYear()).slice(-2);
    const parts = (fullName || "").trim().split(/\s+/).filter(Boolean);
    const initials = parts.map((p) => p.charAt(0).toUpperCase()).join("");
    return `EMPL-${year}-${initials}`;
  }

  const MEMBER_COLORS = ["#1b5e20", "#1565c0", "#e65100", "#6a1b9a", "#ad1457"];

  function buildBulkMemberBlock(i) {
    const n = i + 1;
    const color = MEMBER_COLORS[i % MEMBER_COLORS.length];
    return `
      <fieldset class="bulk-member-card" style="border-left: 6px solid ${color};">
        <legend style="color: ${color};">Member ${n}</legend>
        <div class="form-grid-3">
          <div class="form-group">
            <label for="bulk_first_name_${i}">First Name</label>
            <input type="text" id="bulk_first_name_${i}" name="member_${i}_first_name" autocomplete="off" placeholder="First name" />
          </div>
          <div class="form-group">
            <label for="bulk_middle_initial_${i}">Middle Initial</label>
            <input type="text" id="bulk_middle_initial_${i}" name="member_${i}_middle_initial" autocomplete="off" placeholder="M" maxlength="1" />
          </div>
          <div class="form-group">
            <label for="bulk_last_name_${i}">Last Name</label>
            <input type="text" id="bulk_last_name_${i}" name="member_${i}_last_name" autocomplete="off" placeholder="Last name" />
          </div>
        </div>
        <div class="form-grid-2">
          <div class="form-group">
            <label for="bulk_username_${i}">Username</label>
            <input type="text" id="bulk_username_${i}" name="member_${i}_username" autocomplete="off" placeholder="Employee/Faculty ID" />
            <p id="bulk_username_status_${i}" class="field-status" style="display:none;font-size:11px;margin-top:4px;"></p>
          </div>
          <div class="form-group">
            <label for="bulk_email_${i}">Email Address</label>
            <input type="email" id="bulk_email_${i}" name="member_${i}_email" autocomplete="off" placeholder="name@example.com" />
            <p id="bulk_email_status_${i}" class="field-status" style="display:none;font-size:11px;margin-top:4px;"></p>
          </div>
        </div>
        <div class="form-grid-2">
          <div class="form-group">
            <label for="bulk_dept_${i}">Department</label>
            <select id="bulk_dept_${i}" name="member_${i}_dept" autocomplete="off">${DEPT_OPTIONS}</select>
          </div>
          <div class="form-group">
            <label for="bulk_pos_${i}">Position / Rank</label>
            <select id="bulk_pos_${i}" name="member_${i}_pos" autocomplete="off" class="position-rank-select">
              <option value="">Loading positions...</option>
            </select>
          </div>
        </div>
        <div class="form-grid-2">
          <div class="form-group">
            <label for="bulk_status_${i}">Membership Type</label>
            <select id="bulk_status_${i}" name="member_${i}_status" autocomplete="off">
              <option value="Permanent" selected>Permanent</option>
              <option value="Temporary">Temporary</option>
            </select>
          </div>
          <div class="form-group">
            <label for="bulk_contact_${i}">Contact Number</label>
            <input type="tel" id="bulk_contact_${i}" name="member_${i}_contact" autocomplete="off" placeholder="e.g., 0917-123-4567" />
          </div>
        </div>
        <div class="form-grid-2">
          <div class="form-group">
            <label for="bulk_amount_${i}">Amount Paid (₱)</label>
            <input type="number" step="0.01" id="bulk_amount_${i}" name="member_${i}_amount" autocomplete="off" value="500.00" placeholder="e.g. 500.00" />
          </div>
          <div class="form-group">
            <label for="bulk_method_${i}">Payment Method</label>
            <select id="bulk_method_${i}" name="member_${i}_method" autocomplete="off">
              <option value="">Select method</option>
              <option value="OTC Cash">OTC Cash</option>
              <option value="Bank Transfer">Bank Transfer</option>
              <option value="GCash">GCash</option>
              <option value="Maya">Maya</option>
            </select>
          </div>
        </div>
        <div class="form-grid-2">
          <div class="form-group">
            <label for="bulk_date_${i}">Payment Date</label>
            <input type="date" id="bulk_date_${i}" name="member_${i}_date" autocomplete="off" />
          </div>
          <div class="form-group">
            <label for="bulk_notes_${i}">Notes</label>
            <textarea id="bulk_notes_${i}" name="member_${i}_notes" autocomplete="off" placeholder="Optional notes" rows="2"></textarea>
          </div>
        </div>
      </fieldset>
    `;
  }

  function setFieldStatus(element, available, message) {
    if (!element) return;
    element.style.display = "block";
    element.style.color = available ? "#388e3c" : "#d32f2f";
    element.textContent = message;
  }

  function isValidEmail(value) {
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailPattern.test(value);
  }

  async function checkAvailability(field, value, statusElement) {
    if (!value) {
      if (statusElement) statusElement.style.display = "none";
      return false;
    }
    if (value.length < 3) {
      if (statusElement) {
        setFieldStatus(
          statusElement,
          false,
          field === "email"
            ? "Please enter a valid email address."
            : "Username must be at least 3 characters.",
        );
      }
      return false;
    }
    if (field === "email" && !isValidEmail(value)) {
      if (statusElement) {
        setFieldStatus(statusElement, false, "Please enter a valid email address.");
      }
      return false;
    }

    try {
      const url = "/api/treasurer/members/add/";
      const formData = new FormData();
      formData.append("check_" + field, value);

      const response = await fetch(url, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": getCSRFToken && getCSRFToken(),
        },
        credentials: "same-origin",
      });
      const data = await response.json();

      if (data.error && data.error.includes("already taken")) {
        setFieldStatus(statusElement, false, `${field.charAt(0).toUpperCase() + field.slice(1)} is already taken.`);
        return false;
      }
      setFieldStatus(statusElement, true, `${field.charAt(0).toUpperCase() + field.slice(1)} is available.`);
      return true;
    } catch (err) {
      if (statusElement) {
        setFieldStatus(statusElement, false, "Unable to verify availability.");
      }
      return false;
    }
  }

  async function renderBulkBlocks() {
    const container = document.getElementById("bulkMemberRows");
    if (!container) return;
    let html = "";
    for (let i = 0; i < BULK_COUNT; i++) html += buildBulkMemberBlock(i);
    container.innerHTML = html;

    // Load position ranks from API
    const positionOptions = await loadPositionRanks();

    for (let i = 0; i < BULK_COUNT; i++) {
      const firstNameInput = document.getElementById(`bulk_first_name_${i}`);
      const middleInitialInput = document.getElementById(`bulk_middle_initial_${i}`);
      const lastNameInput = document.getElementById(`bulk_last_name_${i}`);
      const usernameInput = document.getElementById(`bulk_username_${i}`);
      const usernameStatus = document.getElementById(`bulk_username_status_${i}`);
      const emailInput = document.getElementById(`bulk_email_${i}`);
      const emailStatus = document.getElementById(`bulk_email_status_${i}`);
      const contactInput = document.getElementById(`bulk_contact_${i}`);
      const posSelect = document.getElementById(`bulk_pos_${i}`);

      // Populate position dropdown
      if (posSelect && positionOptions) {
        posSelect.innerHTML = `<option value="">Select Position</option>${positionOptions}`;
      }

      const syncUsername = function () {
        if (!usernameInput) return;
        const firstName = (firstNameInput && firstNameInput.value || "").trim();
        const middle = (middleInitialInput && middleInitialInput.value || "").trim();
        const lastName = (lastNameInput && lastNameInput.value || "").trim();
        const fullName = [firstName, middle, lastName].filter(Boolean).join(" ");
        if (!fullName) return;
        const generated = generateEmployeeId(fullName);
        if (!usernameInput.value || usernameInput.value === usernameInput.dataset.generatedValue) {
          usernameInput.value = generated;
          usernameInput.dataset.generatedValue = generated;
        }
      };

      const debouncedUsernameCheck = debounce(function () {
        if (usernameInput) checkAvailability("username", usernameInput.value.trim(), usernameStatus);
      }, 400);

      const debouncedEmailCheck = debounce(function () {
        if (emailInput) {
          if (!isValidEmail(emailInput.value)) {
            setFieldStatus(emailStatus, false, "Please enter a valid email address.");
          } else {
            checkAvailability("email", emailInput.value.trim(), emailStatus);
          }
        }
      }, 400);

      [firstNameInput, middleInitialInput, lastNameInput].forEach((input) => {
        if (input) input.addEventListener("input", syncUsername);
      });

      if (usernameInput) usernameInput.addEventListener("input", debouncedUsernameCheck);
      if (emailInput) emailInput.addEventListener("input", function () {
        if (emailInput.value && !isValidEmail(emailInput.value)) {
          setFieldStatus(emailStatus, false, "Please enter a valid email address.");
        } else {
          debouncedEmailCheck();
        }
      });

      if (contactInput && typeof window.formatPhoneInput === "function")
        window.formatPhoneInput(contactInput);
    }
  }

  function triggerBulkUpload() {
    const bulkPanel = document.getElementById("bulkEnrollPanel");
    const singlePanel = document.getElementById("singleEnrollPanel");
    if (bulkPanel) {
      bulkPanel.style.display = "block";
      const bulkForm = document.getElementById("bulkMemberForm");
      if (bulkForm) {
        bulkForm.reset();
        renderBulkBlocks();
      }
    }
    if (singlePanel) singlePanel.style.display = "none";
  }

  function triggerSingleUpload() {
    const bulkPanel = document.getElementById("bulkEnrollPanel");
    const singlePanel = document.getElementById("singleEnrollPanel");
    if (bulkPanel) bulkPanel.style.display = "none";
    if (singlePanel) {
      singlePanel.style.display = "block";
      // Clear single form when switching from bulk to single
      const singleForm = document.getElementById("memberForm");
      if (singleForm) {
        singleForm.reset();
        if (typeof FileQueue !== 'undefined' && FileQueue.clear) {
          FileQueue.clear("prof");
        }
      }
    }
  }

  async function handleBulkSubmit(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const btn = form.querySelector('button[type="submit"]');
    const originalBtnText = btn.innerHTML;

    const entries = [];
    for (let i = 0; i < BULK_COUNT; i++) {
      const firstName = (
        document.getElementById(`bulk_first_name_${i}`).value || ""
      ).trim();
      const middleInitial = (
        document.getElementById(`bulk_middle_initial_${i}`).value || ""
      ).trim();
      const lastName = (
        document.getElementById(`bulk_last_name_${i}`).value || ""
      ).trim();
      const username = (
        document.getElementById(`bulk_username_${i}`).value || ""
      ).trim();
      const email = (
        document.getElementById(`bulk_email_${i}`).value || ""
      ).trim();
      const dept = (
        document.getElementById(`bulk_dept_${i}`).value || ""
      ).trim();
      const pos = (
        document.getElementById(`bulk_pos_${i}`).value || ""
      ).trim();
      const status = (
        document.getElementById(`bulk_status_${i}`).value || "Permanent"
      ).trim();
      const contact = (
        document.getElementById(`bulk_contact_${i}`).value || ""
      ).trim();
      const amount = (
        document.getElementById(`bulk_amount_${i}`).value || ""
      ).trim();
      const method = (
        document.getElementById(`bulk_method_${i}`).value || ""
      ).trim();
      const date = (
        document.getElementById(`bulk_date_${i}`).value || ""
      ).trim();
      const notes = (
        document.getElementById(`bulk_notes_${i}`).value || ""
      ).trim();

      const hasData = [
        firstName,
        middleInitial,
        lastName,
        username,
        email,
        dept,
        pos,
        status,
        contact,
        amount,
        method,
        date,
        notes,
      ].some(Boolean);
      if (!hasData) continue;

      if (!firstName || !lastName) {
        return showToast(
          `Member ${i + 1}: First Name and Last Name are required.`,
          true,
        );
      }
      if (!username) {
        return showToast(
          `Member ${i + 1}: Username is required.`,
          true,
        );
      }
      if (!email) {
        return showToast(
          `Member ${i + 1}: Email is required.`,
          true,
        );
      }
      if (email && !email.includes("@")) {
        return showToast(
          `Member ${i + 1}: Email looks invalid.`,
          true,
        );
      }
      if (amount && Number(amount) < 0) {
        return showToast(
          `Member ${i + 1}: Amount Paid must be a positive number.`,
          true,
        );
      }

      entries.push({
        first_name: firstName,
        middle_initial: middleInitial,
        last_name: lastName,
        username: username,
        prof_dept: dept,
        prof_pos: pos,
        prof_contact: contact,
        email: email,
        membership_category: status,
        enrollment_amount: amount,
        payment_method: method,
        payment_date: date,
        notes: notes,
      });
    }

    if (entries.length === 0) {
      return showToast(
        "Please fill in at least one batch member before submitting.",
        true,
      );
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';

    const csrf = getCSRFToken();
    try {
      const resp = await fetch("/api/treasurer/members/batch-add/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ entries }),
        credentials: "same-origin",
      });
      const data = await resp.json().catch(() => ({}));
      const results = (data && data.results) || [];

      const failed = results.filter((r) => !r.ok);
      const succeeded = results.filter((r) => r.ok).length;

      if (typeof window.renderMembersFromBackend === "function") {
        window.renderMembersFromBackend();
      } else if (typeof renderMembersFromBackend === "function") {
        renderMembersFromBackend();
      } else if (typeof window.renderMembersTable === "function") {
        window.renderMembersTable();
      }

      // Clear form after successful batch enrollment
      form.reset();
      renderBulkBlocks(); // Re-render fresh form blocks

      btn.disabled = false;
      btn.innerHTML = originalBtnText;

      const enrolledNames = results.filter((r) => r.ok).map((r) => r.name);
      if (failed.length === 0) {
        Swal.fire({
          title: "Batch Enrollment Complete",
          html:
            `<b>Enrolled ${succeeded} member(s):</b><br><br>` +
            enrolledNames.map((n) => `• ${n}`).join("<br>"),
          icon: "success",
          confirmButtonColor: "#1b5e20",
        });
      } else {
        Swal.fire({
          title: "Batch Enrollment Finished",
          html:
            `<b>${succeeded} enrolled, ${failed.length} failed.</b><br><br>` +
            `<b>Enrolled:</b><br>` +
            enrolledNames.map((n) => `• ${n}`).join("<br>") +
            `<br><br><b>Failed:</b><br>` +
            failed.map((f) => `• ${f.name}: ${f.error}`).join("<br>"),
          icon: "warning",
          confirmButtonColor: "#e53935",
        });
      }
    } catch (err) {
      btn.disabled = false;
      btn.innerHTML = originalBtnText;
      // Don't clear form on error - let user retry with their data
      Swal.fire({
        title: "Error",
        text: "Network/server error while enrolling members.",
        icon: "error",
        confirmButtonColor: "#e53935",
      });
    }
  }

  function debounce(fn, delay) {
    let timer;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(fn, delay);
    };
  }

  function init() {
    const bulkForm = document.getElementById("bulkMemberForm");
    if (bulkForm) {
      // Clear form on page load to prevent browser autocomplete persistence
      // Use setTimeout to ensure DOM is fully loaded and override browser autocomplete
      setTimeout(function() {
        bulkForm.reset();
        renderBulkBlocks(); // Re-render fresh form blocks
      }, 100);
      bulkForm.addEventListener("submit", handleBulkSubmit);
    }
    // Expose toggle handlers for inline onclick attributes
    window.triggerBulkUpload = triggerBulkUpload;
    window.triggerSingleUpload = triggerSingleUpload;
  }

  document.addEventListener("turbo:load", init);
})();
