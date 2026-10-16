# Implementation Plan: Product Contribution Dashboard (Claudex Loop)

**Document Version:** 1.0.0 (APPROVED)  
**Governance Framework:** Claudex Loop Standard v1.0  
**Coordinating Host:** Claude Code (claude-fable-5-1)  
**Adversarial Reviewer:** Codex CLI (gpt-6-astra)  
**Authorized Builder:** Codex CLI (gpt-6-astra)  
**Independent Inspector:** Fresh Claude Code Session (claude-fable-5-1)  
**Plan SHA-256 Hash:** Dynamic Content-Addressed

---

## 1. Business Context & Objective

The objective of this project is to implement a local, privacy-preserving **Product Profit & Contribution Dashboard** capable of calculating and revealing true unit economics after allocated advertising spend. A sales chart showing revenue growth can easily conceal unprofitable SKUs; this dashboard isolates product contribution after ad allocation to pinpoint value-destroying inventory lines.

- **Intended Users:** Business Owner, CFO / Finance, Operations.
- **Reporting Currency:** USD ($) — strict single-currency enforcement (mixed currency imports rejected).
- **Time Zone:** UTC / Local store timezone.
- **Deployment & Security:** 100% Local execution. No external data telemetry, no public cloud hosting, no production database write-access.

---

## 2. Mathematical Definitions & Financial Rules

### Core Formulas

1. **Net Product Sales:**
   $$\text{Net Sales} = \text{Gross Product Sales} - \text{Discounts} - \text{Product Refunds}$$

2. **Contribution Before Advertising:**
   $$\text{Contribution Before Ads} = \text{Net Sales} + \text{Shipping Collected} - \text{Net Product Cost} - \text{Fulfillment Cost} - \text{Payment Processing Fees}$$

3. **Contribution After Allocated Advertising (Net Contribution):**
   $$\text{Contribution After Allocated Ads} = \text{Contribution Before Ads} - \text{Allocated Ad Spend}$$

4. **Contribution Margin (%):**
   $$\text{Contribution Margin \%} = \left(\frac{\text{Contribution After Allocated Ads}}{\text{Net Product Sales}}\right) \times 100$$

### Critical Financial Guardrails
- **Taxes:** Product sales and costs are evaluated exclusive of sales tax / VAT.
- **Shipping Split:** Distinguishes customer shipping collected (revenue) from merchant fulfillment shipping paid (cost).
- **No Double-Deduction:** Discounts and refunds are not subtracted twice if exports already report net figures.
- **Inventory Recovery:** Net product cost already reflects agreed return recovery policies; partial refunds do not automatically reverse COGS without documented inventory receipt.
- **Missing Data Discipline:** Missing cost is strictly rejected and never treated as $0.00 (a product is never free).

---

## 3. Data Schema & Field Mappings

| Field Name | Type | Mandatory | Definition & Integrity Rule |
|---|---|---|---|
| `order_id` | String | Yes | Unique order identifier. |
| `line_id` | String | Yes | Line item identifier within order (used with `order_id` for deduplication). |
| `sku` | String | Yes | Stock Keeping Unit identifier. |
| `date` | YYYY-MM-DD | Yes | Order transaction timestamp. |
| `currency` | ISO-4217 | Yes | Single currency required (e.g. `USD`). Mixed currencies rejected. |
| `gross_sales` | Decimal | Yes | Product catalog price &times; quantity before discounts. |
| `discounts` | Decimal | Yes | Promotional coupons or line-level deductions. |
| `product_refunds` | Decimal | Yes | Returns or refund amounts credited back to buyer. |
| `shipping_collected`| Decimal | Yes | Shipping charges paid by customer for this item. |
| `net_product_cost` | Decimal | Yes | Unit cost of goods sold (COGS). Missing values reject the row. |
| `fulfillment_cost` | Decimal | Yes | Warehouse pick, pack, and carrier shipping fee. |
| `payment_fees` | Decimal | Yes | Credit card / payment gateway processing fee allocated to line. |
| `allocated_ad_spend`| Decimal | Yes | Marketing / ad spend attributed to this line item. |

---

## 4. Acceptance Criteria & Verification Checks

| ID | Check Name | Passing Standard |
|---|---|---|
| **C1** | **Known-Answer Fixture** | Row `TEST-001,LINE-001,DESK-LAMP,2026-09-01,USD,200,20,30,10,60,15,6,25` returns Net Sales = **$150.00**, Contribution Before Ads = **$79.00**, and Contribution After Ads = **$54.00**. |
| **C2** | **Duplicate Line Idempotency** | Re-importing identical `order_id` + `line_id` does not multiply figures; triggers duplicate warning. |
| **C3** | **Order-Level Cost Allocation**| Multi-line orders distribute shipping collected and fees correctly without repeating order-level totals on each line. |
| **C4** | **Missing Cost & Currency** | Rows missing currency or cost are rejected into an error ledger; missing cost is never assumed to be $0. |
| **C5** | **Refunds & Date Policy** | Late refunds and partial refunds do not trigger fictitious COGS recoveries. |
| **C6** | **Advertising Reconciliation** | Allocated ad spend + Unallocated ad spend equals total source campaign spend. Zero-sales dates preserve ad costs without division-by-zero. |
| **C7** | **Source Reconciliation** | Totals of sales, refunds, fulfillment, and fees equal raw CSV source export totals under the same filters. |
| **C8** | **Interactive UI & Export** | Responsive dark-mode dashboard provides live date/SKU filtering, negative-contribution loss flags, and CSV export. |

---

## 5. Execution Proof Commands

```bash
# 1. Run Python unit tests verifying all acceptance criteria
python -m unittest tests/test_product_contribution.py

# 2. Run Claudex Loop integration tests
python -m unittest discover -s .agents/plugins/claudex-loop/tests

# 3. Verify Marzneshin Adapter execution
python -c "from adapters.claudex_loop import ClaudexLoopAdapter; a = ClaudexLoopAdapter(); print(a.execute('run_fixture_test', {}, idem_key='test-c1'))"
```
