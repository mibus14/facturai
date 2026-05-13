import os
import sqlite3
from urllib.parse import urlparse, parse_qs

DATABASE_URL = os.getenv("DATABASE_URL", "")
IS_POSTGRES = bool(DATABASE_URL)

def _parse_pg_url(url):
    url = url.replace("postgres://", "postgresql://", 1)
    p = urlparse(url)
    qs = parse_qs(p.query)
    kwargs = {
        "host": p.hostname,
        "port": p.port or 5432,
        "user": p.username,
        "password": p.password,
        "database": p.path.lstrip("/"),
    }
    if qs.get("sslmode", [""])[0] == "require":
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
    return kwargs

if IS_POSTGRES:
    import pg8000.dbapi as _pg
    _PG_KWARGS = _parse_pg_url(DATABASE_URL)
else:
    DB_PATH = "/tmp/facturai.db" if os.getenv("VERCEL") else os.path.join(os.path.dirname(__file__), "facturai.db")


class _Row(dict):
    """Dict that also supports integer indexing (like sqlite3.Row)."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _Cursor:
    def __init__(self, raw, is_pg):
        self._raw = raw
        self._is_pg = is_pg
        self.lastrowid = getattr(raw, "lastrowid", None)

    def _wrap(self, row):
        if row is None:
            return None
        if self._is_pg:
            cols = [d[0] for d in self._raw.description]
            return _Row(dict(zip(cols, row)))
        return _Row({k: row[k] for k in row.keys()})

    def fetchone(self):
        return self._wrap(self._raw.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._raw.fetchall()]


class Connection:
    def __init__(self):
        if IS_POSTGRES:
            self._conn = _pg.connect(**_PG_KWARGS)
        else:
            self._conn = sqlite3.connect(DB_PATH)
            self._conn.row_factory = sqlite3.Row
        self._is_pg = IS_POSTGRES

    def _adapt(self, sql):
        if not self._is_pg:
            return sql
        sql = sql.replace("?", "%s")
        sql = sql.replace("datetime('now')", "CURRENT_TIMESTAMP")
        sql = sql.replace("(CURRENT_TIMESTAMP)", "CURRENT_TIMESTAMP")
        sql = sql.replace("SELECT last_insert_rowid()", "SELECT lastval()")
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
        return sql

    def execute(self, sql, params=()):
        sql = self._adapt(sql)
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return _Cursor(cur, self._is_pg)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db() -> Connection:
    return Connection()


_SCHEMA_SQLITE = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        rfc TEXT,
        regimen_fiscal TEXT DEFAULT '612',
        cp TEXT,
        plan TEXT DEFAULT 'free',
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        mp_subscription_id TEXT,
        subscription_status TEXT DEFAULT 'inactive',
        invoices_created INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        invoice_number TEXT NOT NULL,
        client_name TEXT NOT NULL,
        client_email TEXT,
        client_address TEXT,
        rfc_receptor TEXT,
        regimen_fiscal_receptor TEXT,
        cp_receptor TEXT,
        uso_cfdi TEXT DEFAULT 'G03',
        forma_pago TEXT DEFAULT '03',
        metodo_pago TEXT DEFAULT 'PUE',
        moneda TEXT DEFAULT 'MXN',
        issue_date TEXT NOT NULL,
        due_date TEXT,
        items TEXT NOT NULL,
        subtotal REAL NOT NULL,
        tax_rate REAL DEFAULT 16,
        tax_amount REAL DEFAULT 0,
        total REAL NOT NULL,
        notes TEXT,
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        mp_payment_id TEXT,
        mp_subscription_id TEXT,
        plan TEXT,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'MXN',
        status TEXT DEFAULT 'pending',
        payment_method TEXT,
        description TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
"""

_SCHEMA_PG = [
    """CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        rfc TEXT,
        regimen_fiscal TEXT DEFAULT '612',
        cp TEXT,
        plan TEXT DEFAULT 'free',
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        subscription_status TEXT DEFAULT 'inactive',
        invoices_created INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS invoices (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        invoice_number TEXT NOT NULL,
        client_name TEXT NOT NULL,
        client_email TEXT,
        client_address TEXT,
        rfc_receptor TEXT,
        regimen_fiscal_receptor TEXT,
        cp_receptor TEXT,
        uso_cfdi TEXT DEFAULT 'G03',
        forma_pago TEXT DEFAULT '03',
        metodo_pago TEXT DEFAULT 'PUE',
        moneda TEXT DEFAULT 'MXN',
        issue_date TEXT NOT NULL,
        due_date TEXT,
        items TEXT NOT NULL,
        subtotal REAL NOT NULL,
        tax_rate REAL DEFAULT 16,
        tax_amount REAL DEFAULT 0,
        total REAL NOT NULL,
        notes TEXT,
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""",
]

_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS rfc TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS regimen_fiscal TEXT DEFAULT '612'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS cp TEXT",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS rfc_receptor TEXT",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS regimen_fiscal_receptor TEXT",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS cp_receptor TEXT",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS uso_cfdi TEXT DEFAULT 'G03'",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS forma_pago TEXT DEFAULT '03'",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS metodo_pago TEXT DEFAULT 'PUE'",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'MXN'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS mp_subscription_id TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT",
]


def init_db():
    conn = get_db()
    if IS_POSTGRES:
        cur = conn._conn.cursor()
        for stmt in _SCHEMA_PG:
            cur.execute(stmt)
        conn.commit()
    else:
        conn._conn.executescript(_SCHEMA_SQLITE)

    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            if IS_POSTGRES:
                try:
                    conn._conn.rollback()
                except Exception:
                    pass

    conn.commit()
    conn.close()
