"""Production WSGI entrypoint; initializes schema and safe catalogue seeds."""
import os

from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from app import app
from database import get_db, init_db
from seed import seed_database

# Render terminates HTTPS at its proxy. Trust only its forwarded scheme header.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=0, x_port=0, x_prefix=0)

with app.app_context():
    init_db()
    db = get_db()
    seed_database(db)  # Idempotent; it never deletes or replaces catalogue/loan rows.
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    bootstrap_password = os.getenv("INITIAL_USER_PASSWORD")
    if user_count == 0 and bootstrap_password:
        if len(bootstrap_password) < 16:
            raise RuntimeError("INITIAL_USER_PASSWORD must be at least 16 characters.")
        username = (os.getenv("INITIAL_USER_USERNAME") or "reader").strip()
        email = (os.getenv("INITIAL_USER_EMAIL") or "reader@example.invalid").strip()
        full_name = (os.getenv("INITIAL_USER_FULL_NAME") or "Library Reader").strip()
        db.execute(
            "INSERT INTO users(username,email,full_name,password_hash) VALUES(?,?,?,?)",
            (username, email, full_name, generate_password_hash(bootstrap_password)),
        )
        app.logger.info("Initial production account provisioned.")
