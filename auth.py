import hashlib
import hmac
import secrets
import streamlit as st
from database import get_connection

PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def password_policy_errors(password: str):
    errors = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Use no more than {MAX_PASSWORD_LENGTH} characters.")
    if not any(c.islower() for c in password):
        errors.append("Add at least one lowercase letter.")
    if not any(c.isupper() for c in password):
        errors.append("Add at least one uppercase letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Add at least one number.")
    if not any(not c.isalnum() for c in password):
        errors.append("Add at least one symbol, such as !, @, #, or $.")
    if password.lower() in {"password", "password123", "admin123", "qwerty123"}:
        errors.append("Choose a less predictable password.")
    return errors


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, rounds, salt_hex, expected = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def user_count() -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM app_users")
        count = cur.fetchone()[0]
        cur.close()
        return count
    finally:
        conn.close()


def create_first_admin(username: str, password: str):
    username = username.strip()
    if len(username) < 4 or len(username) > 60:
        raise ValueError("Username must be 4–60 characters.")
    errors = password_policy_errors(password)
    if errors:
        raise ValueError("Password does not meet policy: " + " ".join(errors))
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM app_users")
        if cur.fetchone()[0] != 0:
            raise ValueError("Initial admin has already been created.")
        cur.execute(
            "INSERT INTO app_users (username, password_hash, role) VALUES (%s,%s,'Admin')",
            (username, hash_password(password)),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def authenticate(username: str, password: str):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, username, password_hash, role, active FROM app_users WHERE username=%s",
            (username.strip(),),
        )
        user = cur.fetchone()
        cur.close()
        if not user or not user["active"]:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return {"id": user["id"], "username": user["username"], "role": user["role"]}
    finally:
        conn.close()


def add_user(username: str, password: str, role: str):
    username = username.strip()
    if len(username) < 4 or len(username) > 60:
        raise ValueError("Username must be 4–60 characters.")
    errors = password_policy_errors(password)
    if errors:
        raise ValueError("Password does not meet policy: " + " ".join(errors))
    if role not in {"Admin", "Coordinator", "Secretary"}:
        raise ValueError("Invalid role.")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO app_users (username,password_hash,role) VALUES (%s,%s,%s)",
            (username, hash_password(password), role),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def list_users():
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, username, role, active, created_at FROM app_users ORDER BY id")
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()


def set_user_active(user_id: int, active: bool):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE app_users SET active=%s WHERE id=%s", (active, user_id))
        conn.commit()
        cur.close()
    finally:
        conn.close()


def change_password(user_id: int, old_password: str, new_password: str):
    errors = password_policy_errors(new_password)
    if errors:
        raise ValueError("Password does not meet policy: " + " ".join(errors))
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT password_hash FROM app_users WHERE id=%s AND active=TRUE", (user_id,))
        row = cur.fetchone()
        cur.close()
        if not row or not verify_password(old_password, row["password_hash"]):
            raise ValueError("Current password is incorrect.")
        cur = conn.cursor()
        cur.execute("UPDATE app_users SET password_hash=%s WHERE id=%s", (hash_password(new_password), user_id))
        conn.commit()
        cur.close()
    finally:
        conn.close()
