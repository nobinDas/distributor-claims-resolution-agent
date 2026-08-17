"""
db.py

Local SQLite replacement for BigQuery (business data) + Cloud SQL (audit
log). One file, one connection helper, used by every tool module.

Run this directly to (re)create an empty schema:
    python db.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "claims.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id     TEXT PRIMARY KEY,
    supplier_name   TEXT NOT NULL,
    region          TEXT,
    contact_email   TEXT,
    payment_terms   TEXT
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    po_number               TEXT PRIMARY KEY,
    supplier_id              TEXT NOT NULL,
    order_date                TEXT NOT NULL,
    expected_delivery_date    TEXT,
    item_sku                  TEXT NOT NULL,
    item_description          TEXT,
    quantity_ordered           INTEGER NOT NULL,
    unit_price                 REAL NOT NULL,
    total_po_amount            REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    asn_id             TEXT PRIMARY KEY,
    po_number          TEXT NOT NULL,
    ship_date          TEXT NOT NULL,
    carrier            TEXT,
    item_sku           TEXT NOT NULL,
    quantity_shipped   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS receiving (
    pod_id             TEXT PRIMARY KEY,
    po_number          TEXT NOT NULL,
    asn_id             TEXT,
    received_date      TEXT NOT NULL,
    quantity_received  INTEGER NOT NULL,
    condition_notes    TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_number    TEXT PRIMARY KEY,
    po_number         TEXT NOT NULL,
    supplier_id       TEXT NOT NULL,
    invoice_date      TEXT NOT NULL,
    quantity_billed   INTEGER NOT NULL,
    invoice_amount    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS deduction_codes (
    code                    TEXT PRIMARY KEY,
    description             TEXT NOT NULL,
    category                TEXT,
    typical_validity_notes  TEXT
);

CREATE TABLE IF NOT EXISTS deduction_claims (
    claim_id         TEXT PRIMARY KEY,
    invoice_number   TEXT NOT NULL,
    po_number        TEXT NOT NULL,
    supplier_id      TEXT NOT NULL,
    deduction_code   TEXT NOT NULL,
    claim_amount     REAL NOT NULL,
    claim_date       TEXT NOT NULL,
    dispute_status   TEXT,
    dispute_text     TEXT
);

-- Replaces the Cloud SQL Postgres case_history audit log.
CREATE TABLE IF NOT EXISTS case_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id            TEXT NOT NULL,
    match_status        TEXT,
    claim_amount        REAL,
    evidence            TEXT,
    recommended_action  TEXT,
    analyst_decision    TEXT NOT NULL DEFAULT 'pending',
    analyst_notes       TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_case_history_claim_id
    ON case_history (claim_id);
"""


def get_connection():
    """Single helper every tool module uses to reach the local DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_schema():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Schema ready at {DB_PATH}")


if __name__ == "__main__":
    create_schema()
