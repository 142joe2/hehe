(function () {
  "use strict";

  const FORM_ID = "memberForm";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function getFormValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : "";
  }

  async function handleSubmit(e) {
    e.preventDefault();

    const form = document.getElementById(FORM_ID);
    if (!form) return;

    // ==========================================
    // MODULE 1: EXTRACT CORE MEMBER VALUES
    // ==========================================
    const firstName = getFormValue("first_name").trim();
    const middleInitial = getFormValue("middle_initial").trim();
    const lastName = getFormValue("last_name").trim();
    const empId = getFormValue("username").trim();
    const dept = getFormValue("prof_dept").trim();
    const pos = getFormValue("prof_pos").trim();
    const contact = getFormValue("prof_contact").trim();
    const email = getFormValue("email").trim();
    const status = getFormValue("membership_category").trim();

    // Client-side duplicate check
    const dupKey = empId;
    if (
      dupKey &&
      window.db &&
      window.db.members &&
      Array.isArray(window.db.members) &&
      window.db.members.some((m) => String(m.id).trim() === `M-${dupKey}`)
    ) {
      return showToast(
        `Member with Employee/Faculty ID ${dupKey} is already enrolled.`,
        true,
      );
    }

    // Profile Validations
    if (!firstName || !lastName)
      return showToast("First Name and Last Name are required.", true);
    if (!empId) return showToast("Employee/Faculty ID is required.", true);
    if (!status) return showToast("Membership Status is required.", true);
    if (email && !email.includes("@"))
      return showToast("Email looks invalid.", true);

    // Instantiate Unified Payload
    const fd = new FormData();
    fd.append("first_name", firstName);
    fd.append("middle_initial", middleInitial);
    fd.append("last_name", lastName);
    fd.append("username", empId);
    fd.append("prof_dept", dept);
    fd.append("prof_pos", pos);
    fd.append("prof_contact", contact);
    fd.append("email", email);
    fd.append("membership_category", status);
    var linkedOfficer = getFormValue("linked_officer_id");
    if (linkedOfficer) fd.append("officer_user_id", linkedOfficer);
    var profFiles = FileQueue.getFiles("prof");
    if (profFiles.length > 0) fd.append("prof_photo_file", profFiles[0]);

    const csrf = getCSRFToken();

    const submitBtn = form.querySelector("button[type='submit']");
    let originalBtnHTML = "";
    if (submitBtn) {
      originalBtnHTML = submitBtn.innerHTML;
      submitBtn.disabled = true;
    }

    // ==========================================
    // MODULE 4: UNIFIED NETWORK AJAX DESTINATION
    // ==========================================
    (async () => {
      try {
        const resp = await fetch("/api/treasurer/members/add/", {
          method: "POST",
          body: fd,
          headers: csrf ? { "X-CSRFToken": csrf } : {},
          credentials: "same-origin",
        });

        const data = await resp.json().catch(() => ({}));

        if (!resp.ok || !data.ok) {
          const err =
            data && data.error
              ? data.error
              : "Failed to execute streamlined directory registration.";
          showToast(err, true);
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnHTML;
          }
          // Don't clear form on error - let user retry with their data
          return;
        }

        Swal.fire({
          title: "Enrollment Complete",
          text: `Member ${firstName} ${lastName} has been added and recorded.`,
          icon: "success",
          confirmButtonColor: "#1b5e20",
        });

        // Sync window database matrix structure if context array is present
        const activeDb = window.db || (typeof db !== "undefined" ? db : null);
        if (activeDb && Array.isArray(activeDb.members)) {
          const newMember = {
            id: `M-${data.member.member_id}`,
            name: data.member.full_name,
            facultyId:
              data.member.employee_id || data.member.member_type || empId,
            department: dept,
            position: pos,
            contact: contact,
            email: email,
            status: data.member.membership_status,
            type: data.member.member_type || "Member",
            self_enrolled: !!data.member.officer_user_id,
          };
          activeDb.members.push(newMember);
        }

        if (typeof window.saveSystemDatabase === "function") {
          window.saveSystemDatabase();
        } else if (typeof saveSystemDatabase === "function") {
          saveSystemDatabase();
        }

        if (typeof window.renderMembersFromBackend === "function") {
          window.renderMembersFromBackend();
        } else if (typeof renderMembersFromBackend === "function") {
          renderMembersFromBackend();
        } else {
          if (typeof window.renderAllComponents === "function") {
            window.renderAllComponents();
          } else if (typeof renderAllComponents === "function") {
            renderAllComponents();
          } else if (typeof window.renderMembersTable === "function") {
            window.renderMembersTable();
          } else if (typeof renderMembersTable === "function") {
            renderMembersTable();
          }
        }

        // Clear form after successful enrollment
        form.reset();
        if (typeof FileQueue !== 'undefined' && FileQueue.clear) {
          FileQueue.clear("prof");
        }

        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHTML;
        }
      } catch (err) {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHTML;
        }
        // Don't clear form on error - let user retry with their data
        showToast(
          "Network/server error while handling your execution request.",
          true,
        );
      }
    })();
  }

  function init() {
    if (typeof FileQueue !== 'undefined' && FileQueue.init) {
      FileQueue.init("prof", { inputId: "prof_file_input", containerId: "prof_file_queue", maxFiles: 1 });
    }
    loadOfficerDropdown();
    loadPositionRankDropdown();

    var officerSelect = document.getElementById("linked_officer_id");
    if (officerSelect) {
      officerSelect.addEventListener("change", function () {
        var officerId = this.value;
        if (!officerId) return;
        var officers = window.__officersCache || [];
        var officer = officers.find(function (o) { return String(o.id) === String(officerId); });
        if (!officer) return;
        var nameEl = document.getElementById("prof_name");
        var deptEl = document.getElementById("prof_dept");
        var posEl = document.getElementById("prof_pos");
        if (nameEl && !nameEl.value) nameEl.value = officer.full_name || "";
        if (deptEl && !deptEl.value && officer.department_name) deptEl.value = officer.department_name;
        if (posEl && !posEl.value && officer.role) posEl.value = officer.role;
      });
    }

    const form = document.getElementById(FORM_ID);
    if (!form) return;

    // Clear form on page load to prevent browser autocomplete persistence
    // Use setTimeout to ensure DOM is fully loaded and override browser autocomplete
    setTimeout(function() {
      form.reset();
      if (typeof FileQueue !== 'undefined' && FileQueue.clear) {
        FileQueue.clear("prof");
      }
    }, 100);

    window.handleMemberSubmit = handleSubmit;
    form.addEventListener("submit", handleSubmit);
  }

  async function loadOfficerDropdown() {
    var select = document.getElementById("linked_officer_id");
    if (!select) return;
    try {
      var resp = await fetch("/api/treasurer/officers/list/", { credentials: "same-origin" });
      var data = await resp.json();
      if (!data || !data.ok || !data.officers) return;
      window.__officersCache = data.officers || [];
      data.officers.forEach(function (o) {
        var opt = document.createElement("option");
        opt.value = o.id;
        opt.textContent = (o.full_name || "") + " (" + (o.role || "Officer") + ")";
        select.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed to load officers", e);
    }
  }

  async function loadPositionRankDropdown() {
    var select = document.getElementById("prof_pos");
    if (!select) return;
    try {
      var resp = await fetch("/api/treasurer/members/position-ranks/options/", { credentials: "same-origin" });
      var data = await resp.json();
      if (!data || !data.ok || !data.ranks) return;
      
      // Clear existing options except the first one
      select.innerHTML = '<option value="">Select Position</option>';
      
      data.ranks.forEach(function (r) {
        var opt = document.createElement("option");
        opt.value = r.name;
        opt.textContent = r.name;
        select.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed to load position ranks", e);
    }
  }

  document.addEventListener("turbo:load", init);
})();
