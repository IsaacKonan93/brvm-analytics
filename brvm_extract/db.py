"""SQLite storage for the extracted BOC data (brvm.db). Schema documented in EXTRACTION.md."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

-- one row per BOC PDF processed
CREATE TABLE IF NOT EXISTS documents (
    date TEXT PRIMARY KEY,           -- trading date (YYYY-MM-DD)
    file TEXT NOT NULL,
    file_size INTEGER,
    file_mtime REAL,
    pages INTEGER,
    locale TEXT,                     -- fr | en (number format of the PDF)
    layout TEXT,                     -- A (2016-08..2017-12) | B (..2022) | C (2023-2024) | D (2025+)
    parser_version TEXT,
    extracted_at TEXT,
    status TEXT,                     -- ok | partial | error
    n_warnings INTEGER,
    error TEXT
);

-- one row per weekday since 2016-08-01, from boc/manifest.csv (written by download_all.py):
-- was a bulletin published, and where is the official PDF on brvm.org (the web app links to it)
CREATE TABLE IF NOT EXISTS bulletins (
    date TEXT PRIMARY KEY,           -- weekday (YYYY-MM-DD)
    status TEXT,                     -- published | none (holiday, no session) | unavailable (broken link on brvm.org)
    url TEXT                         -- address of the PDF on brvm.org (published days)
);

-- number of shares of every listed stock, one snapshot per day, from brvm.org "Capitalisations"
-- (boc/shares_outstanding.csv written by fetch_shares.py); the web app's market structure uses it
CREATE TABLE IF NOT EXISTS shares_outstanding (
    date TEXT,                       -- day of the download
    symbol TEXT,
    name TEXT,
    shares REAL,                     -- number of shares
    price REAL,                      -- price shown on the page (latest session on brvm.org)
    float_cap REAL,                  -- free-float capitalisation (FCFA)
    global_cap REAL,                 -- total capitalisation (FCFA) = shares x price
    PRIMARY KEY (date, symbol)
);

-- master data, refreshed from the latest bulletin in which a security appears
CREATE TABLE IF NOT EXISTS securities (
    symbol TEXT PRIMARY KEY,
    asset_type TEXT,                 -- equity | right | bond
    name TEXT,
    country TEXT,                    -- CI SN BF BJ ML NE TG GW (equities: name suffix, else symbol suffix)
    sector TEXT,                     -- latest sector label / code
    compartment TEXT,                -- latest compartment
    issuer TEXT, coupon_rate REAL, issue_year INTEGER, maturity_year INTEGER,   -- bonds
    first_date TEXT, last_date TEXT
);

CREATE TABLE IF NOT EXISTS equity_quotes (
    date TEXT NOT NULL, symbol TEXT NOT NULL,
    name TEXT, group_label TEXT, sector_code TEXT, sector TEXT, compartment TEXT,
    prev_close REAL, open REAL, close REAL, avg_price REAL, change_pct REAL,
    volume INTEGER, value INTEGER, ref_price REAL, ytd_pct REAL,
    limit_low REAL, limit_high REAL,
    div_amount REAL, div_date TEXT, net_yield REAL, per REAL,
    status_flag TEXT, page INTEGER,
    PRIMARY KEY (date, symbol)
);

CREATE TABLE IF NOT EXISTS right_quotes (
    date TEXT NOT NULL, symbol TEXT NOT NULL, name TEXT,
    prev_close REAL, open REAL, close REAL, avg_price REAL, change_pct REAL,
    volume INTEGER, value INTEGER, ref_price REAL, change_origin_pct REAL,
    parity TEXT, start_date TEXT, end_date TEXT, status_flag TEXT, page INTEGER,
    PRIMARY KEY (date, symbol)
);

CREATE TABLE IF NOT EXISTS bond_quotes (
    date TEXT NOT NULL, symbol TEXT NOT NULL, name TEXT, section TEXT,
    issuer TEXT, coupon_rate REAL, issue_year INTEGER, maturity_year INTEGER,
    nominal REAL, prev_price REAL, open REAL, price REAL, avg_price REAL, change_pct REAL,
    ref_price REAL, limit_low REAL, limit_high REAL, volume INTEGER, value INTEGER,
    accrued_coupon REAL, periodicity TEXT, coupon_amount REAL,
    next_coupon_date TEXT, next_coupon_raw TEXT, amort_type TEXT,
    status_flag TEXT, page INTEGER,
    PRIMARY KEY (date, symbol)
);

CREATE TABLE IF NOT EXISTS order_book (
    date TEXT NOT NULL, market TEXT NOT NULL, symbol TEXT NOT NULL, name TEXT,
    bid_qty INTEGER, bid_price REAL, ask_price REAL, ask_qty INTEGER, ref_price REAL, page INTEGER,
    PRIMARY KEY (date, market, symbol)
);

CREATE TABLE IF NOT EXISTS table_totals (
    date TEXT NOT NULL, "table" TEXT NOT NULL, level TEXT NOT NULL, label TEXT NOT NULL,
    volume INTEGER, value INTEGER,
    PRIMARY KEY (date, "table", level, label)
);

CREATE TABLE IF NOT EXISTS index_values (
    date TEXT NOT NULL, index_name TEXT NOT NULL,
    family TEXT NOT NULL,            -- headline | compartment | sector | sector_new
    value REAL, change_pct REAL, ytd_pct REAL,
    nb_companies INTEGER, volume INTEGER, value_traded INTEGER, avg_per REAL, base TEXT,
    PRIMARY KEY (date, family, index_name)
);

CREATE TABLE IF NOT EXISTS market_stats (
    date TEXT NOT NULL, key TEXT NOT NULL, value REAL, unit TEXT, raw TEXT,
    PRIMARY KEY (date, key)
);

CREATE TABLE IF NOT EXISTS fund_navs (
    date TEXT NOT NULL, fund_name TEXT NOT NULL, manager TEXT, depositary TEXT, category TEXT,
    origin_value REAL, nav_prev REAL, nav_prev_date TEXT, nav REAL, nav_date TEXT,
    inception_date TEXT, inception_raw TEXT, perf_origin_pct REAL, perf_period_pct REAL, frequency TEXT,
    PRIMARY KEY (date, fund_name)
);

CREATE TABLE IF NOT EXISTS corporate_notices (
    date TEXT NOT NULL,
    kind TEXT NOT NULL,              -- operation (operations en cours) | avis (BRVM notices) | communique
    seq INTEGER NOT NULL,            -- position in the block
    company TEXT, reference TEXT, nature TEXT, subject TEXT,
    PRIMARY KEY (date, kind, seq)
);

-- each listing of a shareholder meeting in a bulletin (the list is repeated every day)
CREATE TABLE IF NOT EXISTS meeting_mentions (
    date TEXT NOT NULL, company TEXT NOT NULL, meeting_date TEXT NOT NULL, nature TEXT NOT NULL DEFAULT '',
    time TEXT, place TEXT,
    PRIMARY KEY (date, company, meeting_date, nature)
);
-- one row per meeting, with the first and last bulletin that listed it
CREATE VIEW IF NOT EXISTS general_meetings AS
    SELECT company, meeting_date, nature, MAX(time) AS time, MAX(place) AS place,
           MIN(date) AS first_seen, MAX(date) AS last_seen, COUNT(*) AS n_bulletins
    FROM meeting_mentions GROUP BY company, meeting_date, nature;

CREATE TABLE IF NOT EXISTS extraction_log (
    date TEXT NOT NULL, section TEXT, level TEXT, message TEXT
);
CREATE INDEX IF NOT EXISTS ix_log_date ON extraction_log(date);
CREATE INDEX IF NOT EXISTS ix_eq_symbol ON equity_quotes(symbol, date);
CREATE INDEX IF NOT EXISTS ix_bond_symbol ON bond_quotes(symbol, date);
CREATE INDEX IF NOT EXISTS ix_fund ON fund_navs(fund_name, date);
"""

# tables whose rows belong to one bulletin date (deleted before re-inserting a date)
DATED_TABLES = ["equity_quotes", "right_quotes", "bond_quotes", "order_book", "table_totals",
                "index_values", "market_stats", "fund_navs", "corporate_notices", "meeting_mentions",
                "extraction_log"]


def connect(path: str | Path = "brvm.db") -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    # schema v1 had general_meetings as a table; it is now a view over meeting_mentions
    if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'general_meetings' AND type = 'table'").fetchone():
        con.execute("DROP TABLE general_meetings")
    con.executescript(SCHEMA)
    con.execute("INSERT OR REPLACE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
    return con


def _insert(con: sqlite3.Connection, table: str, rows: list[dict], replace: bool = True) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    q = f'INSERT OR {"REPLACE" if replace else "IGNORE"} INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) ' \
        f'VALUES ({", ".join("?" for _ in cols)})'
    con.executemany(q, [tuple(r.get(c) for c in cols) for r in rows])


def save_document(con: sqlite3.Connection, date: str, data: dict) -> None:
    """Replace everything stored for one bulletin date with `data` (one transaction)."""
    with con:
        for t in DATED_TABLES:
            con.execute(f'DELETE FROM "{t}" WHERE date = ?', (date,))
        for table in DATED_TABLES:
            _insert(con, table, data.get(table, []))
        _insert(con, "documents", [data["document"]])


MANIFEST_STATUS = {"present": "published", "downloaded": "published", "not_found": "none", "failed": "unavailable"}


def refresh_bulletins(con: sqlite3.Connection, manifest: str | Path = "boc/manifest.csv") -> int:
    """Rebuild `bulletins` from the download manifest. Returns the number of published bulletins.
    A missing manifest (e.g. a database moved without its PDFs) leaves the table as it is."""
    import csv

    manifest = Path(manifest)
    if not manifest.exists():
        return 0
    with open(manifest, newline="", encoding="utf-8") as f:
        rows = [(r["date"], MANIFEST_STATUS.get(r["status"], r["status"]), r.get("url") or None)
                for r in csv.DictReader(f)]
    with con:
        con.execute("DELETE FROM bulletins")
        con.executemany("INSERT INTO bulletins VALUES (?, ?, ?)", rows)
    return sum(r[1] == "published" for r in rows)


def refresh_shares(con: sqlite3.Connection, path: str | Path = "boc/shares_outstanding.csv") -> int:
    """Rebuild `shares_outstanding` from the snapshots of fetch_shares.py. Returns the number of snapshots.
    A missing file leaves the table as it is."""
    import csv

    path = Path(path)
    if not path.exists():
        return 0
    with open(path, newline="", encoding="utf-8") as f:
        rows = [(r["date"], r["symbol"], r["name"], float(r["shares"]), float(r["price"]),
                 float(r["float_cap"] or 0), float(r["global_cap"])) for r in csv.DictReader(f)]
    with con:
        con.execute("DELETE FROM shares_outstanding")
        con.executemany("INSERT INTO shares_outstanding VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return len({r[0] for r in rows})


def refresh_securities(con: sqlite3.Connection) -> None:
    """Rebuild the securities master table from the quote tables (latest name/sector wins)."""
    with con:
        con.execute("DELETE FROM securities")
        con.execute("""
            INSERT INTO securities (symbol, asset_type, name, sector, compartment, first_date, last_date)
            SELECT q.symbol, 'equity', q.name, COALESCE(q.sector_code, q.sector), q.compartment, f.first, f.last
            FROM equity_quotes q
            JOIN (SELECT symbol, MIN(date) first, MAX(date) last FROM equity_quotes GROUP BY symbol) f
              ON f.symbol = q.symbol AND f.last = q.date""")
        con.execute("""
            INSERT OR IGNORE INTO securities (symbol, asset_type, name, issuer, coupon_rate, issue_year,
                                              maturity_year, sector, first_date, last_date)
            SELECT q.symbol, 'bond', q.name, q.issuer, q.coupon_rate, q.issue_year, q.maturity_year, q.section,
                   f.first, f.last
            FROM bond_quotes q
            JOIN (SELECT symbol, MIN(date) first, MAX(date) last FROM bond_quotes GROUP BY symbol) f
              ON f.symbol = q.symbol AND f.last = q.date""")
        con.execute("""
            INSERT OR IGNORE INTO securities (symbol, asset_type, name, first_date, last_date)
            SELECT q.symbol, 'right', q.name, MIN(q.date), MAX(q.date) FROM right_quotes q GROUP BY q.symbol""")
        # country code from the equity name suffix (e.g. 'SONATEL SN', 'BANK OF AFRICA BF')
        con.execute("""
            UPDATE securities SET country = CASE
              WHEN name LIKE '% CI' OR name LIKE '%COTE D''IVOIRE%' OR name LIKE '%ABIDJAN%' THEN 'CI'
              WHEN name LIKE '% SN' OR name LIKE '%SENEGAL%' THEN 'SN'
              WHEN name LIKE '% BF' OR name LIKE '%BURKINA%' THEN 'BF'
              WHEN name LIKE '% BN' OR name LIKE '%BENIN%' THEN 'BJ'
              WHEN name LIKE '% ML' OR name LIKE '%MALI%' THEN 'ML'
              WHEN name LIKE '% NG' OR name LIKE '%NIGER%' THEN 'NE'
              WHEN name LIKE '% TG' OR name LIKE '%TOGO%' THEN 'TG'
              WHEN name LIKE '% GB' OR name LIKE '%BISSAU%' THEN 'GW'
            END WHERE asset_type = 'equity'""")
        # names without a country (e.g. 'CORIS BANK INTERNATIONAL', 'SUCRIVOIRE'): BRVM symbols end with the
        # country (SNTS -> SN, CBIBF -> BF, SCRC -> CI). Agrees with the name rule for every stock that has both.
        con.execute("""
            UPDATE securities SET country = CASE
              WHEN symbol LIKE '%BF' THEN 'BF'
              WHEN substr(symbol, -1) = 'C' THEN 'CI'
              WHEN substr(symbol, -1) = 'S' THEN 'SN'
              WHEN substr(symbol, -1) = 'B' THEN 'BJ'
              WHEN substr(symbol, -1) = 'M' THEN 'ML'
              WHEN substr(symbol, -1) = 'N' THEN 'NE'
              WHEN substr(symbol, -1) = 'T' THEN 'TG'
            END WHERE asset_type = 'equity' AND country IS NULL""")
