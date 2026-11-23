"""Quality report of the extraction (python extract_boc.py --qc -> qc_report.md)."""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
from collections import Counter
from pathlib import Path


def _rows(con: sqlite3.Connection, q: str, *a) -> list[tuple]:
    return con.execute(q, a).fetchall()


def write_report(con: sqlite3.Connection, path: Path) -> Path:
    L: list[str] = []
    add = L.append
    add(f"# Extraction quality report\n\nGenerated {dt.datetime.now():%Y-%m-%d %H:%M} from `brvm.db`.\n")

    add("## Documents\n")
    add("| Layout | ok | partial | error |\n|---|---|---|---|")
    stat: dict[str, Counter] = {}
    for layout, status, n in _rows(con, "SELECT layout, status, COUNT(*) FROM documents GROUP BY 1, 2"):
        stat.setdefault(layout, Counter())[status] = n
    for layout in sorted(stat):
        c = stat[layout]
        add(f"| {layout} | {c['ok']} | {c['partial']} | {c['error']} |")
    first, last, n = _rows(con, "SELECT MIN(date), MAX(date), COUNT(*) FROM documents")[0]
    add(f"\n{n} bulletins from {first} to {last}.\n")

    add("## Rows per table and year\n")
    tables = ["equity_quotes", "bond_quotes", "right_quotes", "order_book", "index_values",
              "market_stats", "fund_navs", "corporate_notices"]
    years = [r[0] for r in _rows(con, "SELECT DISTINCT substr(date,1,4) FROM documents ORDER BY 1")]
    add("| Table | " + " | ".join(years) + " |\n|---|" + "---|" * len(years))
    for t in tables:
        counts = dict(_rows(con, f"SELECT substr(date,1,4), COUNT(*) FROM {t} GROUP BY 1"))
        add(f"| {t} | " + " | ".join(str(counts.get(y, 0)) for y in years) + " |")
    add(f"\n`general_meetings`: {_rows(con, 'SELECT COUNT(*) FROM general_meetings')[0][0]} distinct meetings; "
        f"`securities`: {_rows(con, 'SELECT COUNT(*) FROM securities')[0][0]} securities.\n")

    add("## Checksums (sum of rows vs TOTAL printed in the BOC)\n")
    for table, qt in (("equities", "equity_quotes"), ("bonds", "bond_quotes")):
        rows = _rows(con, f"""
            SELECT t.date, t.volume, t.value, s.v, s.val FROM table_totals t
            JOIN (SELECT date, SUM(volume) v, SUM(value) val FROM {qt} GROUP BY date) s ON s.date = t.date
            WHERE t."table" = ? AND t.level = 'grand'""", table)
        ok_vol = sum(1 for r in rows if r[1] is None or r[1] == (r[3] or 0))
        ok_val = sum(1 for r in rows if r[2] is None or abs((r[4] or 0) - r[2]) <= 2)
        add(f"* **{table}**: {len(rows)} bulletins with a printed grand total; volume matches in {ok_vol}, "
            f"value matches (±2 FCFA) in {ok_val}.")
    est = _rows(con, "SELECT COUNT(*) FROM bond_quotes WHERE status_flag LIKE '%VALUE-%'")[0][0] + \
        _rows(con, "SELECT COUNT(*) FROM equity_quotes WHERE status_flag LIKE '%VALUE-%'")[0][0]
    add(f"* {est} traded values were clipped in the PDF and estimated (VALUE-EST) or reconstructed (VALUE-REC).\n")

    add("## Warnings by pattern\n")
    c: Counter = Counter()
    ex: dict[str, str] = {}
    for d, s, m in _rows(con, "SELECT date, section, message FROM extraction_log WHERE level IN ('warning','error')"):
        k = f"{s}: " + re.sub(r"\d[\d ,.]*", "N", m)[:110]
        c[k] += 1
        ex.setdefault(k, d)
    add("| Count | Pattern | First date |\n|---|---|---|")
    for k, n in c.most_common(40):
        add(f"| {n} | {k.replace('|', '/')} | {ex[k]} |")

    add("\n## Documents not fully extracted\n")
    bad = _rows(con, "SELECT date, status, error FROM documents WHERE status != 'ok' ORDER BY date")
    if not bad:
        add("None.")
    for d, s, e in bad:
        msgs = [m for (m,) in _rows(con, "SELECT message FROM extraction_log WHERE date = ? AND level IN ('warning','error')", d)]
        add(f"* **{d}** ({s}){' ' + e if e else ''}: " + "; ".join(msgs[:4]))

    add("\n## Coverage gaps\n")
    no_eq = _rows(con, "SELECT date FROM documents d WHERE NOT EXISTS (SELECT 1 FROM equity_quotes q WHERE q.date = d.date)")
    no_fund = _rows(con, "SELECT COUNT(*) FROM documents d WHERE NOT EXISTS (SELECT 1 FROM fund_navs f WHERE f.date = d.date)")[0][0]
    no_idx = _rows(con, "SELECT COUNT(*) FROM documents d WHERE NOT EXISTS (SELECT 1 FROM index_values i WHERE i.date = d.date AND i.family = 'headline')")[0][0]
    add(f"* Bulletins without equity quotes: {len(no_eq)} {[r[0] for r in no_eq][:10]}")
    add(f"* Bulletins without fund NAVs: {no_fund} (the fund page starts in October 2016)")
    add(f"* Bulletins without headline index: {no_idx}")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path
