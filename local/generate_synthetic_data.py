"""
generate_synthetic_data.py (local / SQLite version)

Same generation logic, same fixed seed (42), same three planted demo cases
as the original data/setup/generate_synthetic_data.py - just written to the
local claims.db SQLite file (via db.py) instead of BigQuery, so
"three_way_match(CLAIM-DEMO-001)" etc. produce identical results locally.

Usage:
    python generate_synthetic_data.py
    python generate_synthetic_data.py --seed 42 --num-suppliers 20 --pos-per-supplier 8
"""

import argparse
import random
from datetime import timedelta, date

import pandas as pd
from faker import Faker

from db import get_connection, create_schema

fake = Faker()

# ---------------------------------------------------------------------------
# Reference data (identical to the BigQuery version)
# ---------------------------------------------------------------------------

GROCERY_ITEMS = [
    ("SKU-1001", "Organic Whole Milk, 1 Gal", "Dairy"),
    ("SKU-1002", "Sharp Cheddar Cheese, 8oz", "Dairy"),
    ("SKU-1003", "Greek Yogurt, 32oz", "Dairy"),
    ("SKU-2001", "Roma Tomatoes, per case", "Produce"),
    ("SKU-2002", "Organic Baby Spinach, 5oz", "Produce"),
    ("SKU-2003", "Avocados, per case", "Produce"),
    ("SKU-3001", "Sourdough Bread Loaf", "Bakery"),
    ("SKU-3002", "Bagels, 6-pack", "Bakery"),
    ("SKU-4001", "Sparkling Water, 12-pack", "Dry Goods"),
    ("SKU-4002", "Organic Pasta, 16oz", "Dry Goods"),
    ("SKU-4003", "Granola Bars, 12-pack", "Dry Goods"),
    ("SKU-5001", "Frozen Mixed Berries, 16oz", "Frozen"),
    ("SKU-5002", "Frozen Veggie Burgers, 8-pack", "Frozen"),
]

DEDUCTION_CODES = [
    ("SHORT-01", "Shortage - quantity received less than invoiced", "Shortage",
     "Valid if receiving (POD) quantity is genuinely less than the invoiced quantity; verify against ASN and receiving records."),
    ("DAMAGE-02", "Damaged goods deduction", "Damage",
     "Valid only if receiving condition notes confirm damaged product; check the condition_notes field."),
    ("PRICE-03", "Pricing discrepancy - invoice price differs from PO price", "Pricing",
     "Valid if the invoice unit price does not match the agreed purchase order unit price."),
    ("COMP-04", "Vendor compliance fee - late ASN or mislabeled carton", "Compliance",
     "Frequently disputed; verify ASN timestamp against the required lead time in the vendor agreement."),
    ("EPD-05", "Early payment discount (2/10 net 30 terms)", "Early Payment Discount",
     "Automatic and expected under standard terms; rarely disputable if the payment date confirms early payment."),
    ("DUPE-06", "Duplicate billing - invoice submitted twice", "Billing Error",
     "Valid if two invoice numbers reference the same PO and quantity."),
    ("MISC-07", "Miscellaneous administrative fee", "Administrative",
     "Frequently disputed due to unclear documentation; usually needs manual review."),
    ("OVER-08", "Overage - quantity received exceeds invoice", "Overage",
     "Rare; typically requires a supplier credit rather than a deduction."),
    ("FRT-09", "Freight / routing guide violation fee", "Compliance",
     "Valid if the carrier or routing guide specified in the vendor agreement was not followed."),
    ("PROMO-10", "Promotional allowance not reflected on invoice", "Trade Promotion",
     "Valid if the signed trade agreement specifies the allowance amount and it is missing from the invoice."),
    ("CONCEAL-11", "Concealed shortage found after case count audit", "Shortage",
     "Valid if a warehouse audit found fewer units inside cases than the case label indicated."),
    ("SUBST-12", "Unauthorized product substitution", "Compliance",
     "Valid if the SKU received does not match the SKU ordered on the purchase order."),
]

REGIONS = ["East", "West"]
PAYMENT_TERMS = ["2/10 Net 30", "1/15 Net 45", "Net 30"]


# ---------------------------------------------------------------------------
# Background (random) data generation - unchanged from the BigQuery version
# ---------------------------------------------------------------------------

def generate_suppliers(n):
    rows = []
    for i in range(1, n + 1):
        supplier_id = f"SUP-{i:04d}"
        rows.append({
            "supplier_id": supplier_id,
            "supplier_name": fake.company(),
            "region": random.choice(REGIONS),
            "contact_email": fake.company_email(),
            "payment_terms": random.choice(PAYMENT_TERMS),
        })
    return pd.DataFrame(rows)


def random_date(start_days_ago=240, end_days_ago=10):
    days_ago = random.randint(end_days_ago, start_days_ago)
    return date.today() - timedelta(days=days_ago)


def generate_purchase_orders(suppliers_df, pos_per_supplier=8):
    rows = []
    po_counter = 1
    for _, supplier in suppliers_df.iterrows():
        for _ in range(pos_per_supplier):
            sku, desc, _category = random.choice(GROCERY_ITEMS)
            qty = random.randint(50, 500)
            unit_price = round(random.uniform(1.5, 40.0), 2)
            order_date = random_date()
            po_number = f"PO-{po_counter:06d}"
            rows.append({
                "po_number": po_number,
                "supplier_id": supplier["supplier_id"],
                "order_date": order_date,
                "expected_delivery_date": order_date + timedelta(days=random.randint(3, 10)),
                "item_sku": sku,
                "item_description": desc,
                "quantity_ordered": qty,
                "unit_price": unit_price,
                "total_po_amount": round(qty * unit_price, 2),
            })
            po_counter += 1
    return pd.DataFrame(rows)


def generate_shipments_and_receiving(pos_df):
    shipments, receiving = [], []
    asn_counter, pod_counter = 1, 1

    for _, po in pos_df.iterrows():
        ship_date = po["order_date"] + timedelta(days=random.randint(1, 4))
        qty_ordered = po["quantity_ordered"]

        if random.random() < 0.12:
            qty_shipped = max(1, qty_ordered - random.randint(1, 15))
        else:
            qty_shipped = qty_ordered

        asn_id = f"ASN-{asn_counter:06d}"
        shipments.append({
            "asn_id": asn_id,
            "po_number": po["po_number"],
            "ship_date": ship_date,
            "carrier": random.choice(["Regional Freight Co", "Continental Logistics", "Swift Carriers"]),
            "item_sku": po["item_sku"],
            "quantity_shipped": qty_shipped,
        })
        asn_counter += 1

        received_date = ship_date + timedelta(days=random.randint(1, 3))
        if random.random() < 0.08:
            qty_received = max(1, qty_shipped - random.randint(1, 10))
            condition = random.choice(["short", "damaged"])
        else:
            qty_received = qty_shipped
            condition = "ok"

        pod_id = f"POD-{pod_counter:06d}"
        receiving.append({
            "pod_id": pod_id,
            "po_number": po["po_number"],
            "asn_id": asn_id,
            "received_date": received_date,
            "quantity_received": qty_received,
            "condition_notes": condition,
        })
        pod_counter += 1

    return pd.DataFrame(shipments), pd.DataFrame(receiving)


def generate_invoices(pos_df):
    rows = []
    inv_counter = 1
    for _, po in pos_df.iterrows():
        invoice_date = po["order_date"] + timedelta(days=random.randint(5, 12))
        if random.random() < 0.06:
            qty_billed = po["quantity_ordered"] + random.randint(1, 10)
        else:
            qty_billed = po["quantity_ordered"]

        invoice_number = f"INV-{inv_counter:06d}"
        rows.append({
            "invoice_number": invoice_number,
            "po_number": po["po_number"],
            "supplier_id": po["supplier_id"],
            "invoice_date": invoice_date,
            "quantity_billed": qty_billed,
            "invoice_amount": round(qty_billed * po["unit_price"], 2),
        })
        inv_counter += 1
    return pd.DataFrame(rows)


def generate_deduction_claims(pos_df, invoices_df, receiving_df, claim_rate=0.30):
    rows = []
    claim_counter = 1
    invoices_sample = invoices_df.sample(frac=claim_rate, random_state=random.randint(1, 9999))

    for _, invoice in invoices_sample.iterrows():
        po_number = invoice["po_number"]
        pod_row = receiving_df[receiving_df["po_number"] == po_number].iloc[0]
        code, description, category, _notes = random.choice(DEDUCTION_CODES)

        shortfall = invoice["quantity_billed"] - pod_row["quantity_received"]
        if shortfall > 0:
            claim_amount = round(shortfall * 5.0, 2)
            dispute_text = (
                f"We are disputing this deduction on invoice {invoice['invoice_number']}. "
                f"Our shipping records show the full order was sent."
            )
        else:
            claim_amount = round(random.uniform(20, 400), 2)
            dispute_text = (
                f"Requesting review of deduction on invoice {invoice['invoice_number']}. "
                f"Please provide supporting documentation."
            )

        claim_id = f"CLAIM-{claim_counter:06d}"
        rows.append({
            "claim_id": claim_id,
            "invoice_number": invoice["invoice_number"],
            "po_number": po_number,
            "supplier_id": invoice["supplier_id"],
            "deduction_code": code,
            "claim_amount": claim_amount,
            "claim_date": invoice["invoice_date"] + timedelta(days=random.randint(10, 25)),
            "dispute_status": random.choice(["open", "disputed"]),
            "dispute_text": dispute_text,
        })
        claim_counter += 1

    return pd.DataFrame(rows), claim_counter


# ---------------------------------------------------------------------------
# PLANTED DEMO CASES - identical IDs/values to the original script:
#   CLAIM-DEMO-001  genuinely VALID shortage claim
#   CLAIM-DEMO-002  clearly INVALID deduction (fully received)
#   CLAIM-DEMO-003  AMBIGUOUS damaged-goods case
# ---------------------------------------------------------------------------

def build_planted_demo_cases(next_po_num, next_asn_num, next_pod_num, next_inv_num, next_claim_num):
    demo_supplier_id = "SUP-DEMO"
    order_date = date.today() - timedelta(days=20)

    po_rows, shipment_rows, receiving_rows, invoice_rows, claim_rows = [], [], [], [], []

    # --- DEMO-001: valid shortage -----------------------------------------
    po1 = f"PO-{next_po_num:06d}"
    po_rows.append({
        "po_number": po1, "supplier_id": demo_supplier_id, "order_date": order_date,
        "expected_delivery_date": order_date + timedelta(days=5),
        "item_sku": "SKU-2001", "item_description": "Roma Tomatoes, per case",
        "quantity_ordered": 200, "unit_price": 12.00, "total_po_amount": 2400.00,
    })
    shipment_rows.append({
        "asn_id": f"ASN-{next_asn_num:06d}", "po_number": po1,
        "ship_date": order_date + timedelta(days=2), "carrier": "Regional Freight Co",
        "item_sku": "SKU-2001", "quantity_shipped": 200,
    })
    receiving_rows.append({
        "pod_id": f"POD-{next_pod_num:06d}", "po_number": po1, "asn_id": f"ASN-{next_asn_num:06d}",
        "received_date": order_date + timedelta(days=4),
        "quantity_received": 180,  # genuinely 20 cases short at the dock
        "condition_notes": "short",
    })
    invoice_rows.append({
        "invoice_number": f"INV-{next_inv_num:06d}", "po_number": po1, "supplier_id": demo_supplier_id,
        "invoice_date": order_date + timedelta(days=6),
        "quantity_billed": 200, "invoice_amount": 2400.00,
    })
    claim_rows.append({
        "claim_id": "CLAIM-DEMO-001", "invoice_number": f"INV-{next_inv_num:06d}", "po_number": po1,
        "supplier_id": demo_supplier_id, "deduction_code": "SHORT-01",
        "claim_amount": 240.00, "claim_date": order_date + timedelta(days=15),
        "dispute_status": "disputed",
        "dispute_text": (
            "We are disputing the $240 shortage deduction on this invoice. Our records show "
            "the full 200 cases were shipped and we should not be charged for a shortage."
        ),
    })

    # --- DEMO-002: invalid deduction (fully received, no discrepancy) -----
    po2 = f"PO-{next_po_num + 1:06d}"
    po_rows.append({
        "po_number": po2, "supplier_id": demo_supplier_id, "order_date": order_date,
        "expected_delivery_date": order_date + timedelta(days=5),
        "item_sku": "SKU-1001", "item_description": "Organic Whole Milk, 1 Gal",
        "quantity_ordered": 300, "unit_price": 3.50, "total_po_amount": 1050.00,
    })
    shipment_rows.append({
        "asn_id": f"ASN-{next_asn_num + 1:06d}", "po_number": po2,
        "ship_date": order_date + timedelta(days=1), "carrier": "Swift Carriers",
        "item_sku": "SKU-1001", "quantity_shipped": 300,
    })
    receiving_rows.append({
        "pod_id": f"POD-{next_pod_num + 1:06d}", "po_number": po2, "asn_id": f"ASN-{next_asn_num + 1:06d}",
        "received_date": order_date + timedelta(days=3),
        "quantity_received": 300,  # fully received, matches exactly
        "condition_notes": "ok",
    })
    invoice_rows.append({
        "invoice_number": f"INV-{next_inv_num + 1:06d}", "po_number": po2, "supplier_id": demo_supplier_id,
        "invoice_date": order_date + timedelta(days=5),
        "quantity_billed": 300, "invoice_amount": 1050.00,
    })
    claim_rows.append({
        "claim_id": "CLAIM-DEMO-002", "invoice_number": f"INV-{next_inv_num + 1:06d}", "po_number": po2,
        "supplier_id": demo_supplier_id, "deduction_code": "SHORT-01",
        "claim_amount": 105.00, "claim_date": order_date + timedelta(days=14),
        "dispute_status": "disputed",
        "dispute_text": (
            "This $105 shortage deduction appears to be an error. We shipped and you received "
            "the full 300 units - please review and reverse this deduction."
        ),
    })

    # --- DEMO-003: ambiguous, needs human review ---------------------------
    po3 = f"PO-{next_po_num + 2:06d}"
    po_rows.append({
        "po_number": po3, "supplier_id": demo_supplier_id, "order_date": order_date,
        "expected_delivery_date": order_date + timedelta(days=5),
        "item_sku": "SKU-5002", "item_description": "Frozen Veggie Burgers, 8-pack",
        "quantity_ordered": 150, "unit_price": 9.25, "total_po_amount": 1387.50,
    })
    shipment_rows.append({
        "asn_id": f"ASN-{next_asn_num + 2:06d}", "po_number": po3,
        "ship_date": order_date + timedelta(days=2), "carrier": "Continental Logistics",
        "item_sku": "SKU-5002", "quantity_shipped": 150,
    })
    receiving_rows.append({
        "pod_id": f"POD-{next_pod_num + 2:06d}", "po_number": po3, "asn_id": f"ASN-{next_asn_num + 2:06d}",
        "received_date": order_date + timedelta(days=4),
        "quantity_received": 150,  # quantity matches...
        "condition_notes": "damaged",  # ...but condition notes flag partial damage, no unit count given
    })
    invoice_rows.append({
        "invoice_number": f"INV-{next_inv_num + 2:06d}", "po_number": po3, "supplier_id": demo_supplier_id,
        "invoice_date": order_date + timedelta(days=6),
        "quantity_billed": 150, "invoice_amount": 1387.50,
    })
    claim_rows.append({
        "claim_id": "CLAIM-DEMO-003", "invoice_number": f"INV-{next_inv_num + 2:06d}", "po_number": po3,
        "supplier_id": demo_supplier_id, "deduction_code": "DAMAGE-02",
        "claim_amount": 138.75, "claim_date": order_date + timedelta(days=16),
        "dispute_status": "disputed",
        "dispute_text": (
            "Disputing this damage deduction. The receiving note says 'damaged' but doesn't specify "
            "how many units were affected - the full case count was received. Please clarify."
        ),
    })

    demo_supplier_row = {
        "supplier_id": demo_supplier_id, "supplier_name": "Demo Fresh Foods Co.",
        "region": "East", "contact_email": "ar@demofreshfoods.example.com",
        "payment_terms": "2/10 Net 30",
    }

    return (
        demo_supplier_row,
        pd.DataFrame(po_rows), pd.DataFrame(shipment_rows),
        pd.DataFrame(receiving_rows), pd.DataFrame(invoice_rows), pd.DataFrame(claim_rows),
    )


# ---------------------------------------------------------------------------
# SQLite load helper (replaces the BigQuery load_table_from_dataframe call)
# ---------------------------------------------------------------------------

def load_df(conn, table_name, df):
    if df.empty:
        print(f"Skipping {table_name} - no rows to load.")
        return
    # to_sql with 'replace' mirrors the original script's WRITE_TRUNCATE
    # behavior: re-running the generator gives you a clean, reproducible set.
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    print(f"Loaded {len(df):>4} rows into {table_name}")


def main():
    parser = argparse.ArgumentParser(description="Generate and load synthetic data into local claims.db")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-suppliers", type=int, default=20)
    parser.add_argument("--pos-per-supplier", type=int, default=8)
    args = parser.parse_args()

    random.seed(args.seed)
    Faker.seed(args.seed)

    create_schema()
    conn = get_connection()

    # --- Background (random) data ---
    suppliers_df = generate_suppliers(args.num_suppliers)
    codes_df = pd.DataFrame(DEDUCTION_CODES, columns=["code", "description", "category", "typical_validity_notes"])
    pos_df = generate_purchase_orders(suppliers_df, args.pos_per_supplier)
    shipments_df, receiving_df = generate_shipments_and_receiving(pos_df)
    invoices_df = generate_invoices(pos_df)
    claims_df, next_claim_num = generate_deduction_claims(pos_df, invoices_df, receiving_df)

    # --- Planted demo cases (fixed IDs, always present, easy to reference) ---
    next_po_num = len(pos_df) + 1
    next_asn_num = len(shipments_df) + 1
    next_pod_num = len(receiving_df) + 1
    next_inv_num = len(invoices_df) + 1

    (demo_supplier_row, demo_pos_df, demo_shipments_df,
     demo_receiving_df, demo_invoices_df, demo_claims_df) = build_planted_demo_cases(
        next_po_num, next_asn_num, next_pod_num, next_inv_num, next_claim_num
    )

    suppliers_df = pd.concat([suppliers_df, pd.DataFrame([demo_supplier_row])], ignore_index=True)
    pos_df = pd.concat([pos_df, demo_pos_df], ignore_index=True)
    shipments_df = pd.concat([shipments_df, demo_shipments_df], ignore_index=True)
    receiving_df = pd.concat([receiving_df, demo_receiving_df], ignore_index=True)
    invoices_df = pd.concat([invoices_df, demo_invoices_df], ignore_index=True)
    claims_df = pd.concat([claims_df, demo_claims_df], ignore_index=True)

    # Dates need to be plain strings for SQLite storage/comparison.
    for df, cols in [
        (pos_df, ["order_date", "expected_delivery_date"]),
        (shipments_df, ["ship_date"]),
        (receiving_df, ["received_date"]),
        (invoices_df, ["invoice_date"]),
        (claims_df, ["claim_date"]),
    ]:
        for col in cols:
            df[col] = df[col].astype(str)

    # --- Load everything, in dependency order ---
    load_df(conn, "suppliers", suppliers_df)
    load_df(conn, "deduction_codes", codes_df)
    load_df(conn, "purchase_orders", pos_df)
    load_df(conn, "shipments", shipments_df)
    load_df(conn, "receiving", receiving_df)
    load_df(conn, "invoices", invoices_df)
    load_df(conn, "deduction_claims", claims_df)
    conn.commit()
    conn.close()

    print("\nDone. Planted demo cases for your capstone walkthrough:")
    print("  CLAIM-DEMO-001  -> genuinely VALID shortage claim (agent should confirm)")
    print("  CLAIM-DEMO-002  -> clearly INVALID deduction, fully received (agent should flag for reversal)")
    print("  CLAIM-DEMO-003  -> AMBIGUOUS damaged-goods case (agent should route to human review)")


if __name__ == "__main__":
    main()
