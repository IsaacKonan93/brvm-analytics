"""Corporate actions (splits / reverse splits) and split-adjusted equity prices.

BOC prices are printed as traded, never adjusted. This module, run after each extraction
(`refresh_adjustments`), derives from `equity_quotes`:

* `corporate_actions`  one row per detected split / reverse split (or manual entry);
* `price_anomalies`    sessions whose printed price is a misprint (a jump that comes back);
* `adjustment_factors` per symbol, the factor to apply to each date range;
* view `equity_quotes_adjusted`: equity_quotes with split-adjusted prices, volumes and dividends.

Detection: BRVM limits daily moves to +-7.5 %, so a reference price that jumps beyond
[0.6, 1.6] x the previous session's can only be a corporate action or a misprint.
* Two opposite jumps within 10 sessions whose product is ~1 are a misprint: both are dropped
  and the sessions in between are recorded in `price_anomalies`.
* The remaining jumps are splits. The observed ratio includes the day's price move, so it is
  snapped to the nearest standard split ratio (1:2, 1:4, 1:5, 1:10, 1:20, 1:25, 1:40, 1:50, 1:100...)
  when within 8 %, else to the nearest whole number when within 3 %; otherwise kept as observed.
* data/corporate_actions_manual.csv overrides the detection (see EXTRACTION.md).
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import sqlite3
import unicodedata
from pathlib import Path

MANUAL_CSV = Path(__file__).resolve().parent.parent / "data" / "corporate_actions_manual.csv"
LOW, HIGH = 0.6, 1.6
MISPRINT_SESSIONS = 10
STANDARD = [2, 3, 4, 5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 75, 80, 100, 150, 200, 250, 500, 1000]

SCHEMA = """
CREATE TABLE IF NOT EXISTS corporate_actions (
    symbol TEXT NOT NULL, date TEXT NOT NULL,       -- first session at the new price
    kind TEXT NOT NULL,                             -- split | reverse_split
    ratio REAL NOT NULL,                            -- new price / old price (0.1 for a 1:10 split)
    label TEXT,                                     -- '1:10' (split) or '2:1' (reverse split)
    prev_ref REAL, ref_price REAL, observed_ratio REAL,
    source TEXT NOT NULL,                           -- notice | detected | manual
    evidence TEXT,                                  -- the BRVM notice stating the ratio, or the manual note
    PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS price_anomalies (
    symbol TEXT NOT NULL, date TEXT NOT NULL, ref_price REAL, reason TEXT,
    PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS adjustment_factors (
    symbol TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,  -- [start, end)
    factor REAL NOT NULL,                           -- multiply prices of that period by this
    PRIMARY KEY (symbol, start_date)
);
DROP VIEW IF EXISTS equity_quotes_adjusted;
CREATE VIEW equity_quotes_adjusted AS
SELECT q.date, q.symbol, q.name, q.sector_code, q.sector, q.compartment,
       COALESCE(f.factor, 1.0) AS adj_factor,
       (a.date IS NOT NULL) AS price_anomaly,
       CASE WHEN a.date IS NULL THEN q.prev_close * COALESCE(f.factor, 1.0) END AS adj_prev_close,
       CASE WHEN a.date IS NULL THEN q.open      * COALESCE(f.factor, 1.0) END AS adj_open,
       CASE WHEN a.date IS NULL THEN q.close     * COALESCE(f.factor, 1.0) END AS adj_close,
       CASE WHEN a.date IS NULL THEN q.ref_price * COALESCE(f.factor, 1.0) END AS adj_ref_price,
       CASE WHEN a.date IS NULL THEN q.avg_price * COALESCE(f.factor, 1.0) END AS adj_avg_price,
       CAST(ROUND(q.volume / COALESCE(f.factor, 1.0)) AS INTEGER) AS adj_volume,
       q.value,
       q.div_amount * COALESCE(fd.factor, 1.0) AS adj_div_amount, q.div_date,
       q.change_pct, q.ytd_pct, q.net_yield, q.per, q.status_flag,
       q.prev_close, q.open, q.close, q.ref_price, q.volume, q.div_amount
FROM equity_quotes q
LEFT JOIN adjustment_factors f  ON f.symbol = q.symbol AND q.date >= f.start_date AND q.date < f.end_date
LEFT JOIN adjustment_factors fd ON fd.symbol = q.symbol AND q.div_date >= fd.start_date AND q.div_date < fd.end_date
LEFT JOIN price_anomalies a ON a.symbol = q.symbol AND a.date = q.date;
"""


def snap_ratio(observed: float) -> float:
    """Observed new/old price ratio -> split ratio (e.g. 0.0474 -> 1/20)."""
    n = 1 / observed if observed < 1 else observed
    best = min(STANDARD, key=lambda s: abs(n / s - 1))
    if abs(n / best - 1) <= 0.08:
        n = best
    elif abs(n / round(n) - 1) <= 0.03:
        n = round(n)
    else:
        return observed
    return 1 / n if observed < 1 else float(n)


def label(ratio: float) -> str:
    n = 1 / ratio if ratio < 1 else ratio
    txt = f"{n:g}" if abs(n - round(n)) < 1e-9 else f"{n:.2f}"
    return f"1:{txt}" if ratio < 1 else f"{txt}:1"


def detect(rows: list[tuple[str, float]]) -> tuple[list[dict], list[dict]]:
    """rows = [(date, ref_price)] of one symbol, sorted by date.
    Returns (actions, anomalies) - dicts without the symbol."""
    jumps = []  # (index, date, prev_ref, ref, ratio)
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1][1], rows[i][1]
        r = cur / prev
        if r < LOW or r > HIGH:
            jumps.append((i, rows[i][0], prev, cur, r))
    actions, anomalies, k = [], [], 0
    while k < len(jumps):
        j = jumps[k]
        nxt = jumps[k + 1] if k + 1 < len(jumps) else None
        if nxt and nxt[0] - j[0] <= MISPRINT_SESSIONS and 0.8 <= j[4] * nxt[4] <= 1.25:
            for i in range(j[0], nxt[0]):  # misprinted sessions, between the jump and the return
                anomalies.append({"date": rows[i][0], "ref_price": rows[i][1],
                                  "reason": f"jump x{j[4]:.3g} reverted on {nxt[1]}"})
            k += 2
            continue
        ratio = snap_ratio(j[4])
        actions.append({"date": j[1], "kind": "split" if ratio < 1 else "reverse_split", "ratio": ratio,
                        "label": label(ratio), "prev_ref": j[2], "ref_price": j[3],
                        "observed_ratio": round(j[4], 6), "source": "detected", "evidence": None})
        k += 1
    return actions, anomalies


_NOTICE_RX = re.compile(r"\((\d+)\)\s*actions?\s+nouvelles?\s+pour\s+(?:\w+\s+)?\((\d+)\)\s*actions?\s+anciennes?",
                        re.IGNORECASE)


def split_notices(con: sqlite3.Connection) -> list[dict]:
    """Splits announced in the bulletins' notices ('Fractionnement des actions a raison de dix (10)
    actions nouvelles pour une (1) action ancienne le 21/12/2017') -> [{date, company, ratio, text}]."""
    out, seen = [], set()
    for date, company, nature in con.execute(
            """SELECT MIN(date), company, nature FROM corporate_notices
               WHERE kind = 'operation' AND (nature LIKE '%nouvelle%ancienne%') GROUP BY company, nature"""):
        m = _NOTICE_RX.search(nature or "")
        if not m:
            continue
        new, old = int(m[1]), int(m[2])
        key = (company, new, old)
        if key not in seen and new and old:
            seen.add(key)
            out.append({"date": date, "company": company, "ratio": old / new, "text": nature})
    return out


_COUNTRY = {"COTE D'IVOIRE": "CI", "COTE DIVOIRE": "CI", "SENEGAL": "SN", "MALI": "ML", "BURKINA FASO": "BF",
            "BURKINA": "BF", "NIGER": "NG", "BENIN": "BN", "TOGO": "TG"}
_STOP = {"SA", "S.A.", "DE", "DU", "DES", "LA", "LE", "ET", "-", "&"}


def _tokens(name: str) -> set[str]:
    t = unicodedata.normalize("NFKD", name.upper())
    t = "".join(c for c in t if not unicodedata.combining(c)).replace("’", "'")
    t = re.sub(r"\bBOA\b", "BANK OF AFRICA", t)
    for k, v in _COUNTRY.items():
        t = re.sub(rf"\b{k}\b", v, t)
    return {w for w in re.split(r"[\s\-,.()]+", t) if w and w not in _STOP and w != "OF"}


def _same_company(notice_company: str, symbol: str, name: str) -> bool:
    """Every word of the notice's company name is in the security name (or starts its symbol):
    'BOA - MALI' ~ 'BANK OF AFRICA ML', 'SIB' ~ SIBC, 'ECOBANK CI' ~ "ECOBANK COTE D'IVOIRE"."""
    sec = _tokens(name)
    return all(w in sec or symbol.startswith(w) for w in _tokens(notice_company))


def _confirm(action: dict, notices: list[dict], symbol: str, name: str) -> None:
    """Replace the snapped ratio by the official one when a split notice of the same company,
    published up to 90 days before (or 5 days after) the jump, announces a ratio within 30 % of
    the observed one."""
    d = dt.date.fromisoformat(action["date"])
    cands: dict[float, dict] = {}
    for n in sorted(notices, key=lambda n: n["date"]):  # keep the earliest notice per ratio
        if (-90 <= (dt.date.fromisoformat(n["date"]) - d).days <= 5
                and abs(n["ratio"] / action["observed_ratio"] - 1) <= 0.3
                and _same_company(n["company"], symbol, name)):
            cands.setdefault(round(n["ratio"], 9), n)
    if len(cands) == 1:
        n = next(iter(cands.values()))
        action.update(ratio=n["ratio"], label=label(n["ratio"]), source="notice",
                      kind="split" if n["ratio"] < 1 else "reverse_split",
                      evidence=f"{n['date']} {n['company']}: {n['text']}")


def load_manual(path: Path = MANUAL_CSV) -> list[dict]:
    """Manual overrides: symbol,date,action,ratio,note  (action = set | ignore)."""
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("symbol") and not r["symbol"].startswith("#")]


def factors(actions: list[dict]) -> list[tuple[str, str, float]]:
    """[(start, end, factor)] covering all dates: before each action, prices are multiplied by the
    product of the ratios of all later actions."""
    acts = sorted(actions, key=lambda a: a["date"])
    out, start = [], "0000-01-01"
    for i, a in enumerate(acts):
        f = 1.0
        for later in acts[i:]:
            f *= later["ratio"]
        out.append((start, a["date"], f))
        start = a["date"]
    out.append((start, "9999-12-31", 1.0))
    return out


def refresh_adjustments(con: sqlite3.Connection) -> dict:
    """Recompute corporate_actions, price_anomalies, adjustment_factors from equity_quotes."""
    con.executescript(SCHEMA)
    by_symbol: dict[str, list[tuple[str, float]]] = {}
    names: dict[tuple[str, str], str] = {}
    for sym, date, ref, name in con.execute(
            "SELECT symbol, date, ref_price, name FROM equity_quotes WHERE ref_price > 0 ORDER BY symbol, date"):
        by_symbol.setdefault(sym, []).append((date, ref))
        names[(sym, date)] = name or ""
    actions: dict[tuple[str, str], dict] = {}
    anomalies: list[dict] = []
    notices = split_notices(con)
    for sym, rows in by_symbol.items():
        acts, anos = detect(rows)
        for a in acts:
            _confirm(a, notices, sym, names.get((sym, a["date"]), ""))
            actions[(sym, a["date"])] = {"symbol": sym, **a}
        anomalies += [{"symbol": sym, **a} for a in anos]
    for m in load_manual():
        key = (m["symbol"].strip(), m["date"].strip())
        if m.get("action", "set").strip() == "ignore":
            actions.pop(key, None)
        else:
            r = float(m["ratio"])
            old = actions.get(key, {})
            actions[key] = {"symbol": key[0], "date": key[1], "kind": "split" if r < 1 else "reverse_split",
                            "ratio": r, "label": label(r), "prev_ref": old.get("prev_ref"),
                            "ref_price": old.get("ref_price"), "observed_ratio": old.get("observed_ratio"),
                            "source": "manual", "evidence": (m.get("note") or "").strip() or None}
    with con:
        for t in ("corporate_actions", "price_anomalies", "adjustment_factors"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("""INSERT INTO corporate_actions VALUES (:symbol, :date, :kind, :ratio, :label,
                           :prev_ref, :ref_price, :observed_ratio, :source, :evidence)""", list(actions.values()))
        con.executemany("INSERT OR IGNORE INTO price_anomalies VALUES (:symbol, :date, :ref_price, :reason)",
                        anomalies)
        per_sym: dict[str, list[dict]] = {}
        for a in actions.values():
            per_sym.setdefault(a["symbol"], []).append(a)
        con.executemany("INSERT INTO adjustment_factors VALUES (?, ?, ?, ?)",
                        [(s, st, en, f) for s, acts in per_sym.items() for st, en, f in factors(acts)])
    return {"actions": len(actions), "anomalies": len(anomalies), "symbols": len(per_sym)}
