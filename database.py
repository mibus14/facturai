import os
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL", "")
IS_POSTGRES = bool(DATABASE_URL)

def _clean_pg_url(url):
    """Strip parameters psycopg2 doesn't support (e.g. channel_binding)."""
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    p = urlparse(url)
    qs = parse_qs(p.query, keep_blank_values=True)
    qs.pop("channel_binding", None)
    cleaned = urlunparse(p._replace(query=urlencode(qs, doseq=True)))
    return cleaned

if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras
    _raw = DATABASE_URL.replace("postgres://", "postgresql://", 1) \
           if DATABASE_URL.startswith("postgres://") else DATABASE_URL
    _PG_URL = _clean_pg_url(_raw)
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
            return _Row(dict(row))
        return _Row({k: row[k] for k in row.keys()})

    def fetchone(self):
        return self._wrap(self._raw.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._raw.fetchall()]


class Connection:
    def __init__(self):
        if IS_POSTGRES:
            self._conn = psycopg2.connect(_PG_URL)
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
        if self._is_pg:
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
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
        subscription_status TEXT DEFAULT 'inactive',
        invoices_created INTEGER DEFAULT 0,
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
"""

_SCHEMA_PG = """
    CREATE TABLE IF NOT EXISTS users (
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
    );
    CREATE TABLE IF NOT EXISTS invoices (
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
    );
"""

_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN rfc TEXT",
    "ALTER TABLE users ADD COLUMN regimen_fiscal TEXT DEFAULT '612'",
    "ALTER TABLE users ADD COLUMN cp TEXT",
    "ALTER TABLE invoices ADD COLUMN rfc_receptor TEXT",
    "ALTER TABLE invoices ADD COLUMN regimen_fiscal_receptor TEXT",
    "ALTER TABLE invoices ADD COLUMN cp_receptor TEXT",
    "ALTER TABLE invoices ADD COLUMN uso_cfdi TEXT DEFAULT 'G03'",
    "ALTER TABLE invoices ADD COLUMN forma_pago TEXT DEFAULT '03'",
    "ALTER TABLE invoices ADD COLUMN metodo_pago TEXT DEFAULT 'PUE'",
    "ALTER TABLE invoices ADD COLUMN moneda TEXT DEFAULT 'MXN'",
]


def init_db():
    conn = get_db()
    schema = _SCHEMA_PG if IS_POSTGRES else _SCHEMA_SQLITE

    if IS_POSTGRES:
        cur = conn._conn.cursor()
        for stmt in schema.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
    else:
        conn._conn.executescript(schema)

    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
        except Exception:
            pass

    conn.commit()
    conn.close()
