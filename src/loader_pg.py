"""
PostgreSQL Relational Loader for Intelligent Fraud Ring Detection
=================================================================
Loads fraudTrain.csv and fraudTest.csv (Sparkov dataset) into the
normalized PostgreSQL schema defined in schema.sql.

Tables populated: customer, account, card, merchant, transaction.
Tables intentionally left EMPTY: device, ip_address, analyst, alert.

KNOWN LIMITATIONS (per project spec):
  - None of the datasets contain device or IP data. We do NOT fabricate
    device IDs or IP addresses. transaction.device_id and transaction.ip_id
    stay NULL, and the device and ip_address tables stay empty.
  - merchant.location is built from merch_lat and merch_long (the merchant's
    coordinates), NOT from the cardholder's city/state.

Schema extensions applied by this loader (via migrate_schema()):
  - ALTER TABLE merchant ADD CONSTRAINT uniq_merchant_name UNIQUE (merchant_name)
  - ALTER TABLE card ADD CONSTRAINT uniq_card_hash UNIQUE (card_number_hash)
  - ALTER TABLE transaction ADD COLUMN trans_num VARCHAR(50) UNIQUE
    (natural key from the CSV for idempotent reloads)

The loader is idempotent: running it on both CSVs (or re-running) never
creates duplicates, thanks to ON CONFLICT DO NOTHING on every INSERT.
"""

import os
import sys
import hashlib
import argparse
import time
from io import StringIO
from datetime import datetime

import pandas as pd
import psycopg
from psycopg.rows import tuple_row

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_NAME = os.getenv("PGDATABASE", "fraud_db")
DB_USER = os.getenv("PGUSER", os.getenv("USER", "arnavbansal"))
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FILES = [
    os.path.join(PROJECT_ROOT, "Datasets", "fraudTrain.csv"),
    os.path.join(PROJECT_ROOT, "Datasets", "fraudTest.csv"),
]


def get_conn_str():
    return f"dbname={DB_NAME} user={DB_USER} host={DB_HOST} port={DB_PORT}"


def hash_card(cc_num: str) -> str:
    return hashlib.sha256(str(cc_num).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Schema migration — add constraints / columns the original DDL lacks
# ---------------------------------------------------------------------------
def migrate_schema(conn):
    """Idempotently add the unique constraints and columns needed."""
    with conn.cursor() as cur:
        # 1. UNIQUE on merchant.merchant_name
        cur.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'merchant'::regclass
              AND conname  = 'uniq_merchant_name';
        """)
        if not cur.fetchone():
            print("[migrate] Adding UNIQUE(merchant_name) to merchant...")
            cur.execute("""
                ALTER TABLE merchant
                ADD CONSTRAINT uniq_merchant_name UNIQUE (merchant_name);
            """)

        # 2. UNIQUE on card.card_number_hash
        cur.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'card'::regclass
              AND conname  = 'uniq_card_hash';
        """)
        if not cur.fetchone():
            print("[migrate] Adding UNIQUE(card_number_hash) to card...")
            cur.execute("""
                ALTER TABLE card
                ADD CONSTRAINT uniq_card_hash UNIQUE (card_number_hash);
            """)

        # 3. trans_num column on transaction (natural key for idempotency)
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'transaction' AND column_name = 'trans_num';
        """)
        if not cur.fetchone():
            print("[migrate] Adding trans_num VARCHAR(50) UNIQUE to transaction...")
            cur.execute("""
                ALTER TABLE transaction
                ADD COLUMN trans_num VARCHAR(50) UNIQUE;
            """)

    conn.commit()
    print("[migrate] Schema migration complete.")


# ---------------------------------------------------------------------------
# Truncate (optional fresh start)
# ---------------------------------------------------------------------------
def truncate_tables(conn):
    print("[*] Truncating all tables...")
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE TABLE alert, transaction, card, account,
                          customer, merchant, device, ip_address, analyst
            CASCADE;
        """)
    conn.commit()
    print("[+] All tables truncated.")


# ---------------------------------------------------------------------------
# Print row counts
# ---------------------------------------------------------------------------
TABLE_ORDER = [
    "customer", "account", "card", "merchant",
    "device", "ip_address", "transaction", "alert", "analyst",
]

def print_counts(conn, label=""):
    with conn.cursor() as cur:
        print(f"\n{'=' * 50}")
        print(f"  TABLE ROW COUNTS {label}")
        print(f"{'=' * 50}")
        for t in TABLE_ORDER:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            cnt = cur.fetchone()[0]
            cur_fraud = ""
            if t == "transaction":
                cur.execute("SELECT COUNT(*) FROM transaction WHERE fraud_label = TRUE")
                fc = cur.fetchone()[0]
                cur_fraud = f"  (fraud: {fc:,})"
            print(f"  {t:20s} {cnt:>12,}{cur_fraud}")
        print(f"{'=' * 50}\n")


# ---------------------------------------------------------------------------
# Load a single CSV into the database
# ---------------------------------------------------------------------------
def load_csv(conn, filepath: str, limit: int | None = None):
    """Load one Sparkov CSV into the normalized PostgreSQL schema."""
    print(f"\n[*] Reading {filepath} (limit: {limit or 'ALL'})...")
    t0 = time.time()
    df = pd.read_csv(filepath, nrows=limit)
    print(f"[*] Loaded {len(df):,} rows in {time.time() - t0:.1f}s")

    with conn.cursor() as cur:
        # ── 1. Customers ─────────────────────────────────────────────────
        print("[*] Upserting customers...")
        cust_df = df[["first", "last", "dob"]].drop_duplicates()
        cust_count = 0
        for _, r in cust_df.iterrows():
            fn = r["first"].strip()
            ln = r["last"].strip()
            dob = r["dob"]
            email = f"{fn.lower()}.{ln.lower()}.{hash(dob) % 10000}@ringdefense.net"
            phone = (
                f"+1-555-{abs(hash(fn + ln)) % 900 + 100:03d}"
                f"-{abs(hash(dob)) % 9000 + 1000:04d}"
            )
            cur.execute(
                """
                INSERT INTO customer
                    (first_name, last_name, email, phone_number, date_of_birth, kyc_verified)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO NOTHING;
                """,
                (fn, ln, email, phone, dob),
            )
            cust_count += cur.rowcount
        conn.commit()
        print(f"[+] Customers: {cust_count:,} new rows inserted.")

        # Build lookup
        cur.execute("SELECT customer_id, first_name, last_name, date_of_birth FROM customer")
        cust_map = {(fn, ln, str(dob)): cid for cid, fn, ln, dob in cur.fetchall()}

        # ── 2. Accounts ──────────────────────────────────────────────────
        print("[*] Upserting accounts...")
        card_df = df[["first", "last", "dob", "cc_num"]].drop_duplicates(subset=["cc_num"])
        acct_count = 0
        for _, r in card_df.iterrows():
            cid = cust_map.get((r["first"].strip(), r["last"].strip(), str(r["dob"])))
            if not cid:
                continue
            acct_num = f"ACCT-{hashlib.md5(str(r['cc_num']).encode()).hexdigest()[:12].upper()}"
            cur.execute(
                """
                INSERT INTO account
                    (customer_id, account_number, account_type, balance, status)
                VALUES (%s, %s, 'checking', 2500.00, 'active')
                ON CONFLICT (account_number) DO NOTHING;
                """,
                (cid, acct_num),
            )
            acct_count += cur.rowcount
        conn.commit()
        print(f"[+] Accounts: {acct_count:,} new rows inserted.")

        cur.execute("SELECT account_id, account_number FROM account")
        acct_map = {acc_num: aid for aid, acc_num in cur.fetchall()}

        # ── 3. Cards ─────────────────────────────────────────────────────
        print("[*] Upserting cards...")
        card_count = 0
        for _, r in card_df.iterrows():
            acct_num = f"ACCT-{hashlib.md5(str(r['cc_num']).encode()).hexdigest()[:12].upper()}"
            aid = acct_map.get(acct_num)
            if not aid:
                continue
            chash = hash_card(r["cc_num"])
            cc_str = str(r["cc_num"])
            ctype = (
                "visa" if cc_str.startswith("4")
                else "mastercard" if cc_str.startswith("5")
                else "other"
            )
            cur.execute(
                """
                INSERT INTO card (account_id, card_number_hash, card_type, expiry_date, status)
                VALUES (%s, %s, %s, '2028-12-31', 'active')
                ON CONFLICT (card_number_hash) DO NOTHING;
                """,
                (aid, chash, ctype),
            )
            card_count += cur.rowcount
        conn.commit()
        print(f"[+] Cards: {card_count:,} new rows inserted.")

        cur.execute("SELECT card_id, card_number_hash FROM card")
        card_map = {h: cid for cid, h in cur.fetchall()}

        # ── 4. Merchants ─────────────────────────────────────────────────
        # IMPORTANT: location is built from merch_lat / merch_long
        # (the merchant's coordinates), NOT the cardholder's city/state.
        print("[*] Upserting merchants...")
        merch_df = df[["merchant", "category", "merch_lat", "merch_long"]].drop_duplicates(
            subset=["merchant"]
        )
        merch_count = 0
        for _, r in merch_df.iterrows():
            mname = r["merchant"].strip()
            cat = r["category"].strip()
            location = f"{r['merch_lat']}, {r['merch_long']}"
            cur.execute(
                """
                INSERT INTO merchant (merchant_name, mcc_category, location)
                VALUES (%s, %s, %s)
                ON CONFLICT (merchant_name) DO NOTHING;
                """,
                (mname, cat, location),
            )
            merch_count += cur.rowcount
        conn.commit()
        print(f"[+] Merchants: {merch_count:,} new rows inserted.")

        cur.execute("SELECT merchant_id, merchant_name FROM merchant")
        merch_map = {name: mid for mid, name in cur.fetchall()}

        # ── 5. Transactions ──────────────────────────────────────────────
        # NOTE: device_id and ip_id are intentionally NULL.
        # The datasets contain no device or IP information.
        print("[*] Inserting transactions in batches...")
        batch = []
        batch_size = 5000
        total_inserted = 0

        for _, r in df.iterrows():
            acct_num = f"ACCT-{hashlib.md5(str(r['cc_num']).encode()).hexdigest()[:12].upper()}"
            aid = acct_map.get(acct_num)
            mid = merch_map.get(r["merchant"].strip())
            if not aid or not mid:
                continue
            chash = hash_card(r["cc_num"])
            cid = card_map.get(chash)

            batch.append((
                aid,
                cid,
                mid,
                None,   # device_id — intentionally NULL
                None,   # ip_id    — intentionally NULL
                float(r["amt"]),
                r["trans_date_trans_time"],
                "approved",
                bool(r["is_fraud"]),
                r["trans_num"],   # natural key for idempotency
            ))

            if len(batch) >= batch_size:
                total_inserted += _insert_txn_batch(cur, batch)
                conn.commit()
                batch = []
                if total_inserted % 50000 < batch_size:
                    print(f"    -> {total_inserted:,} transactions inserted so far...")

        if batch:
            total_inserted += _insert_txn_batch(cur, batch)
            conn.commit()

        print(f"[+] Transactions: {total_inserted:,} new rows inserted from this file.")


def _insert_txn_batch(cur, batch):
    """Insert a batch of transaction tuples, returning count of new rows."""
    inserted = 0
    for row in batch:
        cur.execute(
            """
            INSERT INTO transaction
                (account_id, card_id, merchant_id, device_id, ip_id,
                 amount, txn_timestamp, status, fraud_label, trans_num)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (trans_num) DO NOTHING;
            """,
            row,
        )
        inserted += cur.rowcount
    return inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Load Sparkov fraud CSVs into PostgreSQL (idempotent)"
    )
    parser.add_argument(
        "--files", nargs="+",
        default=DEFAULT_FILES,
        help="CSV file(s) to load. Default: fraudTrain.csv + fraudTest.csv",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max rows per file (default: no limit = full load)",
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="Truncate all tables before loading (fresh start)",
    )
    args = parser.parse_args()

    conn_str = get_conn_str()
    print(f"[*] Connecting to PostgreSQL ({conn_str})...")

    with psycopg.connect(conn_str) as conn:
        # Apply schema migrations first
        migrate_schema(conn)

        if args.truncate:
            truncate_tables(conn)

        print_counts(conn, "(before load)")

        for fpath in args.files:
            if not os.path.isfile(fpath):
                print(f"[!] File not found, skipping: {fpath}")
                continue
            load_csv(conn, fpath, limit=args.limit)

        print_counts(conn, "(after load)")

    print("[DONE] Loader finished successfully.")


if __name__ == "__main__":
    main()
