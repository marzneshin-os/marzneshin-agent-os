import os
from pathlib import Path
import sys
from decimal import Decimal
import unittest

_engine_dir = Path(__file__).resolve().parent.parent / "dashboards" / "product-profit-dashboard"
if str(_engine_dir) not in sys.path:
    sys.path.insert(0, str(_engine_dir))

from engine import ContributionEngine, LineItem, to_decimal


KNOWN_FIXTURE_CSV = """order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend
TEST-001,LINE-001,DESK-LAMP,2026-09-01,USD,200,20,30,10,60,15,6,25
"""

MULTI_LINE_CSV = """order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend
ORD-100,LINE-1,CHAIR,2026-09-02,USD,100,0,0,5,40,10,3,10
ORD-100,LINE-2,TABLE,2026-09-02,USD,300,0,0,15,120,20,9,30
"""

DUPLICATE_CSV = """order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend
TEST-001,LINE-001,DESK-LAMP,2026-09-01,USD,200,20,30,10,60,15,6,25
TEST-001,LINE-001,DESK-LAMP,2026-09-01,USD,200,20,30,10,60,15,6,25
"""

MISSING_COST_CSV = """order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend
TEST-002,LINE-001,FREE-ITEM,2026-09-01,USD,100,0,0,0,,5,3,10
"""

MIXED_CURRENCY_CSV = """order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend
TEST-001,LINE-001,DESK-LAMP,2026-09-01,USD,200,20,30,10,60,15,6,25
TEST-003,LINE-001,RUG,2026-09-01,EUR,150,0,0,10,50,10,4,15
"""


class TestProductContributionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ContributionEngine(target_currency="USD")

    def test_check_1_known_answer(self):
        """Check 1: Known-answer calculation must yield exactly $150, $79, $54."""
        res = self.engine.process_csv_content(KNOWN_FIXTURE_CSV)
        self.assertEqual(len(res.items), 1)
        item = res.items[0]

        # Net sales = 200 - 20 - 30 = 150
        self.assertEqual(item.net_product_sales, Decimal("150.00"))
        self.assertEqual(res.total_net_sales, Decimal("150.00"))

        # Contribution before ads = 150 + 10 - 60 - 15 - 6 = 79
        self.assertEqual(item.contribution_before_ads, Decimal("79.00"))
        self.assertEqual(res.total_contribution_before_ads, Decimal("79.00"))

        # Contribution after allocated ads = 79 - 25 = 54
        self.assertEqual(item.contribution_after_allocated_ads, Decimal("54.00"))
        self.assertEqual(res.total_contribution_after_ads, Decimal("54.00"))

        # Verify product cost is net and not reversed again
        self.assertEqual(item.net_product_cost, Decimal("60.00"))

    def test_check_2_duplicate_import(self):
        """Check 2: Duplicate imports are detected and do not multiply totals."""
        res = self.engine.process_csv_content(DUPLICATE_CSV)
        self.assertEqual(len(res.items), 1)
        self.assertEqual(res.total_net_sales, Decimal("150.00"))
        self.assertTrue(any("Duplicate order/line ignored" in w for w in res.warnings))

    def test_check_3_multiline_order(self):
        """Check 3: Multi-line orders sum accurately without doubling order-level costs."""
        res = self.engine.process_csv_content(MULTI_LINE_CSV)
        self.assertEqual(len(res.items), 2)
        # Total gross: 100 + 300 = 400
        self.assertEqual(res.total_gross_sales, Decimal("400.00"))
        # Shipping: 5 + 15 = 20
        self.assertEqual(res.total_shipping_collected, Decimal("20.00"))
        # Total fulfillment: 10 + 20 = 30
        self.assertEqual(res.total_fulfillment_cost, Decimal("30.00"))
        # Total fees: 3 + 9 = 12
        self.assertEqual(res.total_payment_fees, Decimal("12.00"))
        # Contribution:
        # Line 1: 100 + 5 - 40 - 10 - 3 - 10 = 42
        # Line 2: 300 + 15 - 120 - 20 - 9 - 30 = 136
        # Total = 178
        self.assertEqual(res.total_contribution_after_ads, Decimal("178.00"))

    def test_check_4_missing_cost_and_currency(self):
        """Check 4: Missing cost or mixed currency rows are rejected, never treated as free."""
        # Missing cost
        res_cost = self.engine.process_csv_content(MISSING_COST_CSV)
        self.assertEqual(len(res_cost.items), 0)
        self.assertEqual(len(res_cost.rejected_rows), 1)
        self.assertTrue(any("Missing product cost" in r["reason"] for r in res_cost.rejected_rows))

        # Mixed currency
        res_curr = self.engine.process_csv_content(MIXED_CURRENCY_CSV)
        self.assertEqual(len(res_curr.items), 1)
        self.assertEqual(len(res_curr.rejected_rows), 1)
        self.assertEqual(res_curr.rejected_rows[0]["reason"], "Mixed currency 'EUR' incompatible with target 'USD'")

    def test_check_6_advertising_reconciliation(self):
        """Check 6: Allocated + unallocated spend equals total source spend."""
        # 25 allocated from fixture, 50 total source ad spend
        res = self.engine.process_csv_content(KNOWN_FIXTURE_CSV, total_source_ad_spend=Decimal("50.00"))
        self.assertEqual(res.total_allocated_ad_spend, Decimal("25.00"))
        self.assertEqual(res.total_unallocated_ad_spend, Decimal("25.00"))
        self.assertEqual(res.total_ad_spend, Decimal("50.00"))
        self.assertEqual(res.total_allocated_ad_spend + res.total_unallocated_ad_spend, res.total_ad_spend)

    def test_check_8_sku_negative_flag(self):
        """Check 8: Negative contribution products are clearly identified."""
        unprofitable_csv = """order_id,line_id,sku,date,currency,gross_sales,discounts,product_refunds,shipping_collected,net_product_cost,fulfillment_cost,payment_fees,allocated_ad_spend
TEST-999,LINE-001,LOSER-PROD,2026-09-01,USD,50,0,0,0,40,10,2,20
"""
        res = self.engine.process_csv_content(unprofitable_csv)
        self.assertEqual(len(res.items), 1)
        # Net: 50. Before ads: 50 - 40 - 10 - 2 = -2. After ads: -2 - 20 = -22.
        self.assertEqual(res.total_contribution_after_ads, Decimal("-22.00"))
        sku_entry = res.sku_aggregates["LOSER-PROD"]
        self.assertTrue(sku_entry["is_negative"])
        self.assertEqual(sku_entry["contribution_after_ads"], Decimal("-22.00"))


if __name__ == "__main__":
    unittest.main()
