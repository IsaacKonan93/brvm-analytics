"""Data access for the web app (read-only).

Where the database comes from, in this order:
1. environment variable / Streamlit secret BRVM_DB: a path to a SQLite file;
2. ../brvm.db next to the project (local use, always up to date);
3. BRVM_DATA_URL (secret): a zip published by publish_app_data.py (GitHub release asset). It is
   downloaded to a temporary folder and re-checked every 30 minutes (swapped when newer).

All query functions are cached with st.cache_data and take `v`, the latest bulletin date, as
first argument: when a new bulletin arrives, the cache is naturally refreshed.
"""

from __future__ import annotations

import datetime as dt
import os
import sqlite3
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
REMOTE_CHECK_SECONDS = 30 * 60
_lock = threading.Lock()
_remote = {"path": None, "checked": 0.0, "stamp": None}


def _setting(name: str) -> str | None:
    v = os.environ.get(name)
    if v:
        return v
    try:
        return st.secrets.get(name)  # Streamlit Cloud secrets
    except Exception:
        return None


def _download(url: str, token: str | None) -> Path:
    """Download the published zip if it changed since the last check; return the DB path.
    If the check or download fails but a previous copy exists, keep serving the previous copy."""
    with _lock:
        if _remote["path"] and time.time() - _remote["checked"] < REMOTE_CHECK_SECONDS:
            return _remote["path"]
        try:
            return _fetch(url, token)
        except Exception:
            if _remote["path"] and _remote["path"].exists():
                _remote["checked"] = time.time()  # retry at the next check interval
                return _remote["path"]
            raise


def _fetch(url: str, token: str | None) -> Path:
    """Check the published file (ETag / Last-Modified); download and unzip it only if it changed."""
    import requests

    now = time.time()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/octet-stream"} if token else {}
    head = requests.head(url, headers=headers, allow_redirects=True, timeout=30)
    head.raise_for_status()
    stamp = head.headers.get("ETag") or head.headers.get("Last-Modified") or str(int(now))
    if _remote["path"] and stamp == _remote["stamp"] and _remote["path"].exists():
        _remote["checked"] = now
        return _remote["path"]
    folder = Path(tempfile.gettempdir()) / "brvm_app"
    folder.mkdir(exist_ok=True)
    zpath = folder / "brvm_app.db.zip"
    with requests.get(url, headers=headers, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    target = folder / f"brvm_app_{int(now)}.db"
    with zipfile.ZipFile(zpath) as z, z.open("brvm_app.db") as src, open(target, "wb") as dst:
        while chunk := src.read(1 << 20):
            dst.write(chunk)
    old = _remote["path"]
    _remote.update(path=target, checked=now, stamp=stamp)
    if old and old != target:
        try:
            old.unlink()
        except OSError:
            pass  # still open by a running query: left for the OS temp cleanup
    # no explicit cache clear: queries are keyed on as_of(), which changes with the new data
    return target


def db_path() -> Path:
    p = _setting("BRVM_DB")
    if p:
        return Path(p)
    local = ROOT / "brvm.db"
    if local.exists():
        return local
    url = _setting("BRVM_DATA_URL")
    if url:
        return _download(url, _setting("BRVM_DATA_TOKEN"))
    raise FileNotFoundError("No database: set BRVM_DB, put brvm.db in the project folder, or set BRVM_DATA_URL.")


def connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path().as_posix()}?mode=ro", uri=True, check_same_thread=False)


def query(sql: str, params=(), dates=("date",)) -> pd.DataFrame:
    with connect() as con:
        df = pd.read_sql(sql, con, params=params)
    for c in dates:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


# ---------------------------------------------------------------- reference data

@st.cache_data(ttl=60, show_spinner=False)
def as_of() -> str:
    """Latest bulletin in the database (YYYY-MM-DD). Cached 1 minute; used as cache key elsewhere."""
    with connect() as con:
        return con.execute("SELECT MAX(date) FROM documents WHERE status IN ('ok', 'partial')").fetchone()[0]


@st.cache_data(show_spinner=False)
def sessions(v: str) -> list[dt.date]:
    df = query("SELECT DISTINCT date FROM equity_quotes ORDER BY date DESC")
    return [d.date() for d in df["date"]]


@st.cache_data(show_spinner=False)
def bulletins(v: str) -> pd.DataFrame:
    """Every weekday since 2016-08-01 up to the latest bulletin: status (published | none | unavailable)
    and the address of the official PDF on brvm.org. Empty if the database has no `bulletins` table."""
    try:
        return query("SELECT date, status, url FROM bulletins WHERE date <= ? ORDER BY date DESC", (v,))
    except Exception:
        return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "status": [], "url": []})


@st.cache_data(show_spinner=False)
def boc_urls(v: str) -> dict[str, str]:
    """{'YYYY-MM-DD': brvm.org PDF address} for every published bulletin."""
    b = bulletins(v).dropna(subset=["url"])
    return dict(zip(b["date"].dt.strftime("%Y-%m-%d"), b["url"]))


def boc_url(v: str, day) -> str | None:
    """Address of the bulletin of `day` (date, Timestamp or 'YYYY-MM-DD') on brvm.org, if published."""
    if day is None or day != day:
        return None
    return boc_urls(v).get(pd.Timestamp(day).strftime("%Y-%m-%d"))


def session_on_or_before(v: str, day: dt.date) -> dt.date:
    for s in sessions(v):
        if s <= day:
            return s
    return sessions(v)[-1]


@st.cache_data(show_spinner=False)
def stocks(v: str) -> pd.DataFrame:
    """Equities with their latest name, sector, compartment, country, first/last session."""
    return query("""SELECT symbol, name, country, sector, compartment, first_date, last_date
                    FROM securities WHERE asset_type = 'equity' ORDER BY name""",
                 dates=("first_date", "last_date"))


# ---------------------------------------------------------------- market overview

@st.cache_data(show_spinner=False)
def headline(v: str, day: str) -> pd.DataFrame:
    return query("""SELECT index_name, value, change_pct, ytd_pct FROM index_values
                    WHERE family = 'headline' AND date = ? ORDER BY index_name""", (day,))


@st.cache_data(show_spinner=False)
def stats_on(v: str, day: str) -> dict:
    df = query("SELECT key, value FROM market_stats WHERE date = ?", (day,))
    return dict(zip(df["key"], df["value"]))


@st.cache_data(show_spinner=False)
def equity_value_history(v: str) -> pd.Series:
    """Value traded on equities per session, summed from the quotes (also available for 2016-2017,
    whose bulletins have no market statistics; equal to BRVM's figure when both exist)."""
    return query("SELECT date, SUM(value) AS value FROM equity_quotes GROUP BY date ORDER BY date").set_index("date")["value"]


def equity_value(v: str, day: str) -> float | None:
    s = stats_on(v, day).get("equity_value")
    if s is not None:
        return s
    h = equity_value_history(v)
    return h.get(pd.Timestamp(day))


def breadth(v: str, day: str) -> tuple[int, int, int]:
    """(rising, falling, unchanged) stocks: BRVM's statistics, or counted from the quotes when the
    bulletin has none (2016-2017)."""
    s = stats_on(v, day)
    if any(s.get(f"equity_nb_{k}") is not None for k in ("up", "down", "unchanged")):
        return tuple(int(s.get(f"equity_nb_{k}") or 0) for k in ("up", "down", "unchanged"))  # blank = 0
    ch = equities_on(v, day)["change_pct"].dropna()
    return int((ch > 0).sum()), int((ch < 0).sum()), int((ch == 0).sum())


@st.cache_data(show_spinner=False)
def stats_history(v: str, keys: tuple[str, ...]) -> pd.DataFrame:
    marks = ",".join("?" * len(keys))
    df = query(f"SELECT date, key, value FROM market_stats WHERE key IN ({marks})", keys)
    return df.pivot(index="date", columns="key", values="value").sort_index()


@st.cache_data(show_spinner=False)
def index_history(v: str, name: str, family: str = "headline") -> pd.Series:
    df = query("SELECT date, value FROM index_values WHERE family = ? AND index_name = ? ORDER BY date",
               (family, name))
    return df.set_index("date")["value"]


@st.cache_data(show_spinner=False)
def sector_indices(v: str, day: str) -> pd.DataFrame:
    return query("""SELECT index_name, value, change_pct, ytd_pct, nb_companies, avg_per FROM index_values
                    WHERE family = 'sector_new' AND date = ?""", (day,))


@st.cache_data(show_spinner=False)
def equities_on(v: str, day: str) -> pd.DataFrame:
    """Every stock quoted on a session (adjusted view) with its country."""
    return query("""SELECT q.symbol, q.name, q.sector_code, q.compartment, s.country,
                           q.close, q.ref_price, q.change_pct, q.ytd_pct, q.volume, q.value, q.per, q.net_yield,
                           q.div_amount, q.div_date, q.status_flag
                    FROM equity_quotes q LEFT JOIN securities s USING (symbol)
                    WHERE q.date = ?""", (day,), dates=("div_date",))


@st.cache_data(show_spinner=False)
def monthly_value(v: str) -> pd.Series:
    df = query("SELECT date, SUM(value) AS v FROM equity_quotes GROUP BY date")
    return df.set_index("date")["v"].resample("ME").sum()


# ---------------------------------------------------------------- stocks

@st.cache_data(show_spinner=False)
def stock_history(v: str, symbol: str) -> pd.DataFrame:
    return query("""SELECT date, adj_ref_price, adj_close, adj_volume, value, change_pct, ytd_pct, per, net_yield,
                           ref_price, adj_factor, price_anomaly
                    FROM equity_quotes_adjusted WHERE symbol = ? ORDER BY date""", (symbol,)).set_index("date")


@st.cache_data(show_spinner=False)
def dividends(v: str, symbol: str) -> pd.DataFrame:
    return query("""SELECT div_date, MAX(adj_div_amount) AS adj_div, MAX(div_amount) AS div FROM equity_quotes_adjusted
                    WHERE symbol = ? AND div_date IS NOT NULL AND div_amount > 0
                    GROUP BY div_date ORDER BY div_date""", (symbol,), dates=("div_date",))


@st.cache_data(show_spinner=False)
def splits(v: str, symbol: str) -> pd.DataFrame:
    return query("SELECT date, label, kind, source, evidence FROM corporate_actions WHERE symbol = ? ORDER BY date",
                 (symbol,))


@st.cache_data(show_spinner=False)
def order_book(v: str, symbol: str) -> pd.DataFrame:
    return query("""SELECT date, bid_qty, bid_price, ask_price, ask_qty, ref_price FROM order_book
                    WHERE symbol = ? AND market = 'equities' ORDER BY date DESC LIMIT 20""", (symbol,))


def _matching_companies(companies: list[str], symbol: str, name: str) -> list[str]:
    from brvm_extract.adjustments import _same_company
    return [c for c in companies if isinstance(c, str) and c and _same_company(c, symbol, name)]


@st.cache_data(show_spinner=False)
def notices_for(v: str, symbol: str, name: str) -> pd.DataFrame:
    comps = query("SELECT DISTINCT company FROM corporate_notices", dates=())["company"].tolist()
    match = _matching_companies(comps, symbol, name)
    if not match:
        return pd.DataFrame(columns=["date", "kind", "reference", "nature", "subject"])
    marks = ",".join("?" * len(match))
    df = query(f"""SELECT MIN(date) AS date, kind, reference, nature, subject FROM corporate_notices
                   WHERE company IN ({marks}) GROUP BY kind, reference, nature, subject
                   ORDER BY date DESC LIMIT 40""", match)
    return df


@st.cache_data(show_spinner=False)
def meetings_for(v: str, symbol: str, name: str) -> pd.DataFrame:
    comps = query("SELECT DISTINCT company FROM general_meetings", dates=())["company"].tolist()
    match = _matching_companies(comps, symbol, name)
    if not match:
        return pd.DataFrame(columns=["meeting_date", "nature", "time", "place"])
    marks = ",".join("?" * len(match))
    return query(f"""SELECT meeting_date, nature, time, place FROM general_meetings WHERE company IN ({marks})
                     ORDER BY meeting_date DESC LIMIT 20""", match, dates=("meeting_date",))


@st.cache_data(show_spinner=False)
def adjusted_matrix(v: str, symbols: tuple[str, ...], start: str | None) -> pd.DataFrame:
    marks = ",".join("?" * len(symbols))
    q = f"SELECT date, symbol, adj_ref_price FROM equity_quotes_adjusted WHERE symbol IN ({marks})"
    params = list(symbols)
    if start:
        q += " AND date >= ?"
        params.append(start)
    df = query(q, params)
    return df.pivot(index="date", columns="symbol", values="adj_ref_price").sort_index()


@st.cache_data(show_spinner=False)
def screener(v: str) -> pd.DataFrame:
    """Latest session of each listed stock + 3-month average value traded and return."""
    day = v
    snap = equities_on(v, day)
    since = (dt.date.fromisoformat(day) - dt.timedelta(days=91)).isoformat()
    liq = query("""SELECT symbol, AVG(COALESCE(value, 0)) AS avg_value_3m FROM equity_quotes
                   WHERE date > ? GROUP BY symbol""", (since,), dates=())
    return snap.merge(liq, on="symbol", how="left")


# ---------------------------------------------------------------- bonds

@st.cache_data(show_spinner=False)
def bonds_on(v: str, day: str) -> pd.DataFrame:
    return query("""SELECT symbol, name, section, issuer, coupon_rate, issue_year, maturity_year, nominal, price,
                           ref_price, volume, value, accrued_coupon, periodicity, coupon_amount, next_coupon_date,
                           amort_type
                    FROM bond_quotes WHERE date = ?""", (day,), dates=("next_coupon_date",))


@st.cache_data(show_spinner=False)
def bond_history(v: str, symbol: str) -> pd.DataFrame:
    return query("""SELECT date, ref_price, price, nominal, accrued_coupon, volume, value FROM bond_quotes
                    WHERE symbol = ? ORDER BY date""", (symbol,)).set_index("date")


@st.cache_data(show_spinner=False)
def traded_by_year(v: str) -> pd.DataFrame:
    df = query("""SELECT substr(date, 1, 4) AS year, 'equities' AS market, SUM(value) AS v FROM equity_quotes GROUP BY 1
                  UNION ALL SELECT substr(date, 1, 4), 'bonds', SUM(value) FROM bond_quotes GROUP BY 1""", dates=())
    return df.pivot(index="year", columns="market", values="v").fillna(0)


# ---------------------------------------------------------------- funds

@st.cache_data(show_spinner=False)
def fund_navs(v: str) -> pd.DataFrame:
    """One row per fund and NAV date (latest category / manager)."""
    df = query("""SELECT fund_name, manager, category, nav_date, nav FROM fund_navs
                  WHERE nav IS NOT NULL AND nav_date IS NOT NULL""", dates=("nav_date",))
    df = df.drop_duplicates(["fund_name", "nav_date"], keep="last").sort_values("nav_date")
    return df


def drop_spikes(s: pd.Series, window: int = 11, tol: float = 0.25) -> pd.Series:
    """Remove isolated misprints (more than tol away from the centred rolling median)."""
    med = s.rolling(window, center=True, min_periods=3).median()
    return s[(s / med - 1).abs() <= tol]


@st.cache_data(show_spinner=False)
def fund_ranking(v: str) -> pd.DataFrame:
    nav = fund_navs(v)
    last = nav.groupby("fund_name").tail(1).copy()
    last = last[last["nav_date"] >= pd.Timestamp(v) - pd.Timedelta(days=60)]
    out = last.rename(columns={"nav": "nav_last", "nav_date": "nav_date_last"})
    for years, col in ((1, "perf_1y"), (3, "perf_3y")):
        tgt = out[["fund_name", "nav_date_last"]].assign(target=out["nav_date_last"] - pd.Timedelta(days=365 * years))
        past = pd.merge_asof(tgt.sort_values("target"),
                             nav.rename(columns={"nav_date": "target", "nav": "nav_past"})[["fund_name", "target", "nav_past"]],
                             on="target", by="fund_name", tolerance=pd.Timedelta(days=15))
        out = out.merge(past[["fund_name", "nav_past"]], on="fund_name", how="left")
        out[col] = (out["nav_last"] / out["nav_past"] - 1) * 100
        out = out.drop(columns="nav_past")
    return out.reset_index(drop=True)
