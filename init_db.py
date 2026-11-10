"""
FinFlow Database Initialization Script
======================================
BFB 321 - Group 28

Provisions MySQL tables and seeds realistic demo data on Aiven Cloud.
Follows Rubric B1.3:
- Builds database from scratch with one command
- Populates realistic demo records
- Supports safe teardown with '--reset' flag (children dropped before parents)

Usage:
    python init_db.py          # creates tables and loads seed data if empty
    python init_db.py --reset  # drops existing tables, rebuilds schema, and reseeds
"""

import os
import sys
from db import connect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TABLES_IN_DROP_ORDER = ["cartons", "orders", "inventory"]


def read_statements(filename):
    """Reads SQL statements from a file, ignoring comments and empty lines."""
    path = os.path.join(BASE_DIR, "database", filename)
    if not os.path.exists(path):
        path = os.path.join(BASE_DIR, filename)

    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def init_database(reset=False):
    """Connects to MySQL, optionally drops existing tables, creates schema, and seeds data."""
    conn = connect()
    with conn:
        with conn.cursor() as cur:
            if reset:
                print("Dropping existing tables (children before parents)...")
                for table in TABLES_IN_DROP_ORDER:
                    cur.execute(f"DROP TABLE IF EXISTS {table}")
                print("Existing tables dropped.")

            print("Applying database/schema.sql ...")
            for stmt in read_statements("schema.sql"):
                cur.execute(stmt)

            cur.execute("SELECT COUNT(*) AS n FROM orders")
            res = cur.fetchone()
            order_count = res["n"] if res else 0

            if order_count == 0:
                print("Loading initial demo records from database/seed.sql ...")
                for stmt in read_statements("seed.sql"):
                    cur.execute(stmt)
                print("Seed data loaded successfully.")
            else:
                print(f"Database already contains {order_count} orders — seed skipped.")

            conn.commit()

            print("\nDatabase Verification on Aiven MySQL:")
            for table in reversed(TABLES_IN_DROP_ORDER):
                cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
                count = cur.fetchone()["n"]
                print(f"  [OK] Table '{table}': {count} rows present")

    print("\nInitialization complete! Cloud database is ready.")


if __name__ == "__main__":
    should_reset = "--reset" in sys.argv
    init_database(reset=should_reset)
