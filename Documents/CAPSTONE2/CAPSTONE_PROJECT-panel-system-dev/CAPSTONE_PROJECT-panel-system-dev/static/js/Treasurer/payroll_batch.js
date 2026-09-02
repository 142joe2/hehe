const EXPECTED_DUES = 50;
const FEE_AMOUNT = 100;
let selectedMonths = [];
let selectedAidPosts = [];

function getPerMemberAmount() {
  let pm = 0;
  if (document.getElementById('header-cat-md').checked) pm += EXPECTED_DUES;
  if (document.getElementById('header-cat-mf').checked) pm += FEE_AMOUNT;
  if (document.getElementById('header-cat-ac').checked) pm += parseFloat(document.getElementById('header-aid-amount').value) || 0;
  return pm;
}

function loadPayrollBatches() {
  fetch('/api/treasurer/payroll-batches/list/')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('payroll-batch-table-body');
      if (!data.batches || data.batches.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#6c757d;">No payroll batches yet.</td></tr>';
        return;
      }
      tbody.innerHTML = data.batches.map(b => `
        <tr>
          <td>${b.payroll_period}</td>
          <td>₱${parseFloat(b.total_amount).toFixed(2)}</td>
          <td>${b.member_count}</td>
          <td><span class="badge" style="background:#ffc107;padding:2px 8px;border-radius:4px;">${b.status}</span></td>
          <td>${b.recorded_by} <small>${new Date(b.recorded_at).toLocaleDateString()}</small></td>
          <td>${b.verified_by || '—'}</td>
          <td>${b.approved_by || '—'}</td>
          <td>
            <button class="btn-brand btn-brand-secondary" onclick="viewBatch(${b.batch_id})" style="padding:2px 8px;font-size:12px;">View</button>
            ${b.status === 'Pending' || b.status === 'Returned for Revision' ? `
              <button class="btn-brand btn-brand-primary" onclick="editBatch(${b.batch_id})" style="padding:2px 8px;font-size:12px;">Edit</button>
              <button class="btn-brand" style="background:#dc3545;padding:2px 8px;font-size:12px;" onclick="deleteBatch(${b.batch_id})">Del</button>
            ` : ''}
          </td>
        </tr>
      `).join('');
    });
}

function resetBatchForm() {
  document.getElementById('batch-id').value = '';
  document.getElementById('payroll-period').value = '';
  document.getElementById('hardcopy-ref').value = '';
  document.getElementById('batch-notes').value = '';
  document.getElementById('header-cat-md').checked = false;
  document.getElementById('header-cat-mf').checked = false;
  document.getElementById('header-cat-ac').checked = false;
  document.getElementById('header-aid-amount').value = '0';
  document.getElementById('header-fund-impact').value = 'inflow';
  document.getElementById('header-month-group').style.display = 'none';
  document.getElementById('header-aidpost-group').style.display = 'none';
  document.getElementById('header-aid-amount-group').style.display = 'none';
  selectedMonths = [];
  selectedAidPosts = [];
  renderMonthGrid();
  renderMonthTags();
  renderAidPostTags();
  document.querySelectorAll('.member-checkbox').forEach(cb => cb.checked = false);
  updateMemberCount();
  recalcTotals();
  document.getElementById('view-payroll-batches').scrollIntoView({behavior:'smooth',block:'start'});
}

function closeBatchDetailModal() { document.getElementById('batch-detail-modal').style.display = 'none'; }

function toggleSelectAll(checked) {
  document.querySelectorAll('.member-checkbox').forEach(cb => cb.checked = checked);
  updateMemberCount();
  recalcTotals();
}

function updateMemberCount() {
  const checked = document.querySelectorAll('.member-checkbox:checked').length;
  document.getElementById('selected-member-count').textContent = checked;
  document.getElementById('batch-member-count').textContent = checked + ' selected';
}

function onHeaderCategoryChange() {
  const md = document.getElementById('header-cat-md').checked;
  const mf = document.getElementById('header-cat-mf').checked;
  const ac = document.getElementById('header-cat-ac').checked;
  document.getElementById('header-month-group').style.display = md ? 'block' : 'none';
  document.getElementById('header-aidpost-group').style.display = ac ? 'block' : 'none';
  document.getElementById('header-aid-amount-group').style.display = ac ? 'block' : 'none';
  if (!md) { selectedMonths = []; renderMonthGrid(); renderMonthTags(); }
  if (!ac) { selectedAidPosts = []; renderAidPostTags(); document.getElementById('header-aid-amount').value = '0'; }
  if (md) { populateYearDropdown(); renderMonthGrid(); }
  recalcTotals();
}

function recalcTotals() {
  const pm = getPerMemberAmount();
  const checked = document.querySelectorAll('.member-checkbox:checked').length;
  const impact = document.getElementById('header-fund-impact').value;
  const total = pm * checked;
  document.getElementById('per-member-amount').textContent = pm.toFixed(2);
  document.getElementById('batch-total').textContent = total.toFixed(2);
  document.getElementById('fund-impact-total').textContent = impact === 'inflow' ? total.toFixed(2) : '0.00';
}

function toggleMonth(val) {
  const idx = selectedMonths.indexOf(val);
  if (idx >= 0) { selectedMonths.splice(idx, 1); }
  else { selectedMonths.push(val); selectedMonths.sort(); }
  renderMonthGrid();
  renderMonthTags();
  recalcTotals();
}

function populateYearDropdown() {
  const sel = document.getElementById('header-month-year');
  if (!sel) return;
  const currentYear = new Date().getFullYear();
  sel.innerHTML = '';
  for (let y = currentYear - 5; y <= currentYear + 3; y++) {
    const opt = document.createElement('option');
    opt.value = y;
    opt.textContent = y;
    sel.appendChild(opt);
  }
  sel.value = currentYear;
}

function onHeaderMonthYearChange() {
  const year = parseInt(document.getElementById('header-month-year').value);
  selectedMonths = selectedMonths.filter(m => m.startsWith(year + '-'));
  renderMonthGrid();
  renderMonthTags();
  recalcTotals();
}

function renderMonthGrid() {
  const container = document.getElementById('header-month-grid');
  if (!container) return;
  const yearSelect = document.getElementById('header-month-year');
  if (!yearSelect) return;
  const year = parseInt(yearSelect.value) || new Date().getFullYear();
  const months = [];
  for (let i = 0; i < 12; i++) {
    const val = year + '-' + String(i + 1).padStart(2, '0');
    const d = new Date(year, i, 1);
    const label = d.toLocaleDateString('en-US', { month: 'short' });
    months.push({ val, label });
  }
  container.innerHTML = months.map(m =>
    `<div class="month-grid-item${selectedMonths.includes(m.val)?' selected':''}" onclick="toggleMonth('${m.val}')">${m.label}</div>`
  ).join('');
}

function removeMonthTag(monthStr) {
  selectedMonths = selectedMonths.filter(m => m !== monthStr);
  renderMonthTags();
  recalcTotals();
}

function renderMonthTags() {
  const container = document.getElementById('header-month-tags');
  if (selectedMonths.length === 0) {
    container.innerHTML = '<span style="font-size:12px;color:#adb5bd;">No months selected</span>';
    return;
  }
  container.innerHTML = selectedMonths.map(m =>
    `<span class="tag-pill">${escapeHtml(m)}<span class="tag-remove" onclick="removeMonthTag('${m}')">&times;</span></span>`
  ).join('');
}

function addAidPostTag() {
  const sel = document.getElementById('header-aidpost-select');
  if (!sel.value) { alert('Select an aid post'); return; }
  if (selectedAidPosts.some(p => p.post_id === sel.value)) { alert('Aid post already added'); return; }
  const label = sel.options[sel.selectedIndex].text;
  selectedAidPosts.push({ post_id: sel.value, label: label });
  renderAidPostTags();
  sel.value = '';
  recalcTotals();
}

function removeAidPostTag(postId) {
  selectedAidPosts = selectedAidPosts.filter(p => p.post_id !== postId);
  renderAidPostTags();
  recalcTotals();
}

function renderAidPostTags() {
  const container = document.getElementById('header-aidpost-tags');
  if (selectedAidPosts.length === 0) {
    container.innerHTML = '<span style="font-size:12px;color:#adb5bd;">No aid posts selected</span>';
    return;
  }
  container.innerHTML = selectedAidPosts.map(p =>
    `<span class="tag-pill">${escapeHtml(p.label)}<span class="tag-remove" onclick="removeAidPostTag('${p.post_id}')">&times;</span></span>`
  ).join('');
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function loadMemberList() {
  const tbody = document.getElementById('member-checklist-body');
  tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#6c757d;padding:20px;">Loading members...</td></tr>';
  fetch('/api/treasurer/members/list/')
    .then(r => r.json())
    .then(data => {
      if (!data.ok || !data.members) return;
      tbody.innerHTML = '';
      data.members.forEach((m, idx) => {
        const rowId = 'mrow-' + idx;
        const tr = document.createElement('tr');
        tr.id = rowId;
        tr.innerHTML = `
          <td><input type="checkbox" class="member-checkbox" data-member-id="${m.member_id}" onchange="updateMemberCount();recalcTotals();"></td>
          <td><strong>${m.full_name}</strong><br><small style="color:#6c757d;">${m.employee_id||''} ${m.department||''}</small></td>
          <td><button type="button" class="btn-brand btn-brand-secondary" style="padding:2px 6px;font-size:11px;" onclick="showMemberDetails(${m.member_id})">👁️</button></td>
        `;
        tbody.appendChild(tr);
      });
      fetch('/api/treasurer/approved-aid-posts/').catch(()=>{}).then(r=>r.ok?r.json():{posts:[]}).then(data => {
        const sel = document.getElementById('header-aidpost-select');
        sel.innerHTML = '<option value="">— Select an aid post —</option>';
        (data.posts||[]).forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.post_id;
          opt.textContent = (p.aid_label||p.aid_type)+' — '+(p.member_name||'')+' (₱'+p.total_expected+')';
          sel.appendChild(opt);
        });
      });
    });
}

function showMemberDetails(memberId) {
  if (typeof Swal === 'undefined') { alert('SweetAlert2 not loaded'); return; }
  fetch('/api/treasurer/member/'+memberId+'/details/')
    .then(r => r.json())
    .then(data => {
      if (!data.ok) { alert('Error loading details'); return; }
      let missedHtml = '';
      if (data.missed_months && data.missed_months.length > 0) {
        missedHtml = data.missed_months.map(m => {
          const d = new Date(m+'-01');
          return '<span style="display:inline-block;padding:4px 8px;margin:3px;background:#fff3cd;border-radius:4px;font-size:12px;">'+d.toLocaleDateString('en-US',{month:'short',year:'numeric'})+'</span>';
        }).join('');
      } else {
        missedHtml = '<span style="color:#28a745;">All months paid ✓</span>';
      }
      let aidHtml = '';
      if (data.active_aid_obligations && data.active_aid_obligations.length > 0) {
        aidHtml = '<table style="width:100%;border-collapse:collapse;font-size:13px;">' +
          '<tr style="background:#f8f9fa;"><th style="padding:4px 8px;text-align:left;">Type</th><th style="padding:4px 8px;text-align:right;">Expected</th><th style="padding:4px 8px;text-align:right;">Paid</th></tr>' +
          data.active_aid_obligations.map(a => '<tr><td style="padding:4px 8px;">'+a.aid_type+'</td><td style="padding:4px 8px;text-align:right;">₱'+a.expected_amount.toFixed(2)+'</td><td style="padding:4px 8px;text-align:right;">₱'+a.paid_amount.toFixed(2)+'</td></tr>').join('') +
          '</table>';
      } else {
        aidHtml = '<span style="color:#28a745;">No active aid obligations ✓</span>';
      }
      Swal.fire({
        title: data.full_name,
        html: `
          <div style="text-align:left;">
            <p><strong>ID:</strong> ${data.employee_id || 'N/A'} | <strong>Status:</strong> ${data.membership_status}</p>
            <hr style="margin:8px 0;">
            <h5 style="margin:8px 0 4px;">Missed Monthly Dues (${data.missed_months ? data.missed_months.length : 0})</h5>
            <div>${missedHtml}</div>
            <hr style="margin:8px 0;">
            <h5 style="margin:8px 0 4px;">Active Aid Obligations</h5>
            <div>${aidHtml}</div>
            <hr style="margin:8px 0;">
            <p><strong>Membership Fee:</strong> ${data.membership_fee_paid ? '✅ Paid' : '❌ Unpaid'} (₱${data.membership_fee_amount})</p>
            <p><strong>Expected Dues:</strong> ₱${data.expected_dues_amount}/month</p>
          </div>
        `,
        width: 500,
      });
    });
}

function gatherDeductions() {
  const deductions = [];
  const md = document.getElementById('header-cat-md').checked;
  const mf = document.getElementById('header-cat-mf').checked;
  const ac = document.getElementById('header-cat-ac').checked;
  const fundImpact = document.getElementById('header-fund-impact').value;
  const aidAmount = parseFloat(document.getElementById('header-aid-amount').value) || 0;

  document.querySelectorAll('.member-checkbox:checked').forEach(cb => {
    const memberId = parseInt(cb.getAttribute('data-member-id'));

    if (md) {
      const months = selectedMonths.length > 0 ? selectedMonths : [''];
      months.forEach(monthVal => {
        deductions.push({ member_id: memberId, category: 'monthly_dues', amount: EXPECTED_DUES, month_covered: monthVal, aid_tracking_post_id: null, fund_impact: fundImpact, notes: '' });
      });
    }
    if (mf) {
      deductions.push({ member_id: memberId, category: 'membership_fee', amount: FEE_AMOUNT, month_covered: '', aid_tracking_post_id: null, fund_impact: fundImpact, notes: '' });
    }
    if (ac && aidAmount > 0) {
      const posts = selectedAidPosts.length > 0 ? selectedAidPosts : [null];
      posts.forEach(post => {
        deductions.push({ member_id: memberId, category: 'aid_contribution', amount: aidAmount, month_covered: '', aid_tracking_post_id: post ? post.post_id : null, fund_impact: fundImpact, notes: '' });
      });
    }
  });
  return deductions;
}

function saveOrUpdateBatch() {
  const batchId = document.getElementById('batch-id').value;
  const deductions = gatherDeductions();
  if (!deductions.length) { alert('Select at least one member and enable at least one deduction type.'); return; }
  if (!document.getElementById('payroll-period').value) { alert('Select a payroll period.'); return; }
  const url = batchId ? '/api/treasurer/payroll-batches/'+batchId+'/edit/' : '/api/treasurer/payroll-batches/create/';
  fetch(url, {
    method: 'POST',
    headers: {'Content-Type':'application/json', 'X-CSRFToken': getCSRFToken()},
    body: JSON.stringify({
      payroll_period: document.getElementById('payroll-period').value,
      hardcopy_reference: document.getElementById('hardcopy-ref').value,
      notes: document.getElementById('batch-notes').value,
      deductions: deductions,
    }),
  }).then(r=>r.json()).then(data => {
    if (data.ok) { resetBatchForm(); loadPayrollBatches(); alert('Payroll batch saved!'); }
    else alert(data.error||'Error saving batch');
  }).catch(e=>{console.error('Save batch failed',e);alert('Error saving batch');});
}

function viewBatch(batchId) {
  fetch('/api/treasurer/payroll-batches/'+batchId+'/').then(r=>r.json()).then(data => {
    if (!data.ok) { alert(data.error); return; }
    const b = data.batch;
    document.getElementById('batch-detail-content').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px;">
        <div><strong>Period:</strong> ${b.payroll_period}</div>
        <div><strong>Total:</strong> ₱${parseFloat(b.total_amount).toFixed(2)}</div>
        <div><strong>Members:</strong> ${b.member_count}</div>
        <div><strong>Status:</strong> ${b.status}</div>
        <div><strong>Recorded By:</strong> ${b.recorded_by}</div>
        <div><strong>Hardcopy Ref:</strong> ${b.hardcopy_reference||'—'}</div>
      </div>
      ${b.notes ? '<div style="margin-bottom:12px;"><strong>Notes:</strong> '+b.notes+'</div>' : ''}
      <h4>Deductions</h4>
      <div class="table-container">
        <table class="custom-table" style="width:100%;">
          <thead><tr><th>Member</th><th>Category</th><th>Amount</th><th>Impact</th></tr></thead>
          <tbody>${(data.deductions||[]).map(d => '<tr><td>'+d.member_name+'</td><td>'+d.category+'</td><td>₱'+parseFloat(d.amount).toFixed(2)+'</td><td>'+(d.fund_impact==='inflow'?'Inflow':'None')+'</td></tr>').join('')}</tbody>
        </table>
      </div>
    `;
    document.getElementById('batch-detail-modal').style.display = 'block';
  });
}

function editBatch(batchId) {
  fetch('/api/treasurer/payroll-batches/'+batchId+'/').then(r=>r.json()).then(data => {
    if (!data.ok) { alert(data.error); return; }
    const b = data.batch;
    resetBatchForm();
    document.getElementById('batch-id').value = b.batch_id;
    document.getElementById('payroll-period').value = b.payroll_period;
    document.getElementById('hardcopy-ref').value = b.hardcopy_reference||'';
    document.getElementById('batch-notes').value = b.notes||'';
    const cats = { md: false, mf: false, ac: false };
    let aidAmt = 0, fundImp = 'inflow';
    const monthSet = new Set();
    const aidPostSet = new Set();
    (data.deductions||[]).forEach(d => {
      if (d.category === 'monthly_dues') { cats.md = true; if (d.month_covered) monthSet.add(d.month_covered); }
      if (d.category === 'membership_fee') cats.mf = true;
      if (d.category === 'aid_contribution') { cats.ac = true; aidAmt = parseFloat(d.amount) || 0; if (d.aid_tracking_post_id) aidPostSet.add(d.aid_tracking_post_id); }
      if (d.fund_impact) fundImp = d.fund_impact;
    });
    document.getElementById('header-cat-md').checked = cats.md;
    document.getElementById('header-cat-mf').checked = cats.mf;
    document.getElementById('header-cat-ac').checked = cats.ac;
    document.getElementById('header-aid-amount').value = aidAmt || 0;
    document.getElementById('header-fund-impact').value = fundImp;
    selectedMonths = Array.from(monthSet).sort();
    renderMonthGrid();
    renderMonthTags();
    fetch('/api/treasurer/approved-aid-posts/').catch(()=>{}).then(r=>r.ok?r.json():{posts:[]}).then(postsData => {
      const postMap = {};
      (postsData.posts||[]).forEach(p => { postMap[p.post_id] = p; });
      selectedAidPosts = Array.from(aidPostSet).map(id => {
        const p = postMap[id];
        return { post_id: id, label: p ? (p.aid_label||p.aid_type)+' — '+(p.member_name||'')+' (₱'+p.total_expected+')' : id };
      });
      renderAidPostTags();
    });
    onHeaderCategoryChange();
    setTimeout(() => {
      (data.deductions||[]).forEach(d => {
        const cb = document.querySelector(`.member-checkbox[data-member-id="${d.member_id}"]`);
        if (cb) cb.checked = true;
      });
      updateMemberCount();
      recalcTotals();
    }, 500);
    document.getElementById('view-payroll-batches').scrollIntoView({behavior:'smooth',block:'start'});
  });
}

function deleteBatch(batchId) {
  if (!confirm('Delete this payroll batch?')) return;
  fetch('/api/treasurer/payroll-batches/'+batchId+'/delete/', {method:'POST', headers:{'X-CSRFToken': getCSRFToken()}})
    .then(r=>r.json()).then(data => { if(data.ok) { loadPayrollBatches(); alert('Batch deleted.'); } else alert(data.error||'Error'); });
}

document.addEventListener('turbo:load', function() {
  if (document.getElementById('payroll-batch-table-body')) { loadPayrollBatches(); loadMemberList(); }
  renderMonthGrid();
  document.getElementById('header-aidpost-add-btn')?.addEventListener('click', addAidPostTag);
  const aidpostSel = document.getElementById('header-aidpost-select');
  if (aidpostSel) {
    aidpostSel.addEventListener('keydown', function(e) { if (e.key === 'Enter') { e.preventDefault(); addAidPostTag(); } });
  }
});
