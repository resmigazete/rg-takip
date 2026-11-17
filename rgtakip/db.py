"""SQLite şeması. Sonradan PostgreSQL'e taşımak kolay olsun diye düz SQL."""
import os
import sqlite3
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    date TEXT NOT NULL,            -- YYYY-MM-DD
    kind TEXT NOT NULL DEFAULT 'normal',  -- normal | mukerrer | ek
    index_hash TEXT,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, kind)
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_date TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    section TEXT,                  -- bölüm / başlık grubu
    doc_type TEXT,                 -- kanun, yonetmelik, atama, ...
    title TEXT NOT NULL,
    issuer TEXT DEFAULT '',        -- yayımlayan kurum ("Sağlık Bakanlığından:")
    body TEXT,
    is_health INTEGER DEFAULT 0,
    health_score INTEGER DEFAULT 0,
    importance INTEGER DEFAULT 0,
    categories TEXT,               -- virgülle ayrılmış
    summary TEXT,
    notified INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_items_date ON items(issue_date);
CREATE INDEX IF NOT EXISTS idx_items_health ON items(is_health);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id),
    person TEXT,
    new_role TEXT,                 -- Vali, Rektör, Genel Müdür ...
    institution TEXT,              -- Ankara Valiliği, X Üniversitesi ...
    predecessor TEXT,
    action TEXT,                   -- atama | gorevden_alma
    is_key_role INTEGER DEFAULT 0,
    is_health INTEGER DEFAULT 0,
    raw TEXT
);
CREATE INDEX IF NOT EXISTS idx_app_person ON appointments(person);

-- Mevzuat değişikliği farkı için (ileri aşama: diff)
CREATE TABLE IF NOT EXISTS amendments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id),
    target_law TEXT,               -- değiştirilen mevzuat adı
    article_ref TEXT,              -- "5. madde" gibi
    change_kind TEXT,              -- degisti | eklendi | yururlukten_kalkti
    snippet TEXT
);

-- Takip listeleri
CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,            -- keyword | person | institution
    value TEXT NOT NULL
);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    if path != ":memory:" and os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(items)")]
    if "issuer" not in cols:  # eski veritabanlarını yükselt
        conn.execute("ALTER TABLE items ADD COLUMN issuer TEXT DEFAULT ''")
    return conn
