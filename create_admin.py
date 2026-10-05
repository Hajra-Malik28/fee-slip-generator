from getpass import getpass
from werkzeug.security import generate_password_hash
from database import init_db, get_connection

init_db()

password = getpass("Enter admin password: ")
confirm = getpass("Confirm admin password: ")

if len(password) < 8:
    print("Password must be at least 8 characters long.")
    raise SystemExit(1)

if password != confirm:
    print("Passwords do not match.")
    raise SystemExit(1)

conn = get_connection()

conn.execute(
    """
    INSERT INTO users (username, password_hash, role, must_change_password)
    VALUES (?, ?, 'admin', 0)
    ON CONFLICT(username) DO UPDATE SET
        password_hash = excluded.password_hash,
        role = 'admin',
        must_change_password = 0
    """,
    ("admin", generate_password_hash(password)),
)

conn.commit()

user = conn.execute(
    "SELECT username, role FROM users WHERE username = ?",
    ("admin",),
).fetchone()

conn.close()

if user:
    print("ADMIN READY")
    print("Username:", user["username"])
else:
    print("Could not create admin user.")

    