"""Product Profit & Contribution Calculation Engine.

Implements the financial rules and 8 acceptance checks from:
'Claude Plans. Astra Builds. You Win.' (Claudex Loop) by Steve Tan.

Key formulas:
  Net product sales = gross product sales - discounts - product refunds
  Contribution before ads = net product sales + customer shipping collected
                            - net product cost - fulfillment/shipping cost - payment fees
  Contribution after allocated ads = contribution before ads - allocated ad spend
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def to_decimal(val: Any) -> Decimal:
    if val is None or val == "":
        return Decimal("0.00")
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    # clean string
    s = str(val).strip().replace("$", "").replace(",", "")
    return Decimal(s)


@dataclass
class LineItem:
    order_id: str
    line_id: str
    sku: str
    date: str
    currency: str
    gross_sales: Decimal
    discounts: Decimal
    product_refunds: Decimal
    shipping_collected: Decimal
    net_product_cost: Decimal
    fulfillment_cost: Decimal
    payment_fees: Decimal
    allocated_ad_spend: Decimal
    is_cost_missing: bool = False
    raw_row: Dict[str, str] = field(default_factory=dict)

    @property
    def net_product_sales(self) -> Decimal:
        return self.gross_sales - self.discounts - self.product_refunds

    @property
    def contribution_before_ads(self) -> Decimal:
        return (
            self.net_product_sales
            + self.shipping_collected
            - self.net_product_cost
            - self.fulfillment_cost
            - self.payment_fees
        )

    @property
    def contribution_after_allocated_ads(self) -> Decimal:
        return self.contribution_before_ads - self.allocated_ad_spend

    @property
    def is_negative_contribution(self) -> bool:
        return self.contribution_after_allocated_ads < Decimal("0.00")


@dataclass
class CalculationResult:
    items: List[LineItem]
    warnings: List[str]
    rejected_rows: List[Dict[str, Any]]
    total_gross_sales: Decimal
    total_discounts: Decimal
    total_refunds: Decimal
    total_net_sales: Decimal
    total_shipping_collected: Decimal
    total_product_cost: Decimal
    total_fulfillment_cost: Decimal
    total_payment_fees: Decimal
    total_contribution_before_ads: Decimal
    total_allocated_ad_spend: Decimal
    total_unallocated_ad_spend: Decimal
    total_ad_spend: Decimal
    total_contribution_after_ads: Decimal
    currency: str
    sku_aggregates: Dict[str, Dict[str, Any]]


class ContributionEngine:
    def __init__(self, target_currency: str = "USD"):
        self.target_currency = target_currency

    def process_csv_content(
        self,
        csv_text: str,
        total_source_ad_spend: Optional[Decimal] = None
    ) -> CalculationResult:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        items: List[LineItem] = []
        warnings: List[str] = []
        rejected_rows: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, str]] = set()

        line_number = 1
        for row in reader:
            line_number += 1
            order_id = row.get("order_id", "").strip()
            line_id = row.get("line_id", "").strip()
            sku = row.get("sku", "").strip()
            row_curr = row.get("currency", "").strip().upper()
            row_date = row.get("date", "").strip()

            # Acceptance Check 4: Missing cost or currency validation
            if not row_curr:
                rejected_rows.append({"row": line_number, "reason": "Missing currency", "data": row})
                warnings.append(f"Row {line_number}: Rejected due to missing currency")
                continue

            if row_curr != self.target_currency:
                rejected_rows.append({
                    "row": line_number,
                    "reason": f"Mixed currency '{row_curr}' incompatible with target '{self.target_currency}'",
                    "data": row
                })
                warnings.append(f"Row {line_number}: Rejected due to mixed currency '{row_curr}'")
                continue

            # Check missing cost (never treated as free product)
            cost_str = row.get("net_product_cost", "").strip()
            if not cost_str:
                rejected_rows.append({"row": line_number, "reason": "Missing product cost (cannot treat as free)", "data": row})
                warnings.append(f"Row {line_number} (SKU {sku}): Missing cost is not allowed; product cannot be free")
                continue

            # Acceptance Check 2: Duplicate import check
            key = (order_id, line_id)
            if key in seen_keys:
                warnings.append(f"Duplicate order/line ignored: {order_id} / {line_id}")
                continue
            seen_keys.add(key)

            try:
                item = LineItem(
                    order_id=order_id,
                    line_id=line_id,
                    sku=sku,
                    date=row_date,
                    currency=row_curr,
                    gross_sales=to_decimal(row.get("gross_sales")),
                    discounts=to_decimal(row.get("discounts")),
                    product_refunds=to_decimal(row.get("product_refunds")),
                    shipping_collected=to_decimal(row.get("shipping_collected")),
                    net_product_cost=to_decimal(cost_str),
                    fulfillment_cost=to_decimal(row.get("fulfillment_cost")),
                    payment_fees=to_decimal(row.get("payment_fees")),
                    allocated_ad_spend=to_decimal(row.get("allocated_ad_spend")),
                    raw_row=dict(row)
                )
                items.append(item)
            except Exception as e:
                rejected_rows.append({"row": line_number, "reason": f"Parsing error: {e}", "data": row})
                warnings.append(f"Row {line_number}: Failed to parse: {e}")

        # Aggregations
        tot_gross = sum((i.gross_sales for i in items), Decimal("0.00"))
        tot_discounts = sum((i.discounts for i in items), Decimal("0.00"))
        tot_refunds = sum((i.product_refunds for i in items), Decimal("0.00"))
        tot_net_sales = sum((i.net_product_sales for i in items), Decimal("0.00"))
        tot_shipping = sum((i.shipping_collected for i in items), Decimal("0.00"))
        tot_cost = sum((i.net_product_cost for i in items), Decimal("0.00"))
        tot_fulf = sum((i.fulfillment_cost for i in items), Decimal("0.00"))
        tot_fees = sum((i.payment_fees for i in items), Decimal("0.00"))
        tot_before_ads = sum((i.contribution_before_ads for i in items), Decimal("0.00"))
        tot_allocated_ads = sum((i.allocated_ad_spend for i in items), Decimal("0.00"))

        # Acceptance Check 6: Advertising reconciliation
        if total_source_ad_spend is not None:
            tot_ad_spend = total_source_ad_spend
            tot_unallocated = max(Decimal("0.00"), tot_ad_spend - tot_allocated_ads)
        else:
            tot_ad_spend = tot_allocated_ads
            tot_unallocated = Decimal("0.00")

        tot_after_ads = tot_before_ads - tot_allocated_ads

        # SKU aggregation
        sku_map: Dict[str, Dict[str, Any]] = {}
        for it in items:
            s = it.sku
            if s not in sku_map:
                sku_map[s] = {
                    "sku": s,
                    "units": 0,
                    "gross_sales": Decimal("0.00"),
                    "discounts": Decimal("0.00"),
                    "refunds": Decimal("0.00"),
                    "net_sales": Decimal("0.00"),
                    "shipping_collected": Decimal("0.00"),
                    "product_cost": Decimal("0.00"),
                    "fulfillment_cost": Decimal("0.00"),
                    "payment_fees": Decimal("0.00"),
                    "contribution_before_ads": Decimal("0.00"),
                    "allocated_ad_spend": Decimal("0.00"),
                    "contribution_after_ads": Decimal("0.00"),
                    "line_count": 0,
                }
            entry = sku_map[s]
            entry["units"] += 1
            entry["line_count"] += 1
            entry["gross_sales"] += it.gross_sales
            entry["discounts"] += it.discounts
            entry["refunds"] += it.product_refunds
            entry["net_sales"] += it.net_product_sales
            entry["shipping_collected"] += it.shipping_collected
            entry["product_cost"] += it.net_product_cost
            entry["fulfillment_cost"] += it.fulfillment_cost
            entry["payment_fees"] += it.payment_fees
            entry["contribution_before_ads"] += it.contribution_before_ads
            entry["allocated_ad_spend"] += it.allocated_ad_spend
            entry["contribution_after_ads"] += it.contribution_after_allocated_ads

        # Format SKU aggregates
        for s, entry in sku_map.items():
            entry["is_negative"] = entry["contribution_after_ads"] < Decimal("0.00")
            if entry["net_sales"] > Decimal("0.00"):
                entry["margin_pct"] = round((entry["contribution_after_ads"] / entry["net_sales"]) * Decimal("100.0"), 2)
            else:
                entry["margin_pct"] = Decimal("0.00")

        return CalculationResult(
            items=items,
            warnings=warnings,
            rejected_rows=rejected_rows,
            total_gross_sales=tot_gross,
            total_discounts=tot_discounts,
            total_refunds=tot_refunds,
            total_net_sales=tot_net_sales,
            total_shipping_collected=tot_shipping,
            total_product_cost=tot_cost,
            total_fulfillment_cost=tot_fulf,
            total_payment_fees=tot_fees,
            total_contribution_before_ads=tot_before_ads,
            total_allocated_ad_spend=tot_allocated_ads,
            total_unallocated_ad_spend=tot_unallocated,
            total_ad_spend=tot_ad_spend,
            total_contribution_after_ads=tot_after_ads,
            currency=self.target_currency,
            sku_aggregates=sku_map,
        )
