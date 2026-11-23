"""Download every available BRVM BOC PDF, from the oldest (2016-08-01) up to today.

Usage:
    python download_all.py                         # 2016-08-01 -> today, 4 parallel workers
    python download_all.py --start 2020-01-01 --end 2020-12-31
    python download_all.py --find-oldest           # search the oldest date on the site first
    python download_all.py --workers 2 --out D:\\brvm\\boc

Resumable: PDFs already in the output folder are skipped, so re-running only fetches what is missing.
Writes a manifest (boc/manifest.csv) with one row per weekday: date, status, url, file, size.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import brvm_boc

OLDEST_KNOWN = dt.date(2016, 8, 1)  # established on 2026-11-18, see SITE_NOTES.md
RECENT_DAYS = 5  # "not_found" dates newer than this are always re-checked


def weekdays(start: dt.date, end: dt.date) -> list[dt.date]:
    n = (end - start).days + 1
    return [start + dt.timedelta(i) for i in range(n) if (start + dt.timedelta(i)).weekday() < 5]


def load_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["date"]: row for row in csv.DictReader(f)}


def write_manifest(path: Path, rows: dict[str, dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "status", "url", "file", "size"])
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])
    # On Windows the replace fails while another program (Excel, antivirus) holds the file: retry,
    # then fall back to a side file so progress is never lost.
    for attempt in range(10):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(1 + attempt)
    fallback = path.with_name(path.stem + ".locked-copy.csv")
    tmp.replace(fallback)
    print(f"  ! {path} is locked by another program (close it in Excel?); manifest saved to {fallback}",
          flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Download all available BRVM BOC PDFs")
    p.add_argument("--start", type=brvm_boc._date, default=None, help=f"first date (default: {OLDEST_KNOWN})")
    p.add_argument("--end", type=brvm_boc._date, default=dt.date.today(), help="last date (default: today)")
    p.add_argument("--find-oldest", action="store_true", help="search the oldest BOC on the site instead of using the known date")
    p.add_argument("--out", type=Path, default=Path("boc"), help="output folder (default: ./boc)")
    p.add_argument("--workers", type=int, default=4, help="parallel downloads (default: 4)")
    p.add_argument("--retry-missing", action="store_true", help="re-check dates the manifest marks as not_found")
    args = p.parse_args(argv)

    start = args.start
    if start is None:
        if args.find_oldest:
            print("Searching for the oldest BOC ...", flush=True)
            res = brvm_boc.find_oldest(2010)
            if not res:
                print("No BOC found on the site.")
                return 1
            start = res[0]
        else:
            start = OLDEST_KNOWN

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "manifest.csv"
    manifest = load_manifest(manifest_path)

    days = weekdays(start, args.end)
    if not args.retry_missing:
        # Dates already confirmed as having no BOC are not re-queried, except the last few days:
        # a BOC is published in the evening (~18:15 GMT), so "not found" may just mean "not yet".
        recent = dt.date.today() - dt.timedelta(days=RECENT_DAYS)
        days = [d for d in days
                if d >= recent or manifest.get(d.isoformat(), {}).get("status") != "not_found"]
    total = len(days)
    print(f"{total} weekdays to process from {start} to {args.end} -> {args.out.resolve()} "
          f"({args.workers} workers)", flush=True)

    counts: dict[str, int] = {}
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(args.workers) as ex:
        futures = {ex.submit(brvm_boc.fetch_boc, d, args.out): d for d in days}
        for fut in as_completed(futures):
            d = futures[fut]
            try:
                r = fut.result()
            except Exception as e:  # never let one date kill the whole run
                r = brvm_boc.FetchResult(d, "failed")
                print(f"{d}: error {e}", flush=True)
            done += 1
            counts[r.status] = counts.get(r.status, 0) + 1
            manifest[d.isoformat()] = {
                "date": d.isoformat(), "status": r.status, "url": r.url or manifest.get(d.isoformat(), {}).get("url", ""),
                "file": r.path.name if r.path else "", "size": r.size or "",
            }
            if r.status != "present":
                elapsed = time.time() - t0
                eta = elapsed / done * (total - done)
                print(f"[{done}/{total} eta {eta/60:.0f} min] {r.message()}", flush=True)
            if done % 25 == 0:
                write_manifest(manifest_path, manifest)

    write_manifest(manifest_path, manifest)

    pdfs = list(args.out.glob("boc_*.pdf"))
    size_mb = sum(f.stat().st_size for f in pdfs) / 1024 / 1024
    print("\n=== Summary ===")
    for k in ("downloaded", "present", "not_found", "failed"):
        print(f"  {k:<11} {counts.get(k, 0)}")
    print(f"  PDFs in {args.out}: {len(pdfs)} ({size_mb:.0f} MB), time {(time.time() - t0)/60:.1f} min")
    print(f"  manifest: {manifest_path}")
    if counts.get("failed"):
        print("  Some downloads failed: re-run the same command to retry them.")
    return 0 if not counts.get("failed") else 2


if __name__ == "__main__":
    sys.exit(main())
