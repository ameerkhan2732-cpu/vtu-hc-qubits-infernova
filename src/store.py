"""Local storage for QuantaGuard Chat: accounts, chats, BB84 keys and messages.

Everything lives in one SQLite file (qg_data/quantaguard.db, git-ignored) on
the machine that runs the Streamlit server, so every phone that opens the app
sees the same accounts and chats.

Passwords are stored only as salted PBKDF2-SHA256 hashes. Messages are stored
as AES-GCM ciphertext; each one records which key epoch encrypted it.
Demo limitation: the BB84 key for a chat is kept on this server so both
endpoints can use it. In real QKD each device receives its key from a
quantum link and the server would never see it.
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.environ.get(
    "QG_DB", Path(__file__).resolve().parent.parent / "qg_data" / "quantaguard.db"))
PBKDF2_ROUNDS = 200_000
ID_RE = re.compile(r"^\d{10}$")
_lock = threading.Lock()


@contextmanager
def _db():
    with _lock:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB_PATH, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def now():
    return datetime.now().isoformat(timespec="seconds")


def init():
    with _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            uid TEXT PRIMARY KEY, name TEXT NOT NULL,
            salt BLOB NOT NULL, pw BLOB NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tokens(
            token TEXT PRIMARY KEY, uid TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS convs(
            id TEXT PRIMARY KEY, a TEXT NOT NULL, b TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS keys(
            conv TEXT NOT NULL, epoch INTEGER NOT NULL, key BLOB,
            verdict TEXT, qber REAL, key_len INTEGER, noise REAL, eve INTEGER,
            by_uid TEXT, ts TEXT, PRIMARY KEY(conv, epoch));
        CREATE TABLE IF NOT EXISTS msgs(
            id INTEGER PRIMARY KEY AUTOINCREMENT, conv TEXT NOT NULL,
            sender TEXT NOT NULL, epoch INTEGER, blob BLOB, note TEXT, ts TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS msgs_conv ON msgs(conv, id);
        """)


# --------------------------------------------------------------------------- #
# accounts
# --------------------------------------------------------------------------- #
def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, PBKDF2_ROUNDS)


def register(uid, name, pw):
    """Create an account. Returns an error message, or None on success."""
    uid, name = uid.strip(), name.strip()
    if not ID_RE.match(uid):
        return "Your QuantaGuard number must be exactly 10 digits."
    if not 1 <= len(name) <= 30:
        return "Enter a display name (up to 30 characters)."
    if len(pw) < 6:
        return "Password must be at least 6 characters."
    salt = secrets.token_bytes(16)
    with _db() as c:
        if c.execute("SELECT 1 FROM users WHERE uid=?", (uid,)).fetchone():
            return "That number is already registered. Sign in instead."
        c.execute("INSERT INTO users VALUES (?,?,?,?,?)",
                  (uid, name, salt, _hash(pw, salt), now()))
    return None


def check_login(uid, pw):
    """Return the display name if the number and password match, else None."""
    with _db() as c:
        row = c.execute("SELECT name, salt, pw FROM users WHERE uid=?",
                        (uid.strip(),)).fetchone()
    if row and hmac.compare_digest(_hash(pw, row["salt"]), row["pw"]):
        return row["name"]
    return None


def user_name(uid):
    with _db() as c:
        row = c.execute("SELECT name FROM users WHERE uid=?", (uid,)).fetchone()
    return row["name"] if row else None


def new_token(uid):
    token = secrets.token_urlsafe(24)
    with _db() as c:
        c.execute("INSERT INTO tokens VALUES (?,?,?)", (token, uid, now()))
    return token


def token_user(token):
    with _db() as c:
        row = c.execute("SELECT uid FROM tokens WHERE token=?", (token,)).fetchone()
    return row["uid"] if row else None


def drop_token(token):
    with _db() as c:
        c.execute("DELETE FROM tokens WHERE token=?", (token,))


# --------------------------------------------------------------------------- #
# chats, keys, messages
# --------------------------------------------------------------------------- #
def conv_id(a, b):
    return "|".join(sorted((a, b)))


def start_chat(a, b):
    cid = conv_id(a, b)
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO convs VALUES (?,?,?,?)", (cid, a, b, now()))
    return cid


def chats_for(uid):
    """Chats of a user, newest activity first."""
    with _db() as c:
        rows = c.execute("""
            SELECT v.id, CASE WHEN v.a=? THEN v.b ELSE v.a END AS other, u.name,
                   COALESCE((SELECT MAX(ts) FROM msgs m WHERE m.conv=v.id), v.created) AS last_ts
            FROM convs v JOIN users u ON u.uid = CASE WHEN v.a=? THEN v.b ELSE v.a END
            WHERE v.a=? OR v.b=? ORDER BY last_ts DESC""", (uid, uid, uid, uid)).fetchall()
    return [dict(r) for r in rows]


def latest_key(cid):
    with _db() as c:
        row = c.execute("SELECT * FROM keys WHERE conv=? ORDER BY epoch DESC LIMIT 1",
                        (cid,)).fetchone()
    return dict(row) if row else None


def keys_by_epoch(cid):
    with _db() as c:
        rows = c.execute("SELECT epoch, key FROM keys WHERE conv=?", (cid,)).fetchall()
    return {r["epoch"]: r["key"] for r in rows}


def add_key(cid, key, verdict, qber, key_len, noise, eve, by_uid, note):
    """Store the result of a key exchange and post a system note in the chat."""
    with _db() as c:
        row = c.execute("SELECT COALESCE(MAX(epoch), 0) AS e FROM keys WHERE conv=?",
                        (cid,)).fetchone()
        epoch = row["e"] + 1
        ts = now()
        c.execute("INSERT INTO keys VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (cid, epoch, key, verdict, qber, key_len, noise, int(eve), by_uid, ts))
        c.execute("INSERT INTO msgs(conv, sender, epoch, blob, note, ts) VALUES (?,?,?,?,?,?)",
                  (cid, "system", epoch, None, note, ts))
    return epoch


def add_msg(cid, sender, epoch, blob):
    with _db() as c:
        c.execute("INSERT INTO msgs(conv, sender, epoch, blob, note, ts) VALUES (?,?,?,?,?,?)",
                  (cid, sender, epoch, blob, None, now()))


def messages(cid, limit=200):
    with _db() as c:
        rows = c.execute("SELECT * FROM (SELECT * FROM msgs WHERE conv=? ORDER BY id DESC LIMIT ?)"
                         " ORDER BY id", (cid, limit)).fetchall()
    return [dict(r) for r in rows]
