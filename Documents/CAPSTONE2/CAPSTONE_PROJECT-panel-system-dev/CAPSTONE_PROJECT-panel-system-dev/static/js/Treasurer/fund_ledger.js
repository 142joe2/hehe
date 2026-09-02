window.loadLedger = async function loadLedger(page) {
  const direction = document.getElementById("ledgerDirection").value;
  const dateFrom = document.getElementById("ledgerDateFrom").value;
  const dateTo = document.getElementById("ledgerDateTo").value;
  const params = new URLSearchParams({ page, per_page: 20 });
  if (direction) params.set("direction", direction);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  try {
    const resp = await fetch(`/api/fund-ledger/?${params}`);
    const data = await resp.json();
    if (!data.ok) return;
    document.getElementById("ledgerSummary").innerHTML = `
      <span style="color:#28a745;">Inflow: ₱${data.summary.total_in.toFixed(2)}</span>
      <span style="color:#dc3545;">Outflow: ₱${data.summary.total_out.toFixed(2)}</span>
      <span style="color:#1a1a2e;">Balance: ₱${data.summary.balance.toFixed(2)}</span>
    `;
    const tbody = document.getElementById("ledgerTableBody");
    tbody.innerHTML = "";
    data.items.forEach(e => {
      const dirLabel = e.direction === "inflow" ? "In" : "Out";
      const dirClass = e.direction === "inflow" ? "text-success" : "text-danger";
      tbody.innerHTML += `<tr>
        <td>${new Date(e.recorded_at).toLocaleDateString()}</td>
        <td class="${dirClass}"><strong>${dirLabel}</strong></td>
        <td>${e.source_type.replace(/_/g, " ")}</td>
        <td>${e.description}${e.reference_number ? ` (Ref: ${e.reference_number})` : ""}</td>
        <td>₱${e.amount.toFixed(2)}</td>
        <td>${e.recorded_by}</td>
      </tr>`;
    });
    if (data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#6c757d;">No entries found.</td></tr>';
    }
    const pag = document.getElementById("ledgerPagination");
    pag.innerHTML = "";
    if (data.total_pages > 1) {
      for (let p = 1; p <= data.total_pages; p++) {
        pag.innerHTML += `<button class="btn-brand ${p === data.page ? 'btn-brand-primary' : 'btn-brand-secondary'}" onclick="loadLedger(${p})" style="padding:4px 10px;">${p}</button>`;
      }
    }
  } catch (e) { console.error("Failed to load ledger", e); }
};

document.addEventListener("turbo:load", () => loadLedger(1));
