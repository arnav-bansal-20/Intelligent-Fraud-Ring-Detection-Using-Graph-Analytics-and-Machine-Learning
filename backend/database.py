import psycopg2
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
from backend.config import PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE, MONGO_URI, MONGO_DB_NAME

# MongoDB singleton
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB_NAME]

def get_pg_connection():
    """
    Returns a new PostgreSQL connection with RealDictCursor.
    Caller must close the connection or use context manager.
    """
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE,
        cursor_factory=RealDictCursor
    )
    return conn

def get_mongo_db():
    return mongo_db

