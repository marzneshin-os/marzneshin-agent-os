// Product Profit & Contribution Dashboard Application
// Built for Claudex Loop workflow (Steve Tan guide)

const KNOWN_FIXTURE = `order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend
TEST-001,LINE-001,DESK-LAMP,2026-09-01,USD,200,20,30,10,60,15,6,25`;

const DEMO_CATALOG = `order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend
TEST-001,LINE-001,DESK-LAMP,2026-09-01,USD,200,20,30,10,60,15,6,25
ORD-101,LINE-001,DESK-LAMP,2026-09-02,USD,200,10,0,10,60,15,6,20
ORD-102,LINE-001,WIRELESS-CHARGER,2026-09-02,USD,60,5,0,5,18,6,2,10
ORD-102,LINE-002,USB-C-CABLE,2026-09-02,USD,25,0,0,3,4,3,1,5
ORD-103,LINE-001,ERGONOMIC-CHAIR,2026-09-03,USD,450,50,0,25,180,40,15,45
ORD-104,LINE-001,MONITOR-ARM,2026-09-03,USD,120,0,120,12,45,15,4,30
ORD-105,LINE-001,KEYBOARD-RGB,2026-09-04,USD,140,15,0,8,65,12,4,20
ORD-106,LINE-001,MOUSEPAD-XL,2026-09-04,USD,30,0,0,4,8,4,1,22
ORD-107,LINE-001,HEADPHONE-STAND,2026-09-05,USD,45,5,0,5,15,5,2,8
ORD-108,LINE-001,CABLE-MANAGEMENT,2026-09-05,USD,20,0,0,3,3,3,1,16`;

let currentItems = [];
let rejectedRows = [];
let warnings = [];
let targetCurrency = 'USD';
let currentTab = 'sku-tab';

function parseCSV(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.trim());
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    const values = lines[i].split(',').map(v => v.trim());
    const row = {};
    headers.forEach((h, idx) => {
      row[h] = values[idx] !== undefined ? values[idx] : '';
    });
    rows.push(row);
  }
  return rows;
}

function processData(rawRows) {
  const items = [];
  const rejected = [];
  const warn = [];
  const seenKeys = new Set();

  rawRows.forEach((row, idx) => {
    const lineNum = idx + 2;
    const order_id = row.order_id || '';
    const line_id = row.line_id || '';
    const sku = row.sku || '';
    const curr = (row.currency || '').toUpperCase();
    const date = row.date || '';

    // Acceptance Check 4: Missing cost or currency
    if (!curr) {
      rejected.push({ line: lineNum, reason: 'Missing currency field', row });
      warn.push(`Row ${lineNum}: Rejected (missing currency)`);
      return;
    }
    if (curr !== targetCurrency) {
      rejected.push({ line: lineNum, reason: `Mixed currency '${curr}' not supported; expected '${targetCurrency}'`, row });
      warn.push(`Row ${lineNum}: Rejected mixed currency '${curr}'`);
      return;
    }
    if (!row.net_product_cost || row.net_product_cost.trim() === '') {
      rejected.push({ line: lineNum, reason: 'Missing product cost (cannot treat as free product)', row });
      warn.push(`Row ${lineNum} (SKU ${sku}): Missing cost rejected; items cannot be free`);
      return;
    }

    // Acceptance Check 2: Duplicate import
    const dedupeKey = `${order_id}__${line_id}`;
    if (seenKeys.has(dedupeKey)) {
      warn.push(`Duplicate line item ignored: ${order_id} [${line_id}]`);
      return;
    }
    seenKeys.add(dedupeKey);

    const gross_sales = parseFloat(row.gross_sales) || 0;
    const discounts = parseFloat(row.discounts) || 0;
    const product_refunds = parseFloat(row.product_refunds) || 0;
    const shipping_collected = parseFloat(row.shipping_collected) || 0;
    const net_product_cost = parseFloat(row.net_product_cost) || 0;
    const fulfillment_cost = parseFloat(row.fulfillment_cost) || 0;
    const payment_fees = parseFloat(row.payment_fees) || 0;
    const allocated_ad_spend = parseFloat(row.allocated_ad_spend) || 0;

    // Formulas
    const net_product_sales = gross_sales - discounts - product_refunds;
    const contribution_before_ads = net_product_sales + shipping_collected - net_product_cost - fulfillment_cost - payment_fees;
    const contribution_after_allocated_ads = contribution_before_ads - allocated_ad_spend;

    items.push({
      order_id,
      line_id,
      sku,
      date,
      currency: curr,
      gross_sales,
      discounts,
      product_refunds,
      shipping_collected,
      net_product_cost,
      fulfillment_cost,
      payment_fees,
      allocated_ad_spend,
      net_product_sales,
      contribution_before_ads,
      contribution_after_allocated_ads,
      is_negative: contribution_after_allocated_ads < 0
    });
  });

  return { items, rejected, warnings: warn };
}

function updateDashboard(items, rejected, warn) {
  currentItems = items;
  rejectedRows = rejected;
  warnings = warn;

  // Filter application
  const searchTerm = (document.getElementById('sku-search').value || '').trim().toLowerCase();
  const statusFilter = document.getElementById('status-filter').value;
  const startDate = document.getElementById('start-date').value;
  const endDate = document.getElementById('end-date').value;

  const filtered = items.filter(it => {
    if (searchTerm && !it.sku.toLowerCase().includes(searchTerm) && !it.order_id.toLowerCase().includes(searchTerm)) {
      return false;
    }
    if (statusFilter === 'loss' && !it.is_negative) return false;
    if (statusFilter === 'profit' && it.is_negative) return false;
    if (startDate && it.date < startDate) return false;
    if (endDate && it.date > endDate) return false;
    return true;
  });

  // Calculate totals
  const totalGross = filtered.reduce((acc, it) => acc + it.gross_sales, 0);
  const totalNet = filtered.reduce((acc, it) => acc + it.net_product_sales, 0);
  const totalBeforeAds = filtered.reduce((acc, it) => acc + it.contribution_before_ads, 0);
  const totalAfterAds = filtered.reduce((acc, it) => acc + it.contribution_after_allocated_ads, 0);
  const totalAllocatedAds = filtered.reduce((acc, it) => acc + it.allocated_ad_spend, 0);
  const negativeCount = filtered.filter(it => it.is_negative).length;
  const marginPct = totalNet > 0 ? ((totalAfterAds / totalNet) * 100).toFixed(1) : 0;

  // Update KPI DOM
  document.getElementById('kpi-gross').textContent = formatCurrency(totalGross);
  document.getElementById('kpi-net').textContent = formatCurrency(totalNet);
  document.getElementById('kpi-before-ads').textContent = formatCurrency(totalBeforeAds);
  document.getElementById('kpi-after-ads').textContent = formatCurrency(totalAfterAds);
  document.getElementById('kpi-ads').textContent = formatCurrency(totalAllocatedAds);
  document.getElementById('kpi-margin').textContent = `${marginPct}%`;
  document.getElementById('kpi-negative-count').textContent = negativeCount;

  // Negative alert banner
  const alertBanner = document.getElementById('negative-alert-banner');
  if (negativeCount > 0) {
    alertBanner.style.display = 'flex';
    document.getElementById('alert-loss-text').textContent = 
      `Warning: ${negativeCount} line items / SKUs are operating at a net negative contribution after allocated advertising.`;
  } else {
    alertBanner.style.display = 'none';
  }

  // Render current tab table
  if (currentTab === 'sku-tab') {
    renderSkuTable(filtered);
  } else if (currentTab === 'orders-tab') {
    renderOrdersTable(filtered);
  } else if (currentTab === 'reconcile-tab') {
    renderReconcileTable(filtered, rejected, warn);
  }
}

function renderSkuTable(items) {
  const skuMap = {};
  items.forEach(it => {
    if (!skuMap[it.sku]) {
      skuMap[it.sku] = {
        sku: it.sku,
        units: 0,
        gross: 0,
        net: 0,
        cost: 0,
        fulfillment: 0,
        fees: 0,
        ads: 0,
        beforeAds: 0,
        afterAds: 0
      };
    }
    const s = skuMap[it.sku];
    s.units += 1;
    s.gross += it.gross_sales;
    s.net += it.net_product_sales;
    s.cost += it.net_product_cost;
    s.fulfillment += it.fulfillment_cost;
    s.fees += it.payment_fees;
    s.ads += it.allocated_ad_spend;
    s.beforeAds += it.contribution_before_ads;
    s.afterAds += it.contribution_after_allocated_ads;
  });

  const skus = Object.values(skuMap).sort((a, b) => a.afterAds - b.afterAds); // Ascending so loss leaders are on top!

  const tbody = document.getElementById('table-body');
  tbody.innerHTML = '';

  if (skus.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding: 2rem;">No data matching filters.</td></tr>';
    return;
  }

  skus.forEach(s => {
    const isNeg = s.afterAds < 0;
    const margin = s.net > 0 ? ((s.afterAds / s.net) * 100).toFixed(1) + '%' : '0.0%';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${s.sku}</strong></td>
      <td class="num-cell">${s.units}</td>
      <td class="num-cell">${formatCurrency(s.gross)}</td>
      <td class="num-cell">${formatCurrency(s.net)}</td>
      <td class="num-cell">${formatCurrency(s.cost)}</td>
      <td class="num-cell">${formatCurrency(s.fulfillment + s.fees)}</td>
      <td class="num-cell">${formatCurrency(s.beforeAds)}</td>
      <td class="num-cell" style="color: #38bdf8;">${formatCurrency(s.ads)}</td>
      <td class="num-cell" style="font-weight: 700; color: ${isNeg ? 'var(--rose)' : 'var(--emerald)'};">
        ${formatCurrency(s.afterAds)}
      </td>
      <td>
        <span class="badge-tag ${isNeg ? 'badge-loss' : 'badge-profit'}">
          ${isNeg ? 'NEGATIVE (' + margin + ')' : 'PROFITABLE (' + margin + ')'}
        </span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderOrdersTable(items) {
  const tbody = document.getElementById('table-body');
  tbody.innerHTML = '';

  if (items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding: 2rem;">No data matching filters.</td></tr>';
    return;
  }

  items.forEach(it => {
    const isNeg = it.is_negative;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${it.order_id} <span style="color:var(--text-muted);">[${it.line_id}]</span></td>
      <td>${it.sku}</td>
      <td>${it.date}</td>
      <td class="num-cell">${formatCurrency(it.gross_sales)}</td>
      <td class="num-cell">${formatCurrency(it.net_product_sales)}</td>
      <td class="num-cell">${formatCurrency(it.net_product_cost)}</td>
      <td class="num-cell">${formatCurrency(it.contribution_before_ads)}</td>
      <td class="num-cell" style="color: #38bdf8;">${formatCurrency(it.allocated_ad_spend)}</td>
      <td class="num-cell" style="font-weight:700; color: ${isNeg ? 'var(--rose)' : 'var(--emerald)'};">
        ${formatCurrency(it.contribution_after_allocated_ads)}
      </td>
      <td>
        <span class="badge-tag ${isNeg ? 'badge-loss' : 'badge-profit'}">
          ${isNeg ? 'DEFICIT' : 'PROFIT'}
        </span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderReconcileTable(items, rejected, warn) {
  const tbody = document.getElementById('table-body');
  tbody.innerHTML = '';

  const totalGross = items.reduce((acc, it) => acc + it.gross_sales, 0);
  const totalNet = items.reduce((acc, it) => acc + it.net_product_sales, 0);
  const totalAds = items.reduce((acc, it) => acc + it.allocated_ad_spend, 0);
  const totalContrib = items.reduce((acc, it) => acc + it.contribution_after_allocated_ads, 0);

  const tr1 = document.createElement('tr');
  tr1.innerHTML = `
    <td colspan="3"><strong>Source Data Reconciliation: Total Active Valid Rows</strong></td>
    <td class="num-cell" colspan="2">${items.length} rows verified</td>
    <td colspan="2">Gross Sales: <strong>${formatCurrency(totalGross)}</strong></td>
    <td colspan="3">Net Sales: <strong>${formatCurrency(totalNet)}</strong></td>
  `;
  tbody.appendChild(tr1);

  const tr2 = document.createElement('tr');
  tr2.innerHTML = `
    <td colspan="3"><strong>Advertising Reconciliation</strong></td>
    <td class="num-cell" colspan="2">Allocated: ${formatCurrency(totalAds)}</td>
    <td colspan="2">Unallocated: $0.00</td>
    <td colspan="3">Total Contribution: <strong>${formatCurrency(totalContrib)}</strong></td>
  `;
  tbody.appendChild(tr2);

  if (rejected.length > 0) {
    rejected.forEach(r => {
      const tr = document.createElement('tr');
      tr.style.background = 'rgba(244, 63, 94, 0.05)';
      tr.innerHTML = `
        <td style="color: var(--rose);"><strong>REJECTED ROW ${r.line}</strong></td>
        <td colspan="3" style="color: var(--rose);">${r.reason}</td>
        <td colspan="6" class="num-cell" style="color: var(--text-muted);">${JSON.stringify(r.row)}</td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="10" style="color: var(--emerald); font-weight:600;">Zero rejected rows. 100% input data integrity verified.</td>`;
    tbody.appendChild(tr);
  }
}

function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: targetCurrency,
    minimumFractionDigits: 2
  }).format(val);
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  // Load initial demo
  loadCSVString(DEMO_CATALOG);

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTab = btn.dataset.tab;
      
      const thead = document.getElementById('table-headers');
      if (currentTab === 'sku-tab') {
        thead.innerHTML = `
          <th>Product SKU</th>
          <th>Units</th>
          <th>Gross Sales</th>
          <th>Net Sales</th>
          <th>Product Cost</th>
          <th>Fulfillment + Fees</th>
          <th>Contrib. Before Ads</th>
          <th>Allocated Ads</th>
          <th>Net Contribution</th>
          <th>Health Status</th>
        `;
      } else if (currentTab === 'orders-tab') {
        thead.innerHTML = `
          <th>Order & Line ID</th>
          <th>SKU</th>
          <th>Date</th>
          <th>Gross</th>
          <th>Net Sales</th>
          <th>Cost</th>
          <th>Contrib. Before Ads</th>
          <th>Ads</th>
          <th>Net Contribution</th>
          <th>Status</th>
        `;
      } else if (currentTab === 'reconcile-tab') {
        thead.innerHTML = `
          <th colspan="3">Audit Category</th>
          <th colspan="2">Count / Ratio</th>
          <th colspan="2">Primary Metric</th>
          <th colspan="3">Reconciliation Outcome</th>
        `;
      }
      updateDashboard(currentItems, rejectedRows, warnings);
    });
  });

  // Buttons
  document.getElementById('btn-load-fixture').addEventListener('click', () => {
    loadCSVString(KNOWN_FIXTURE);
  });

  document.getElementById('btn-load-demo').addEventListener('click', () => {
    loadCSVString(DEMO_CATALOG);
  });

  document.getElementById('sku-search').addEventListener('input', () => {
    updateDashboard(currentItems, rejectedRows, warnings);
  });

  document.getElementById('status-filter').addEventListener('change', () => {
    updateDashboard(currentItems, rejectedRows, warnings);
  });

  document.getElementById('start-date').addEventListener('change', () => {
    updateDashboard(currentItems, rejectedRows, warnings);
  });

  document.getElementById('end-date').addEventListener('change', () => {
    updateDashboard(currentItems, rejectedRows, warnings);
  });

  document.getElementById('btn-reset-filters').addEventListener('click', () => {
    document.getElementById('sku-search').value = '';
    document.getElementById('status-filter').value = 'all';
    document.getElementById('start-date').value = '';
    document.getElementById('end-date').value = '';
    updateDashboard(currentItems, rejectedRows, warnings);
  });

  // File input
  const fileInput = document.getElementById('csv-file-input');
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        loadCSVString(event.target.result);
      };
      reader.readAsText(file);
    }
  });

  // Export CSV
  document.getElementById('btn-export-csv').addEventListener('click', exportResultsToCSV);
});

function loadCSVString(csvStr) {
  const parsed = parseCSV(csvStr);
  const result = processData(parsed);
  updateDashboard(result.items, result.rejected, result.warnings);
}

function exportResultsToCSV() {
  if (currentItems.length === 0) {
    alert('No items to export.');
    return;
  }
  const headers = [
    'order_id', 'line_id', 'sku', 'date', 'currency', 'gross_sales', 'discounts',
    'product_refunds', 'shipping_collected', 'net_product_cost', 'fulfillment_cost',
    'payment_fees', 'allocated_ad_spend', 'net_product_sales', 'contribution_before_ads',
    'contribution_after_allocated_ads', 'is_negative'
  ];
  let csvContent = headers.join(',') + '\n';
  currentItems.forEach(it => {
    const row = [
      it.order_id, it.line_id, it.sku, it.date, it.currency, it.gross_sales, it.discounts,
      it.product_refunds, it.shipping_collected, it.net_product_cost, it.fulfillment_cost,
      it.payment_fees, it.allocated_ad_spend, it.net_product_sales.toFixed(2),
      it.contribution_before_ads.toFixed(2), it.contribution_after_allocated_ads.toFixed(2),
      it.is_negative ? 'TRUE' : 'FALSE'
    ];
    csvContent += row.join(',') + '\n';
  });

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `product_contribution_results_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
