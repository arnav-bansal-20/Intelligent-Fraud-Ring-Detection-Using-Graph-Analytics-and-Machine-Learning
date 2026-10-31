import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
from backend.config import PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE, MONGO_URI, MONGO_DB_NAME

# MongoDB singleton
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB_NAME]

# PostgreSQL Connection Pool (Lazy-initialized)
_pg_pool = None

def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=PG_DATABASE,
            cursor_factory=RealDictCursor
        )
    return _pg_pool

class PooledConnectionWrapper:
    """Wraps pooled connection so conn.close() safely returns it to the pool."""
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._returned = False

    def close(self):
        if not self._returned:
            self._returned = True
            try:
                self._pool.putconn(self._conn)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_pg_connection():
    """Returns a pooled PostgreSQL connection wrapped for safe closing."""
    pool = get_pg_pool()
    raw_conn = pool.getconn()
    return PooledConnectionWrapper(raw_conn, pool)

def get_db():
    """
    FastAPI dependency yielding a connection from the pool and always closing/returning
    it in try/finally block.
    """
    conn = get_pg_connection()
    try:
        yield conn
    finally:
        conn.close()

def get_mongo_db():
    return mongo_db

# Cached Known Fraud Accounts Set
_fraud_accounts_cache = None

def get_known_fraud_accounts(cur=None, force_refresh: bool = False) -> set:
    """
    Returns the cached set of account IDs that have analyst-confirmed fraud or dataset labels.
    Refreshed when an alert is confirmed as fraud or force_refresh is True.
    """
    global _fraud_accounts_cache
    if _fraud_accounts_cache is None or force_refresh:
        should_close = False
        if cur is None:
            conn = get_pg_connection()
            cur = conn.cursor()
            should_close = True
        try:
            cur.execute("SELECT DISTINCT account_id FROM transaction WHERE is_fraud = true;")
            _fraud_accounts_cache = set(r["account_id"] for r in cur.fetchall())
        finally:
            if should_close:
                cur.close()
                conn.close()
    return _fraud_accounts_cache

def refresh_fraud_accounts_cache(cur=None) -> set:
    """Explicitly refreshes and returns the known fraud accounts cache."""
    return get_known_fraud_accounts(cur=cur, force_refresh=True)
