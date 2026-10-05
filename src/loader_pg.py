"""
PostgreSQL Relational Loader for Intelligent Fraud Ring Detection
Loads fraudTest.csv / fraudTrain.csv into normalized PostgreSQL schema:
- customer (deduplicated by first, last, dob)
- account (linked to customer)
- card (linked to account, hashed cc_num)
- merchant (deduplicated by merchant name & category)
- device (derived from merchant + geo-terminal proxy)
- ip_address (derived from customer geo-location subnet proxy)
- transaction (linked to account, card, merchant, device, ip)
"""

import os
import sys
import hashlib
import argparse
from datetime import datetime
import pandas as pd
import psycopg

# Default DB Connection Parameters
DB_NAME = os.getenv("PGDATABASE", "fraud_db")
DB_USER = os.getenv("PGUSER", os.getenv("USER", "arnavbansal"))
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")

def get_connection_string():
    return f"dbname={DB_NAME} user={DB_USER} host={DB_HOST} port={DB_PORT}"

def hash_card(cc_num):
    return hashlib.sha256(str(cc_num).encode("utf-8")).hexdigest()

def derive_device_fingerprint(merchant_name, state):
    # Terminal proxy: Merchant POS / payment gateway terminal cluster within a state
    raw = f"TERM_{merchant_name.strip()}_{state.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

def derive_ip_address(city, state):
    # Geolocation subnet proxy: accounts in the same city/state share local ISP subnet blocks
    octet3 = (abs(hash(state.strip())) % 250) + 1
    octet4 = (abs(hash(city.strip())) % 250) + 1
    return f"198.51.{octet3}.{octet4}"

def load_data(filepath, limit=None):
    print(f"[*] Reading dataset: {filepath} (limit: {limit or 'ALL'})")
    df = pd.read_csv(filepath, nrows=limit)
    print(f"[*] Loaded {len(df):,} records into memory.")
    return df

def populate_database(df):
    conn_str = get_connection_string()
    print(f"[*] Connecting to PostgreSQL ({conn_str})...")

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            # 1. Customer deduplication
            print("[*] Processing customers...")
            cust_df = df[['first', 'last', 'dob', 'gender', 'street', 'city', 'state', 'zip']].drop_duplicates(
                subset=['first', 'last', 'dob']
            ).copy()
            
            # Map clean fields
            customer_rows = []
            for idx, r in cust_df.iterrows():
                email = f"{r['first'].lower().strip()}.{r['last'].lower().strip()}.{hash(r['dob']) % 10000}@ringdefense.net"
                phone = f"+1-555-{abs(hash(r['first'] + r['last'])) % 900 + 100:03d}-{abs(hash(r['dob'])) % 9000 + 1000:04d}"
                customer_rows.append((
                    r['first'].strip(),
                    r['last'].strip(),
                    email,
                    phone,
                    r['dob'],
                    True  # kyc_verified
                ))
            
            # Insert customers with ON CONFLICT DO NOTHING
            cur.executemany(
                """
                INSERT INTO customer (first_name, last_name, email, phone_number, date_of_birth, kyc_verified)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING;
                """,
                customer_rows
            )
            conn.commit()
            
            # Fetch customer IDs into lookup map
            cur.execute("SELECT customer_id, first_name, last_name, date_of_birth FROM customer;")
            cust_map = {}
            for cid, fn, ln, dob in cur.fetchall():
                cust_map[(fn, ln, str(dob))] = cid
            print(f"[+] Synced {len(cust_map):,} customers in PostgreSQL.")

            # 2. Account & Card mapping
            print("[*] Processing accounts and cards...")
            card_df = df[['first', 'last', 'dob', 'cc_num']].drop_duplicates(subset=['cc_num']).copy()
            
            account_rows = []
            for _, r in card_df.iterrows():
                cid = cust_map.get((r['first'].strip(), r['last'].strip(), str(r['dob'])))
                if cid:
                    acct_num = f"ACCT-{hashlib.md5(str(r['cc_num']).encode()).hexdigest()[:12].upper()}"
                    account_rows.append((cid, acct_num, 'checking', 2500.00, 'active'))
            
            cur.executemany(
                """
                INSERT INTO account (customer_id, account_number, account_type, balance, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (account_number) DO NOTHING;
                """,
                account_rows
            )
            conn.commit()
            
            cur.execute("SELECT account_id, account_number FROM account;")
            acct_map = {acc_num: aid for aid, acc_num in cur.fetchall()}
            print(f"[+] Synced {len(acct_map):,} accounts in PostgreSQL.")

            # Insert cards
            card_rows = []
            for _, r in card_df.iterrows():
                acct_num = f"ACCT-{hashlib.md5(str(r['cc_num']).encode()).hexdigest()[:12].upper()}"
                aid = acct_map.get(acct_num)
                if aid:
                    card_hash = hash_card(r['cc_num'])
                    # Determine card brand by first digit
                    cc_str = str(r['cc_num'])
                    ctype = 'visa' if cc_str.startswith('4') else ('mastercard' if cc_str.startswith('5') else 'other')
                    card_rows.append((aid, card_hash, ctype, '2028-12-31', 'active'))
            
            cur.executemany(
                """
                INSERT INTO card (account_id, card_number_hash, card_type, expiry_date, status)
                VALUES (%s, %s, %s, %s, %s);
                """,
                card_rows
            )
            conn.commit()

            cur.execute("SELECT card_id, account_id, card_number_hash FROM card;")
            card_map = {row[2]: row[0] for row in cur.fetchall()}
            print(f"[+] Synced {len(card_map):,} cards in PostgreSQL.")

            # 3. Merchant deduplication
            print("[*] Processing merchants...")
            merch_df = df[['merchant', 'category', 'city', 'state']].drop_duplicates(subset=['merchant']).copy()
            merch_rows = [
                (r['merchant'].strip(), r['category'].strip(), f"{r['city'].strip()}, {r['state'].strip()}")
                for _, r in merch_df.iterrows()
            ]
            cur.executemany(
                """
                INSERT INTO merchant (merchant_name, mcc_category, location)
                VALUES (%s, %s, %s);
                """,
                merch_rows
            )
            conn.commit()

            cur.execute("SELECT merchant_id, merchant_name FROM merchant;")
            merch_map = {name: mid for mid, name in cur.fetchall()}
            print(f"[+] Synced {len(merch_map):,} merchants in PostgreSQL.")

            # 4. Device and IP address proxies
            print("[*] Processing devices and IP proxies...")
            # Compute fingerprints for all rows
            device_records = {}
            ip_records = {}
            for _, r in df.iterrows():
                dfp = derive_device_fingerprint(r['merchant'], r['state'])
                if dfp not in device_records:
                    device_records[dfp] = (dfp, 'pos_terminal', r['trans_date_trans_time'])
                
                ip = derive_ip_address(r['city'], r['state'])
                if ip not in ip_records:
                    ip_records[ip] = (ip, 'US', False)

            # Insert devices
            cur.executemany(
                """
                INSERT INTO device (device_fingerprint, device_type, last_seen_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (device_fingerprint) DO NOTHING;
                """,
                list(device_records.values())
            )
            conn.commit()

            cur.execute("SELECT device_id, device_fingerprint FROM device;")
            device_map = {fp: did for did, fp in cur.fetchall()}
            print(f"[+] Synced {len(device_map):,} devices in PostgreSQL.")

            # Insert IPs
            cur.executemany(
                """
                INSERT INTO ip_address (ip_address, country, is_vpn)
                VALUES (%s, %s, %s);
                """,
                list(ip_records.values())
            )
            conn.commit()

            cur.execute("SELECT ip_id, ip_address FROM ip_address;")
            ip_map = {ip: iid for iid, ip in cur.fetchall()}
            print(f"[+] Synced {len(ip_map):,} IP addresses in PostgreSQL.")

            # 5. Insert Transactions
            print("[*] Inserting transactions in batches...")
            txn_records = []
            for _, r in df.iterrows():
                acct_num = f"ACCT-{hashlib.md5(str(r['cc_num']).encode()).hexdigest()[:12].upper()}"
                aid = acct_map.get(acct_num)
                chash = hash_card(r['cc_num'])
                cid = card_map.get(chash)
                mid = merch_map.get(r['merchant'].strip())
                dfp = derive_device_fingerprint(r['merchant'], r['state'])
                did = device_map.get(dfp)
                ip = derive_ip_address(r['city'], r['state'])
                ipid = ip_map.get(ip)

                if aid and mid:
                    txn_records.append((
                        aid,
                        cid,
                        mid,
                        did,
                        ipid,
                        float(r['amt']),
                        r['trans_date_trans_time'],
                        'approved',
                        bool(r['is_fraud'])
                    ))

            # Batch insert transactions using execute_batch or COPY
            batch_size = 10000
            total_txns = len(txn_records)
            for i in range(0, total_txns, batch_size):
                batch = txn_records[i:i + batch_size]
                cur.executemany(
                    """
                    INSERT INTO transaction (
                        account_id, card_id, merchant_id, device_id, ip_id, amount, txn_timestamp, status, fraud_label
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    batch
                )
                conn.commit()
                print(f"    -> Inserted {min(i + batch_size, total_txns):,}/{total_txns:,} transactions...")

            # Summary check
            cur.execute("SELECT COUNT(*) FROM transaction;")
            count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM transaction WHERE fraud_label = TRUE;")
            fraud_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM customer;")
            cust_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM device;")
            dev_count = cur.fetchone()[0]
            print(f"[SUCCESS] Step 1 Complete:")
            print(f"    - Customers: {cust_count:,}")
            print(f"    - Accounts: {len(acct_map):,}")
            print(f"    - Merchants: {len(merch_map):,}")
            print(f"    - Devices: {dev_count:,}")
            print(f"    - IP Addresses: {len(ip_map):,}")
            print(f"    - Transactions: {count:,} (Fraud: {fraud_count:,})")

def truncate_tables():
    conn_str = get_connection_string()
    print("[*] Truncating existing PostgreSQL tables...")
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE alert, transaction, card, account, customer, merchant, device, ip_address, analyst CASCADE;")
            conn.commit()
    print("[+] All tables truncated.")

def main():
    parser = argparse.ArgumentParser(description="Load fraud dataset into PostgreSQL")
    parser.add_argument("--file", default="Datasets/fraudTest.csv", help="Path to CSV dataset")
    parser.add_argument("--limit", type=int, default=50000, help="Number of records to load (default: 50,000 for rapid iteration)")
    parser.add_argument("--truncate", action="store_true", help="Truncate tables before loading")
    args = parser.parse_args()

    if args.truncate:
        truncate_tables()

    df = load_data(args.file, limit=args.limit)
    populate_database(df)

if __name__ == "__main__":
    main()

