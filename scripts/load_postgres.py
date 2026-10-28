#!/usr/bin/env python3
"""
Step 1: PostgreSQL Data Loader
Populates customer, account, card, merchant, device, ip_address, and transaction tables
from fraudTrain.csv and fraudTest.csv with strict deduplication.
"""

import os
import sys
import hashlib
import argparse
import logging
from datetime import datetime
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.db_config import PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE, DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def derive_device_fingerprint(lat: float, lon: float, zip_code: str) -> str:
    """
    Derive deterministic device fingerprint proxy based on localized coordinate cluster & zip.
    This creates realistic shared device signals for fraud rings without fabricating arbitrary IDs.
    """
    coord_cluster = f"{round(float(lat), 2)}_{round(float(lon), 2)}_{str(zip_code).strip()}"
    digest = hashlib.sha256(coord_cluster.encode("utf-8")).hexdigest()[:16]
    return f"DEV-{digest}"

def derive_ip_address(city: str, state: str, zip_code: str, lat: float, lon: float):
    """
    Derive deterministic IP proxy from geolocation cluster.
    """
    h_state = abs(hash(str(state))) % 250 + 1
    h_city = abs(hash(str(city))) % 250 + 1
    h_zip = abs(hash(str(zip_code))) % 250 + 1
    ip_str = f"10.{h_state}.{h_city}.{h_zip}"
    return ip_str, float(lat), float(lon)

def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE
    )

def load_data(file_path: str, limit: int = None, chunk_size: int = 50000):
    logger.info(f"Loading data from {file_path} (limit={limit})...")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    conn = get_connection()
    cur = conn.cursor()

    # In-memory lookup caches to eliminate round-trip lookups
    customer_map = {}  # (first, last, dob) -> customer_id
    account_map = {}   # customer_id -> account_id
    card_map = {}      # card_number -> card_id
    merchant_map = {}  # merchant_name -> merchant_id
    device_map = {}    # device_fingerprint -> device_id
    ip_map = {}        # ip_str -> ip_id

    # Pre-populate caches with existing DB records (if re-running or incremental)
    logger.info("Initializing in-memory deduplication caches from existing database records...")
    cur.execute("SELECT first_name, last_name, dob, customer_id FROM customer;")
    for row in cur.fetchall():
        customer_map[(row[0], row[1], str(row[2]))] = row[3]

    cur.execute("SELECT customer_id, account_id FROM account;")
    for row in cur.fetchall():
        account_map[row[0]] = row[1]

    cur.execute("SELECT card_number, card_id FROM card;")
    for row in cur.fetchall():
        card_map[str(row[0])] = row[1]

    cur.execute("SELECT merchant_name, merchant_id FROM merchant;")
    for row in cur.fetchall():
        merchant_map[row[0]] = row[1]

    cur.execute("SELECT device_fingerprint, device_id FROM device;")
    for row in cur.fetchall():
        device_map[row[0]] = row[1]

    cur.execute("SELECT ip_str, ip_id FROM ip_address;")
    for row in cur.fetchall():
        ip_map[row[0]] = row[1]

    logger.info(f"Loaded existing caches: {len(customer_map)} customers, {len(merchant_map)} merchants, "
                f"{len(card_map)} cards, {len(device_map)} devices, {len(ip_map)} IPs.")

    # Process in chunks
    total_processed = 0
    total_transactions_inserted = 0

    reader = pd.read_csv(file_path, chunksize=chunk_size, nrows=limit)

    for chunk_idx, df in enumerate(reader):
        logger.info(f"Processing chunk {chunk_idx + 1} ({len(df)} rows)...")

        # 1. Deduplicate & Insert Customers
        new_customers = []
        for _, row in df.iterrows():
            key = (row["first"], row["last"], str(row["dob"]))
            if key not in customer_map:
                customer_map[key] = None  # placeholder
                new_customers.append((
                    row["first"], row["last"], row["gender"], row["dob"],
                    row["job"], row["street"], row["city"], row["state"],
                    str(row["zip"]), float(row["lat"]), float(row["long"]),
                    int(row["city_pop"])
                ))

        if new_customers:
            query = """
            INSERT INTO customer (first_name, last_name, gender, dob, job, street, city, state, zip, lat, long, city_pop)
            VALUES %s RETURNING first_name, last_name, dob, customer_id;
            """
            result = execute_values(cur, query, new_customers, fetch=True)
            for r in result:
                customer_map[(r[0], r[1], str(r[2]))] = r[3]
            logger.info(f"Inserted {len(new_customers)} new customers.")

        # 2. Insert Accounts for any newly inserted customers
        new_accounts = []
        for _, row in df.iterrows():
            c_id = customer_map[(row["first"], row["last"], str(row["dob"]))]
            if c_id not in account_map:
                account_map[c_id] = None
                acc_num = f"ACC-{c_id:08d}"
                new_accounts.append((c_id, acc_num, 'ACTIVE'))

        if new_accounts:
            query = """
            INSERT INTO account (customer_id, account_number, status)
            VALUES %s RETURNING customer_id, account_id;
            """
            result = execute_values(cur, query, new_accounts, fetch=True)
            for r in result:
                account_map[r[0]] = r[1]
            logger.info(f"Inserted {len(new_accounts)} new accounts.")

        # 3. Deduplicate & Insert Cards
        new_cards = []
        for _, row in df.iterrows():
            card_num = str(row["cc_num"])
            c_id = customer_map[(row["first"], row["last"], str(row["dob"]))]
            acc_id = account_map[c_id]
            if card_num not in card_map:
                card_map[card_num] = None
                new_cards.append((acc_id, card_num, 'CREDIT'))

        if new_cards:
            query = """
            INSERT INTO card (account_id, card_number, card_type)
            VALUES %s ON CONFLICT (card_number) DO NOTHING RETURNING card_number, card_id;
            """
            result = execute_values(cur, query, new_cards, fetch=True)
            if result:
                for r in result:
                    card_map[str(r[0])] = r[1]
            logger.info(f"Inserted {len(new_cards)} new cards.")

        # 4. Deduplicate & Insert Merchants
        new_merchants = []
        for _, row in df.iterrows():
            m_name = row["merchant"]
            if m_name not in merchant_map:
                merchant_map[m_name] = None
                new_merchants.append((
                    m_name, row["category"], float(row["merch_lat"]), float(row["merch_long"])
                ))

        if new_merchants:
            query = """
            INSERT INTO merchant (merchant_name, category, merch_lat, merch_long)
            VALUES %s ON CONFLICT (merchant_name) DO NOTHING RETURNING merchant_name, merchant_id;
            """
            result = execute_values(cur, query, new_merchants, fetch=True)
            if result:
                for r in result:
                    merchant_map[r[0]] = r[1]
            logger.info(f"Inserted {len(new_merchants)} new merchants.")

        # 5. Deduplicate & Insert Devices (derived from proxy)
        new_devices = []
        for _, row in df.iterrows():
            fp = derive_device_fingerprint(row["lat"], row["long"], row["zip"])
            if fp not in device_map:
                device_map[fp] = None
                new_devices.append((fp, 'BROWSER_MOBILE'))

        if new_devices:
            query = """
            INSERT INTO device (device_fingerprint, device_type)
            VALUES %s ON CONFLICT (device_fingerprint) DO NOTHING RETURNING device_fingerprint, device_id;
            """
            result = execute_values(cur, query, new_devices, fetch=True)
            if result:
                for r in result:
                    device_map[r[0]] = r[1]
            logger.info(f"Inserted {len(new_devices)} new devices.")

        # 6. Deduplicate & Insert IP Addresses (derived from proxy)
        new_ips = []
        for _, row in df.iterrows():
            ip_str, lat, lon = derive_ip_address(row["city"], row["state"], row["zip"], row["lat"], row["long"])
            if ip_str not in ip_map:
                ip_map[ip_str] = None
                new_ips.append((ip_str, lat, lon))

        if new_ips:
            query = """
            INSERT INTO ip_address (ip_str, lat, long)
            VALUES %s ON CONFLICT (ip_str) DO NOTHING RETURNING ip_str, ip_id;
            """
            result = execute_values(cur, query, new_ips, fetch=True)
            if result:
                for r in result:
                    ip_map[r[0]] = r[1]
            logger.info(f"Inserted {len(new_ips)} new IP addresses.")

        # 7. Insert Transactions
        transactions = []
        for _, row in df.iterrows():
            c_id = customer_map[(row["first"], row["last"], str(row["dob"]))]
            acc_id = account_map[c_id]
            card_id = card_map.get(str(row["cc_num"]))
            m_id = merchant_map.get(row["merchant"])
            fp = derive_device_fingerprint(row["lat"], row["long"], row["zip"])
            dev_id = device_map.get(fp)
            ip_str, _, _ = derive_ip_address(row["city"], row["state"], row["zip"], row["lat"], row["long"])
            ip_id = ip_map.get(ip_str)

            transactions.append((
                str(row["trans_num"]),
                str(row["trans_date_trans_time"]),
                int(row["unix_time"]),
                float(row["amt"]),
                acc_id,
                card_id,
                m_id,
                dev_id,
                ip_id,
                int(row["is_fraud"])
            ))

        query = """
        INSERT INTO transaction (trans_num, trans_date_trans_time, unix_time, amt, account_id, card_id, merchant_id, device_id, ip_id, is_fraud)
        VALUES %s ON CONFLICT (trans_num) DO NOTHING;
        """
        execute_values(cur, query, transactions)
        conn.commit()

        total_processed += len(df)
        total_transactions_inserted += len(transactions)
        logger.info(f"Committed chunk {chunk_idx + 1}. Total transactions processed: {total_processed}")

    cur.close()
    conn.close()
    logger.info(f"Successfully finished loading {total_transactions_inserted} transactions into PostgreSQL.")

def verify_counts():
    conn = get_connection()
    cur = conn.cursor()
    tables = ["customer", "account", "card", "merchant", "device", "ip_address", "transaction"]
    print("\n" + "="*50)
    print("PostgreSQL Database Entity Summary:")
    print("="*50)
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        cnt = cur.fetchone()[0]
        print(f" - {table.ljust(15)}: {cnt:>8,} records")

    cur.execute("SELECT COUNT(*) FROM transaction WHERE is_fraud = 1;")
    fraud_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM transaction;")
    total_tx = cur.fetchone()[0]
    rate = (fraud_cnt / total_tx * 100) if total_tx > 0 else 0
    print(f" - Fraudulent Tx  : {fraud_cnt:>8,} ({rate:.2f}%)")
    print("="*50 + "\n")
    cur.close()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Sparkov fraud dataset into PostgreSQL")
    parser.add_argument("--file", type=str, default=os.path.join(DATA_DIR, "fraudTrain.csv"), help="Path to CSV dataset")
    parser.add_argument("--limit", type=int, default=50000, help="Row limit (default 50,000 for fast verification; omit or set 0 for all)")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing row counts")
    args = parser.parse_args()

    if args.verify_only:
        verify_counts()
    else:
        limit = None if args.limit == 0 else args.limit
        load_data(args.file, limit=limit)
        verify_counts()

