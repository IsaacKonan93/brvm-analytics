"""Download the number of shares of every listed stock from brvm.org, once a day.

The bulletins (BOC) only give the total market capitalisation. brvm.org's "Capitalisations" page
gives, for every listed stock: number of shares, price, free-float and total capitalisation. The web
app multiplies the number of shares by the split-adjusted price to get each stock's capitalisation
(market structure page, see WEBAPP.md).

Usage:
    python fetch_shares.py            # today's snapshot, skipped if already taken today
    python fetch_shares.py --force    # take it again

Output: boc/shares_outstanding.csv, one row per (date, symbol), date = day of the download; loaded into
the table `shares_outstanding` by extract_boc.py. Exit code: 0 ok or skipped, 1 failure (retried at the
next run of the daily update).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

import brvm_boc

URL = "https://www.brvm.org/fr/capitalisations/0"
OUT = Path(__file__).resolve().parent / "boc" / "shares_outstanding.csv"
FIELDS = ["date", "symbol", "name", "shares", "price", "float_cap", "global_cap"]
MIN_STOCKS = 40  # a page with fewer rows is incomplete (the market lists 48 stocks in 2026)


def _num(text: str) -> float | None:
    """'18 511 176 505 734 FCFA' -> 18511176505734.0; '0,15' -> 0.15."""
    s = re.sub(r"[^\d,.-]", "", text).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse(html: str) -> list[dict]:
    """Rows of the table whose header has 'Nombre de titres' and 'Capitalisation globale'."""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.select("table"):
        head = [c.get_text(" ", strip=True) for c in table.select("tr th")]
        if not any("Nombre de titres" in h for h in head) or not any("Capitalisation globale" in h for h in head):
            continue
        rows = []
        for tr in table.select("tr")[1:]:
            c = [td.get_text(" ", strip=True) for td in tr.select("td")]
            if len(c) < 6 or not c[0]:
                continue
            rows.append({"symbol": c[0].strip(), "name": re.sub(r"\s+", " ", c[1]).strip(), "shares": _num(c[2]),
                         "price": _num(c[3]), "float_cap": _num(c[4]), "global_cap": _num(c[5])})
        return rows
    return []


def check(rows: list[dict]) -> None:
    if len(rows) < MIN_STOCKS:
        raise ValueError(f"only {len(rows)} stocks on the page (expected at least {MIN_STOCKS})")
    for r in rows:
        if not r["shares"] or not r["price"] or not r["global_cap"]:
            raise ValueError(f"incomplete row: {r}")
        if abs(r["shares"] * r["price"] / r["global_cap"] - 1) > 0.001:
            raise ValueError(f"shares x price differs from the capitalisation for {r['symbol']}")


def load(path: Path = OUT) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(rows: list[dict], day: str, path: Path = OUT) -> None:
    """Replace the snapshot of `day` in the CSV, keep the others."""
    kept = [r for r in load(path) if r["date"] != day]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(kept + [{"date": day, **r} for r in rows], key=lambda r: (r["date"], r["symbol"])):
            w.writerow({k: r.get(k) for k in FIELDS})
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Download the number of shares of every listed stock from brvm.org")
    ap.add_argument("--force", action="store_true", help="download again even if today's snapshot exists")
    args = ap.parse_args(argv)
    day = dt.date.today().isoformat()
    if not args.force and any(r["date"] == day for r in load()):
        print(f"share counts: today's snapshot ({day}) already taken")
        return 0
    try:
        r = brvm_boc.session().get(URL, timeout=60)
        r.raise_for_status()
        rows = parse(r.text)
        check(rows)
    except Exception as e:  # site unreachable or page changed: retried at the next run
        print(f"share counts: download failed ({e})")
        return 1
    save(rows, day)
    total = sum(r["global_cap"] for r in rows)
    print(f"share counts: {len(rows)} stocks saved for {day} -> {OUT} (capitalisation {total / 1e9:,.0f} bn FCFA)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
