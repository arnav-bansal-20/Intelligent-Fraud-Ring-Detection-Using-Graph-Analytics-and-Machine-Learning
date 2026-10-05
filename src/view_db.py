#!/usr/bin/env python3
"""
Terminal Database Explorer for Fraud Ring Detection Project
Displays tables, counts, schema relations, and live fraud ring clusters.
"""

import os
import psycopg
from datetime import datetime

DB_NAME = os.getenv("PGDATABASE", "fraud_db")
DB_USER = os.getenv("PGUSER", os.getenv("USER", "arnavbansal"))
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")

def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def main():
    conn_str = f"dbname={DB_NAME} user={DB_USER} host={DB_HOST} port={DB_PORT}"
    
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            # 1. Table Counts
            print_header("POSTGRESQL [fraud_db] — TABLE INVENTORY")
            cur.execute("""
                SELECT 
                    table_name, 
                    (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text::int AS row_count
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY row_count DESC;
            """)
            print(f"{'TABLE NAME':<25} {'ROW COUNT':>15}")
            print("-" * 42)
            for tbl, cnt in cur.fetchall():
                print(f"{tbl:<25} {cnt:>15,}")

            # 2. Customers & Accounts Sample
            print_header("CUSTOMER & ACCOUNT RECORDS (First 3)")
            cur.execute("""
                SELECT c.customer_id, c.first_name || ' ' || c.last_name as name,
                       c.email, a.account_number, a.account_type, a.balance
                FROM customer c
                JOIN account a ON c.customer_id = a.customer_id
                LIMIT 3;
            """)
            print(f"{'ID':<6} {'NAME':<20} {'EMAIL':<36} {'ACCOUNT NUMBER':<20} {'BALANCE':>10}")
            print("-" * 96)
            for cid, name, email, acct, atype, bal in cur.fetchall():
                print(f"{cid:<6} {name:<20} {email:<36} {acct:<20} ${float(bal):>9.2f}")

            # 3. Fraud Transactions Sample
            print_header("HIGH-VALUE FRAUDULENT TRANSACTIONS (Top 5)")
            cur.execute("""
                SELECT t.transaction_id, c.first_name || ' ' || c.last_name as customer,
                       m.merchant_name, t.amount, t.txn_timestamp, t.fraud_label
                FROM transaction t
                JOIN account a ON t.account_id = a.account_id
                JOIN customer c ON a.customer_id = c.customer_id
                JOIN merchant m ON t.merchant_id = m.merchant_id
                WHERE t.fraud_label = TRUE
                ORDER BY t.amount DESC
                LIMIT 5;
            """)
            print(f"{'TXN_ID':<8} {'CUSTOMER':<18} {'MERCHANT':<36} {'AMOUNT':>10} {'TIMESTAMP':<20} {'FRAUD?':<6}")
            print("-" * 104)
            for tid, cust, merch, amt, ts, fl in cur.fetchall():
                print(f"{tid:<8} {cust:<18} {merch[:34]:<36} ${float(amt):>9.2f} {str(ts):<20} {str(fl):<6}")

            # 4. Multi-Account Shared Device Fraud Rings
            print_header("COORDINATED FRAUD RINGS — MULTI-ACCOUNT SHARED DEVICES")
            cur.execute("""
                WITH fraud_devices AS (
                    SELECT DISTINCT device_id FROM transaction WHERE fraud_label = TRUE
                )
                SELECT d.device_id, d.device_fingerprint, m.merchant_name,
                       COUNT(DISTINCT t.account_id) as linked_accounts,
                       COUNT(t.transaction_id) as total_txns,
                       SUM(CASE WHEN t.fraud_label THEN 1 ELSE 0 END) as fraud_txns
                FROM transaction t
                JOIN fraud_devices fd ON t.device_id = fd.device_id
                JOIN device d ON t.device_id = d.device_id
                JOIN merchant m ON t.merchant_id = m.merchant_id
                GROUP BY d.device_id, d.device_fingerprint, m.merchant_name
                HAVING COUNT(DISTINCT t.account_id) > 1
                ORDER BY fraud_txns DESC, linked_accounts DESC
                LIMIT 4;
            """)
            rings = cur.fetchall()
            for did, dfp, merch, accounts, txns, frauds in rings:
                print(f"\n[!] FRAUD RING DETECTED on Device ID: {did} ({dfp[:20]}...)")
                print(f"    Merchant: {merch}")
                print(f"    Linked Accounts: {accounts} | Total Transactions: {txns} | Fraudulent Txns: {frauds}")
                
                # Fetch the accounts participating in this ring
                cur.execute("""
                    SELECT DISTINCT a.account_number, c.first_name || ' ' || c.last_name as name,
                           t.amount, t.fraud_label, t.txn_timestamp
                    FROM transaction t
                    JOIN account a ON t.account_id = a.account_id
                    JOIN customer c ON a.customer_id = c.customer_id
                    WHERE t.device_id = %s
                    ORDER BY t.fraud_label DESC, t.amount DESC
                    LIMIT 3;
                """, (did,))
                for acc, cname, amt, is_fr, ts in cur.fetchall():
                    tag = "[FRAUD]" if is_fr else "[CLEAN]"
                    print(f"      -> {tag:<7} {acc} ({cname}) - ${float(amt):.2f} on {ts}")

    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    main()
