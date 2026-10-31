#!/usr/bin/env python3
"""
Seed Users Script
Creates default analyst, manager, and admin users with bcrypt password hashes
read securely from environment variables.
"""

import os
import sys
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.db_config import PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE

def hash_pw(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def seed_users():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE,
        cursor_factory=RealDictCursor
    )
    cur = conn.cursor()

    users = [
        {
            "username": "analyst",
            "password": os.getenv("ANALYST_PASSWORD", "password123"),
            "role": "analyst"
        },
        {
            "username": "manager",
            "password": os.getenv("MANAGER_PASSWORD", "password123"),
            "role": "manager"
        },
        {
            "username": "admin",
            "password": os.getenv("ADMIN_PASSWORD", "password123"),
            "role": "admin"
        }
    ]

    print("Seeding users into PostgreSQL 'analyst' table...")
    for u in users:
        pw_hash = hash_pw(u["password"])
        cur.execute("""
            INSERT INTO analyst (username, password_hash, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (username) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                role = EXCLUDED.role
            RETURNING analyst_id, username, role;
        """, (u["username"], pw_hash, u["role"]))
        row = cur.fetchone()
        print(f"  User '{row['username']}' (role: {row['role']}) seeded successfully with ID {row['analyst_id']}.")

    conn.commit()
    cur.close()
    conn.close()
    print("User seeding completed successfully!")

if __name__ == "__main__":
    seed_users()

