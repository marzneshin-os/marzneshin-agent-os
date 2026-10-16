# Product Contribution Dashboard — Operational Handoff & Runbook

**System Name:** Product Contribution Command Center  
**Framework:** Claudex Loop Cross-Model Verification  
**Repository Location:** `dashboards/product-profit-dashboard/`  

---

## 1. Quick Launch Instructions

You can view and interact with the dashboard immediately using any modern web browser or via a lightweight local server:

### Option A: Direct Web Browser
Open the file in Chrome, Edge, or Firefox:
```text
dashboards/product-profit-dashboard/index.html
```

### Option B: Local Python HTTP Server
```bash
# Start local server on port 8080 (run from repository root)
python -m http.server 8080 -d dashboards/product-profit-dashboard
```
Then navigate to: **`http://localhost:8080`**

---

## 2. Interactive Features & Verification Controls

1. **Load Known-Answer Fixture (TEST-001):**
   - Click the **"Load Known-Answer Fixture (TEST-001)"** button in the dashboard toolbar.
   - Instantly validates the reference calculation:
     - Gross Sales: **$200.00**
     - Discounts: **$20.00**
     - Refunds: **$30.00**
     - Customer Shipping Collected: **$10.00**
     - Net Product Cost: **$60.00**
     - Fulfillment Cost: **$15.00**
     - Payment Fees: **$6.00**
     - Allocated Ad Spend: **$25.00**
   - Expected Output verified in UI:
     - **Net Product Sales: $150.00**
     - **Contribution Before Ads: $79.00**
     - **Contribution After Allocated Ads: $54.00**

2. **Load Demo Catalog:**
   - Click **"Load Catalog Demo"** to see 10 realistic line items including profitable items (e.g. Ergonomic Chair, Wireless Charger) and loss leaders (e.g. Monitor Arm with refunds, Mousepad XL with high ad spend).
   - The **Critical Financial Alert Banner** activates automatically, highlighting loss-making SKUs.

3. **Import Local Sanitized CSV:**
   - Click **"Import Local CSV"** and choose any store export conforming to the schema in `PLAN.md`.
   - The engine automatically validates currency, rejects rows with missing costs, and prevents duplicate line counting.

4. **Export Analyzed CSV:**
   - Click **"Export CSV Results"** to download the calculated contribution data with per-line formulas and loss flags.

---

## 3. Data Ingestion & Weekly Refresh Steps

When exporting updated data from your e-commerce store or ERP:

1. **Sanitize Personal Data:** Strip out customer names, physical addresses, emails, and card numbers.
2. **Preserve Headers:** Ensure headers match the 13 required fields:
   `order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend`
3. **Save Copy:** Store the sanitized export in a local directory (e.g. `data/exports/weekly_YYYY_MM_DD.csv`).
4. **Import:** Use the **Import Local CSV** button on the dashboard.
5. **Reconciliation Audit:** Check the **Reconciliation & Input Integrity Audit** tab to confirm zero rejected rows and verify that total sales reconcile to your bank/Stripe deposits.

---

## 4. Excluded Costs & Financial Limitations

> [!IMPORTANT]
> This dashboard measures **Product Contribution After Allocated Advertising**, NOT the entire company's final net profit.

### What is Included:
- Line-level Product Revenue (Gross minus Discounts & Refunds)
- Customer Shipping Collected
- Direct Product Cost of Goods Sold (COGS)
- Warehouse Pick, Pack & Carrier Shipping (Fulfillment)
- Merchant Gateway Processing Fees
- Attributed Campaign Advertising Spend

### What is Excluded:
- Employee salaries and contractor payroll
- Office rent and warehouse leases
- Software SaaS subscriptions (Shopify apps, Klaviyo, ERP)
- Corporate income taxes and interest expenses
- Depreciation and amortization
- Corporate overhead and legal fees

To calculate true company Net Profit, subtract total monthly operating overhead from aggregate contribution.
