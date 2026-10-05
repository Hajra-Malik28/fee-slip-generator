import os
import sqlite3

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fees.db")


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS challans (
            challan_no INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            father_name TEXT NOT NULL,
            reg_no TEXT NOT NULL,
            degree TEXT NOT NULL,
            semester TEXT NOT NULL,
            batch TEXT NOT NULL,
            installment TEXT NOT NULL,
            fee_type TEXT NOT NULL,
            tuition_fee INTEGER NOT NULL,
            security_fee INTEGER NOT NULL,
            other_fee INTEGER NOT NULL DEFAULT 0,
            total_fee INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL
        )
    """)

    # Purani table mein "kis ne slip banayi" ka column add karna (purana data nahi mitta)
    columns = [r["name"] for r in conn.execute("PRAGMA table_info(challans)")]
    if "created_by" not in columns:
        conn.execute("ALTER TABLE challans ADD COLUMN created_by TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'student')),
            must_change_password INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()