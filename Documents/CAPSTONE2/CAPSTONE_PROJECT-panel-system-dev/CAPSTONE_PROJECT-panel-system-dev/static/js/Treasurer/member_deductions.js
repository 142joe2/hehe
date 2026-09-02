window.loadMemberDropdown = async function loadMemberDropdown() {
  try {
    const resp = await fetch("/api/treasurer/members/list/");
    const data = await resp.json();
    if (data.ok && data.members) {
      const sel = document.getElementById("memberSearch");
      sel.innerHTML = '<option value="">-- Choose a member --</option>';
      data.members.forEach(m => {
        sel.innerHTML += `<option value="${m.member_id}">${m.full_name} (${m.employee_id || "N/A"})</option>`;
      });
    }
  } catch (e) { console.error("Failed to load members", e); }
};

window.fetchMemberDeductions = async function fetchMemberDeductions(memberId) {
  const resultsDiv = document.getElementById("deductionResults");
  const noDiv = document.getElementById("noDeductions");
  const tbody = document.getElementById("deductionTableBody");
  const nameH4 = document.getElementById("deductionMemberName");
  const totalDiv = document.getElementById("deductionTotal");
  resultsDiv.style.display = "none";
  noDiv.style.display = "none";
  if (!memberId) return;
  try {
    const resp = await fetch(`/api/treasurer/member/${memberId}/deductions/`);
    const data = await resp.json();
    if (!data.ok) { alert(data.error || "Error fetching deductions"); return; }
    nameH4.textContent = `Deductions for: ${data.member_name}`;
    totalDiv.textContent = `Total Deducted: ₱${data.total_deducted.toFixed(2)}`;
    tbody.innerHTML = "";
    if (data.count === 0) { noDiv.style.display = "block"; return; }
    data.deductions.forEach(d => {
      tbody.innerHTML += `<tr>
        <td>${d.date ? new Date(d.date).toLocaleDateString() : "\u2014"}</td>
        <td>${d.payroll_period}</td>
        <td>${d.category.replace(/_/g, " ")}</td>
        <td>${d.month_covered || "\u2014"}</td>
        <td>₱${d.amount.toFixed(2)}</td>
        <td>${d.description}</td>
      </tr>`;
    });
    resultsDiv.style.display = "block";
  } catch (e) { console.error("Failed to fetch deductions", e); }
};

document.addEventListener("DOMContentLoaded", loadMemberDropdown);
