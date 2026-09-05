"""
Real authentication: bcrypt-hashed passwords, SQLite-backed users +
sessions. Simple token-based auth — enough for real, verifiable login
without extra library overhead.
"""

import sqlite3
import bcrypt
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone

DB_PATH = Path(__file__).parent / "data" / "users.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_user(username, password):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        raise ValueError("Username already exists")

    conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, hash_password(password), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def authenticate_user(username, password):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        return True
    return False


def create_session(username):
    token = secrets.token_hex(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (token, username, expires_at) VALUES (?, ?, ?)",
        (token, username, expires_at),
    )
    conn.commit()
    conn.close()
    return token


def get_user_from_token(token):
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    conn.close()
    if not row:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return None
    return row["username"]