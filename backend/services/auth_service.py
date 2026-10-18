from contextlib import closing
"""Local accounts and expiring, revocable bearer sessions shared by both UIs."""
import os
import re
import secrets
import sqlite3
import time
import tempfile
import uuid
from pathlib import Path

import jwt
from pwdlib import PasswordHash

from backend.config import DB_PATH, JWT_SECRET_KEY, JWT_EXPIRE_MINUTES


class AuthService:
    def __init__(self, db_path=DB_PATH, secret=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.passwords = PasswordHash.recommended()
        self.secret = secret or self._signing_secret()
        self.dummy_hash = self.passwords.hash(secrets.token_urlsafe(32))
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS login_attempts (
                    username TEXT PRIMARY KEY, failures INTEGER NOT NULL,
                    blocked_until REAL NOT NULL
                );
            """)

    def _signing_secret(self):
        configured = JWT_SECRET_KEY
        if len(configured) >= 32 and not configured.startswith(("default-", "your_")):
            return configured
        # Persist a strong local fallback instead of using a predictable default.
        path = self.db_path.parent / ".auth_signing_key"
        value = secrets.token_urlsafe(64)
        fd, temporary = tempfile.mkstemp(prefix='.auth-key-',dir=self.db_path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                # Publish the complete key atomically without replacing an existing key.
                os.link(temporary,path)
            except FileExistsError:
                value = path.read_text(encoding='utf-8').strip()
            if len(value) < 32:
                raise RuntimeError('Local signing key is invalid; set JWT_SECRET_KEY to at least 32 random characters.')
            return value
        finally:
            os.unlink(temporary)

    @staticmethod
    def normalize_username(username):
        name = username.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", name):
            raise ValueError("Username must contain 3–64 letters, numbers, dots, underscores or hyphens.")
        return name

    def register(self, username, password):
        name = self.normalize_username(username)
        if not 12 <= len(password) <= 128:
            raise ValueError("Password must contain 12–128 characters.")
        user_id = str(uuid.uuid4())
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            try:
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)",
                             (user_id, name, self.passwords.hash(password), time.time()))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Username is already registered.") from exc
        return {"id": user_id, "username": name}

    def login(self, username, password):
        name = username.strip().lower()
        now = time.time()
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            attempt = conn.execute("SELECT failures, blocked_until FROM login_attempts WHERE username=?", (name,)).fetchone()
            if attempt and attempt[0] >= 10 and attempt[1] > now:
                raise PermissionError("Too many login attempts. Try again in 15 minutes.")
            row = conn.execute("SELECT id, username, password_hash FROM users WHERE username=?", (name,)).fetchone()
            valid = self.passwords.verify(password, row[2] if row else self.dummy_hash)
            if not row or not valid:
                failures = (attempt[0] if attempt and attempt[1] > now else 0) + 1
                until = attempt[1] if attempt and attempt[1] > now else now + 900
                conn.execute("INSERT INTO login_attempts VALUES (?, ?, ?) ON CONFLICT(username) DO UPDATE SET failures=excluded.failures, blocked_until=excluded.blocked_until",
                             (name, failures, until))
                conn.commit()
                raise ValueError("Invalid username or password.")
            conn.execute("DELETE FROM login_attempts WHERE username=?", (name,))
            session_id = str(uuid.uuid4())
            expiry = now + JWT_EXPIRE_MINUTES * 60
            conn.execute("INSERT INTO auth_sessions VALUES (?, ?, ?, 0)", (session_id, row[0], expiry))
            conn.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now,))
        token = jwt.encode({"sub": row[0], "jti": session_id, "iat": int(now),
                            "exp": int(expiry), "iss": "ds-agent", "aud": "ds-agent-api"}, self.secret, algorithm="HS256")
        return {"access_token": token, "token_type": "bearer", "user": {"id": row[0], "username": row[1]}}

    def authenticate(self, token):
        try:
            claims = jwt.decode(token, self.secret, algorithms=["HS256"], audience="ds-agent-api",
                                issuer="ds-agent", options={"require": ["sub", "jti", "iat", "exp"]})
        except jwt.PyJWTError as exc:
            raise ValueError("Invalid or expired session. Please sign in.") from exc
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            row = conn.execute("""SELECT u.id, u.username FROM users u JOIN auth_sessions s
                ON s.user_id=u.id WHERE s.id=? AND s.user_id=? AND s.revoked=0 AND s.expires_at>?""",
                               (claims["jti"], claims["sub"], time.time())).fetchone()
        if not row:
            raise ValueError("Invalid or expired session. Please sign in.")
        return {"id": row[0], "username": row[1], "session_id": claims["jti"]}

    def logout(self, session_id):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("UPDATE auth_sessions SET revoked=1 WHERE id=?", (session_id,))


auth_service = AuthService()
