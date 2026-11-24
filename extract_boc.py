"""Extract the BOC PDFs in boc/ into the SQLite database brvm.db.

Usage:
    python extract_boc.py                         # new or changed PDFs only (incremental)
    python extract_boc.py --from 2025-01-01 --to 2025-12-31
    python extract_boc.py --reprocess             # re-extract everything (after a parser change)
    python extract_boc.py --date 2025-10-30       # one bulletin
    python extract_boc.py --qc                    # write the quality report qc_report.md

A PDF is (re)processed when it is not in the `documents` table yet, when its size or
modification time changed, or when it was extracted by an older parser version.
See EXTRACTION.md for the schema and the checks.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from brvm_extract import PARSER_VERSION, db
from brvm_extract.pipeline import extract_file


def _quiet_mupdf() -> None:
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)


def _work(path: str) -> dict:
    return extract_file(path)


def select_files(con, boc_dir: Path, args) -> list[Path]:
    files = sorted(boc_dir.glob("boc_*.pdf"))
    if args.date:
        files = [f for f in files if f.stem == f"boc_{args.date}"]
    if args.date_from:
        files = [f for f in files if f.stem[4:] >= args.date_from]
    if args.date_to:
        files = [f for f in files if f.stem[4:] <= args.date_to]
    if args.reprocess or args.date:
        return files
    known = {r[0]: r[1:] for r in con.execute(
        "SELECT date, file_size, file_mtime, parser_version FROM documents")}
    out = []
    for f in files:
        k = known.get(f.stem[4:])
        st = f.stat()
        if not k or k[0] != st.st_size or abs((k[1] or 0) - st.st_mtime) > 1 or k[2] != PARSER_VERSION:
            out.append(f)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract BRVM BOC PDFs into SQLite")
    ap.add_argument("--boc", type=Path, default=Path("boc"), help="folder with the PDFs (default: boc)")
    ap.add_argument("--db", type=Path, default=Path("brvm.db"), help="SQLite file (default: brvm.db)")
    ap.add_argument("--from", dest="date_from", help="first date YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", help="last date YYYY-MM-DD")
    ap.add_argument("--date", help="a single date YYYY-MM-DD")
    ap.add_argument("--reprocess", action="store_true", help="re-extract even if already up to date")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--qc", action="store_true", help="only write the QC report (qc_report.md)")
    args = ap.parse_args(argv)

    con = db.connect(args.db)
    if args.qc:
        from brvm_extract.qc import write_report
        print(f"QC report written to {write_report(con, Path('qc_report.md'))}")
        return 0

    files = select_files(con, args.boc, args)
    print(f"{len(files)} PDF(s) to extract -> {args.db} (parser {PARSER_VERSION}, {args.workers} workers)", flush=True)
    if not files:
        _refresh_derived(con, args.boc)  # cheap; picks up edits of data/corporate_actions_manual.csv
        con.close()
        return 0
    t0 = time.time()
    status: dict[str, int] = {}
    with ProcessPoolExecutor(args.workers, initializer=_quiet_mupdf) as ex:
        futures = {ex.submit(_work, str(f)): f for f in files}
        for n, fut in enumerate(as_completed(futures), 1):
            data = fut.result()
            d = data["document"]
            try:
                db.save_document(con, d["date"], data)
            except Exception as e:  # keep going: record the failure on the document row
                d.update(status="error", error=f"save failed: {e}")
                db.save_document(con, d["date"], {"document": d, "extraction_log": [
                    {"date": d["date"], "section": "db", "level": "error", "message": str(e)}]})
            status[d["status"]] = status.get(d["status"], 0) + 1
            if d["status"] != "ok" or n % 100 == 0 or len(files) <= 20:
                eq = len(data.get("equity_quotes", []))
                bo = len(data.get("bond_quotes", []))
                print(f"[{n}/{len(files)}] {d['date']} {d['status']:<7} equities={eq} bonds={bo} "
                      f"warnings={d['n_warnings']}{' ' + d['error'] if d['error'] else ''}", flush=True)
    _refresh_derived(con, args.boc)
    print(f"Done in {time.time() - t0:.0f}s: {status}")
    con.close()
    return 0


def _refresh_derived(con, boc_dir: Path = Path("boc")) -> None:
    """Tables computed across bulletins: bulletin links, securities master, corporate actions, adjusted prices,
    dividend events."""
    from brvm_extract.adjustments import refresh_adjustments
    n = db.refresh_bulletins(con, boc_dir / "manifest.csv")
    print(f"Bulletin links refreshed: {n} published bulletins")
    db.refresh_securities(con)
    r = refresh_adjustments(con)
    print(f"Derived tables refreshed: {r['actions']} corporate actions on {r['symbols']} stocks, "
          f"{r['anomalies']} misprinted sessions flagged")
    from brvm_extract.dividends import refresh_dividends
    d = refresh_dividends(con)
    print(f"Dividend events refreshed: {d['events']} ex-dividend sessions placed")


if __name__ == "__main__":
    sys.exit(main())
