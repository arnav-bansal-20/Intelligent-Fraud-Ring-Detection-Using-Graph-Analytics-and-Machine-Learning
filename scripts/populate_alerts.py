#!/usr/bin/env python3
"""
Populate PostgreSQL 'alert' table for high risk transactions (risk_score >= 0.70).
"""

import os
import sys
import logging
import psycopg2
from pymongo import MongoClient

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.db_config import (
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE,
    MONGO_URI, MONGO_DB_NAME
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def populate_alerts(threshold: float = 0.70):
    logger.info(f"Connecting to MongoDB and fetching high-risk transactions (risk_score >= {threshold})...")
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    coll = db["fraud_features"]

    high_risk_docs = list(coll.find({"risk_score": {"$gte": threshold}}))
    logger.info(f"Found {len(high_risk_docs)} high-risk transactions in MongoDB.")

    if not high_risk_docs:
        return

    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE
    )
    cur = conn.cursor()

    # Get trans_num -> transaction_id mapping
    trans_nums = [d["trans_num"] for d in high_risk_docs]
    cur.execute("SELECT trans_num, transaction_id FROM transaction WHERE trans_num = ANY(%s);", (trans_nums,))
    tx_map = {r[0]: r[1] for r in cur.fetchall()}

    # Get default analyst
    cur.execute("SELECT analyst_id FROM analyst LIMIT 1;")
    analyst_row = cur.fetchone()
    analyst_id = analyst_row[0] if analyst_row else None

    alerts_to_insert = []
    for d in high_risk_docs:
        t_id = tx_map.get(d["trans_num"])
        if t_id:
            score = d["risk_score"]
            notes = (f"Automated Alert: risk_score={score:.4f}, hops_to_flagged={d.get('hops_to_nearest_flagged')}, "
                     f"shared_devices={d.get('shared_device_count')}, degree={d.get('account_degree')}")
            alerts_to_insert.append((t_id, score, 'OPEN', analyst_id, notes))

    query = """
    INSERT INTO alert (transaction_id, risk_score, alert_status, analyst_id, notes)
    VALUES %s
    ON CONFLICT (transaction_id) DO UPDATE SET risk_score = EXCLUDED.risk_score, notes = EXCLUDED.notes;
    """
    from psycopg2.extras import execute_values
    execute_values(cur, query, alerts_to_insert)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM alert;")
    cnt = cur.fetchone()[0]
    logger.info(f"Successfully populated {len(alerts_to_insert)} alerts in PostgreSQL (Total alerts: {cnt}).")

    cur.close()
    conn.close()

if __name__ == "__main__":
    populate_alerts()

