"""Dividend events: on which session each dividend went ex, for total-return calculations.

The bulletin shows, for every stock, the last net dividend paid and its payment date (`div_amount`,
`div_date`), and flags the ex-dividend session with "(d)" next to the name (`status_flag` EX-DIV).
On that session BRVM lowers the reference price by about the dividend. Total return adds the
dividend back on that session (see EXTRACTION.md, "Dividends and total return").

One event per (stock, payment date):
* amount: the net dividend as first shown for that payment date. Bulletins sometimes restate it
  after a split (e.g. BOAB 8 941 then 447.05 for the same payment): later restatements are ignored,
  and `adj_div_amount` puts the first amount on today's share basis.
* ex-dividend session, in this order:
    1. "flag": the session flagged EX-DIV in the 25 days up to the payment date;
    2. "price_drop": else, the session of that window where the fall of the reference price below the
       previous close is closest to the dividend (between 0.5 and 1.5 times it). 2016-2017 bulletins
       often filled the dividend column only after the payment, so the flag and the first appearance miss;
    3. "first_seen": else, the session where the new dividend first appears, if it is in that window;
    4. "largest_drop": else, the session of the window where the reference price falls most below the
       previous close.
  A dividend whose ex-session cannot be placed (paid before the stock's history starts, or no
  price drop) is left out.
* a payment date shown in fewer than 3 sessions, and replaced afterwards, is treated as a misprint.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

WINDOW_DAYS = 25        # ex-dividend session searched in the 25 days up to the payment date
MIN_SESSIONS = 3        # a payment date seen fewer times (and replaced) is a misprint

SCHEMA = """
CREATE TABLE IF NOT EXISTS dividend_events (
    symbol TEXT,
    ex_date TEXT,                    -- ex-dividend session: the dividend is added back to the return on this day
    div_date TEXT,                   -- payment date printed in the bulletin
    div_amount REAL,                 -- net dividend per share as first printed for this payment
    adj_div_amount REAL,             -- the same on today's share basis (split-adjusted)
    method TEXT,                     -- flag | price_drop | first_seen | largest_drop (see brvm_extract/dividends.py)
    PRIMARY KEY (symbol, div_date)
);
"""


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s[:10])


def detect(rows: list[tuple]) -> list[dict]:
    """rows of one stock ordered by date: (date, adj_ref_price, adj_prev_close, div_amount, adj_div_amount,
    div_date, status_flag). Returns its dividend events."""
    if not rows:
        return []
    first_session = _d(rows[0][0])
    # 1. one record per payment date: first appearance, number of sessions showing it
    records: dict[str, dict] = {}
    order: list[str] = []
    for date, _, _, amt, adj_amt, div_date, _ in rows:
        if not div_date or amt is None or amt <= 0:
            continue
        r = records.get(div_date)
        if r is None:
            records[div_date] = {"first_seen": date, "div_amount": amt, "adj_div_amount": adj_amt, "n": 1}
            order.append(div_date)
        else:
            r["n"] += 1
    last = order[-1] if order else None
    dates = [r[0] for r in rows]
    flagged = {r[0] for r in rows if r[6] and "EX-DIV" in r[6]}
    used: set[str] = set()
    events = []
    for div_date in sorted(records):
        rec = records[div_date]
        if rec["n"] < MIN_SESSIONS and div_date != last:
            continue  # misprinted payment date
        pay = _d(div_date)
        if pay < first_session:
            continue  # paid before the history starts
        lo = (pay - dt.timedelta(days=WINDOW_DAYS)).isoformat()
        window = [i for i, d in enumerate(dates) if lo <= d <= div_date and d not in used]
        if not window:
            continue
        ex, method = None, None
        flags = [i for i in window if dates[i] in flagged]
        if flags:
            ex, method = flags[-1], "flag"
        else:
            div = rec["adj_div_amount"]
            drops = [(abs((rows[i][2] - rows[i][1]) / div - 1), i) for i in window
                     if div and rows[i][1] and rows[i][2] and 0.5 <= (rows[i][2] - rows[i][1]) / div <= 1.5]
            if drops:
                ex, method = min(drops)[1], "price_drop"
            elif rec["first_seen"] in {dates[i] for i in window}:
                ex, method = dates.index(rec["first_seen"]), "first_seen"
            else:
                falls = [(rows[i][1] / rows[i][2], i) for i in window
                         if rows[i][1] and rows[i][2] and rows[i][1] < rows[i][2]]
                if falls:
                    ex, method = min(falls)[1], "largest_drop"
        if ex is None:
            continue
        used.add(dates[ex])
        events.append({"ex_date": dates[ex], "div_date": div_date, "div_amount": rec["div_amount"],
                       "adj_div_amount": rec["adj_div_amount"], "method": method})
    return events


def refresh_dividends(con: sqlite3.Connection) -> dict:
    """Recompute `dividend_events` from the split-adjusted quotes. Run after refresh_adjustments."""
    con.executescript(SCHEMA)
    by_symbol: dict[str, list[tuple]] = {}
    for row in con.execute("""SELECT symbol, date, adj_ref_price, adj_prev_close, div_amount, adj_div_amount,
                                     div_date, status_flag FROM equity_quotes_adjusted ORDER BY symbol, date"""):
        by_symbol.setdefault(row[0], []).append(row[1:])
    events = [{"symbol": s, **e} for s, rows in by_symbol.items() for e in detect(rows)]
    with con:
        con.execute("DELETE FROM dividend_events")
        con.executemany("""INSERT INTO dividend_events VALUES (:symbol, :ex_date, :div_date, :div_amount,
                           :adj_div_amount, :method)""", events)
    methods: dict[str, int] = {}
    for e in events:
        methods[e["method"]] = methods.get(e["method"], 0) + 1
    return {"events": len(events), **methods}
