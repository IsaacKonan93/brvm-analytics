"""Extraction of one BOC PDF into the record dicts stored by db.save_document."""

from __future__ import annotations

import datetime as dt
import traceback
from pathlib import Path

from . import PARSER_VERSION
from .pdfdoc import load

# Layout eras (see EXTRACTION.md). Used for reporting only: parsers detect the layout from
# the table headers themselves.
ERAS = [("A", "2016-01-01"), ("B", "2017-12-19"), ("C", "2023-01-01"), ("D", "2025-01-01")]


def layout_of(date: str) -> str:
    era = "A"
    for name, start in ERAS:
        if date >= start:
            era = name
    return era


def _sections():
    # imported lazily so a worker process only pays the import once
    from .parsers import quotes, market, funds, events
    return [
        ("equities", quotes.equities_section),
        ("rights", quotes.rights_section),
        ("bonds", quotes.bonds_section),
        ("order_book", quotes.order_book_section),
        ("market", market.parse_market),
        ("funds", funds.parse_funds),
        ("events", events.parse_events),
    ]


def reconstruct_values(data: dict, log) -> None:
    """If exactly one traded value of a table had to be estimated (clipped in the PDF), recover
    it exactly as printed grand total - sum of the other rows (flag VALUE-REC)."""
    for table, rows_key in (("equities", "equity_quotes"), ("bonds", "bond_quotes")):
        rows = data.get(rows_key, [])
        est = [r for r in rows if "VALUE-EST" in (r.get("status_flag") or "")]
        grand = [t for t in data.get("table_totals", []) if t["table"] == table and t["level"] == "grand"]
        if len(est) != 1 or not grand or not grand[0].get("value"):
            continue
        r = est[0]
        rest = sum(x.get("value") or 0 for x in rows if x is not r)
        cand = grand[0]["value"] - rest
        if cand > 0 and abs(cand - r["value"]) <= 0.3 * r["value"]:
            log(table, "info", f"{r['symbol']}: value reconstructed from the printed total: {cand} (estimate {r['value']})")
            r["value"] = cand
            r["status_flag"] = r["status_flag"].replace("VALUE-EST", "VALUE-REC")


def qc_checks(data: dict, log) -> int:
    """Checksums: sum of row volumes/values vs the TOTAL lines printed in the BOC. Returns #failures."""
    fails = 0
    for table, rows_key in (("equities", "equity_quotes"), ("bonds", "bond_quotes")):
        rows = data.get(rows_key, [])
        grand = [t for t in data.get("table_totals", []) if t["table"] == table and t["level"] == "grand"]
        if not rows or not grand:
            continue
        g = grand[0]
        for field in ("volume", "value"):
            s = sum(r.get(field) or 0 for r in rows)
            printed = g.get(field)
            if printed is None or s == printed:
                continue
            est = any("VALUE-EST" in (r.get("status_flag") or "") for r in rows)
            if abs(s - printed) <= 2:
                log("qc", "info", f"{table}: sum of {field} {s} vs printed {printed}: rounding in the BOC")
            elif str(s).startswith(str(printed)) and len(str(printed)) >= 5:
                log("qc", "info", f"{table}: printed total {printed} is clipped in the PDF (sum of rows {s})")
            elif est and field == "value" and abs(s - printed) <= 0.02 * printed:
                log("qc", "info", f"{table}: sum of value {s} vs printed {printed} (includes estimated values)")
            else:
                fails += 1
                log("qc", "warning", f"{table}: sum of {field} {s} != printed total {printed} ({g['label']})")
    # close vs prev x (1 + change)
    for r in data.get("equity_quotes", []):
        p, c, ch = r.get("prev_close"), r.get("close"), r.get("change_pct")
        if p and c and ch is not None and r.get("ref_price") == c:
            implied = (c / p - 1) * 100
            if abs(implied - ch) > 0.6:
                log("qc", "info", f"{r['symbol']}: change {ch}% but close/prev implies {implied:.2f}%")
    return fails


def extract_file(path: str | Path) -> dict:
    """Parse one BOC PDF. Never raises: errors are returned in the document record."""
    path = Path(path)
    date_s = path.stem.replace("boc_", "")
    date = dt.date.fromisoformat(date_s)
    st = path.stat()
    logs: list[dict] = []

    def log(section: str, level: str, msg: str) -> None:
        logs.append({"date": date_s, "section": section, "level": level, "message": msg[:500]})

    data: dict = {}
    doc_rec = {"date": date_s, "file": path.name, "file_size": st.st_size, "file_mtime": st.st_mtime,
               "pages": None, "locale": None, "layout": layout_of(date_s), "parser_version": PARSER_VERSION,
               "extracted_at": dt.datetime.now().isoformat(timespec="seconds"), "status": "ok",
               "n_warnings": 0, "error": None}
    try:
        doc = load(path)
        doc_rec["pages"], doc_rec["locale"] = len(doc.pages), doc.locale
    except Exception as e:
        doc_rec.update(status="error", error=f"cannot open PDF: {e}")
        return {"document": doc_rec, "extraction_log": logs}

    errors = 0
    for name, fn in _sections():
        try:
            res = fn(doc, date)
        except Exception:
            errors += 1
            log(name, "error", traceback.format_exc(limit=3))
            continue
        for key, value in res.items():
            if key == "warnings":
                for w in value:
                    log(name, "warning", w)
            else:
                data.setdefault(key, []).extend(value)

    reconstruct_values(data, log)
    fails = qc_checks(data, log)
    if not data.get("equity_quotes"):
        log("equities", "error", "no equity quotes found")
        errors += 1
    doc_rec["n_warnings"] = sum(1 for x in logs if x["level"] in ("warning", "error"))
    doc_rec["status"] = "error" if errors and not data.get("equity_quotes") else (
        "partial" if errors or fails else "ok")
    data["document"] = doc_rec
    data["extraction_log"] = logs
    return data
