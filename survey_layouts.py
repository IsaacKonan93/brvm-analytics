"""Survey the layout of every BOC PDF (step 0 of the extraction pipeline).

For each PDF it records: page count, number locale, the section headings found (upper-case
title lines) with their page, and the signature of every table header (line(s) containing
'Symbole'). Output:
    survey/layout_survey.csv   one row per PDF
    survey/headings.csv        every distinct heading with first/last date and count
    survey/table_headers.csv   every distinct table-header signature with first/last date and count

Usage:  python survey_layouts.py [--boc boc] [--workers 6]
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from brvm_extract.pdfdoc import load, norm

_HEADING = re.compile(r"^[A-Z0-9][A-Z0-9 '\-\.()&/:]{5,}$")


def is_heading(text: str) -> bool:
    t = norm(text)
    letters = sum(c.isalpha() for c in t)
    digits = sum(c.isdigit() for c in t)
    return bool(_HEADING.match(t)) and letters >= 6 and digits <= 2 and len(t.split()) <= 8


def survey_one(path: Path) -> dict:
    date = path.stem.replace("boc_", "")
    try:
        doc = load(path)
    except Exception as e:  # corrupt file
        return {"date": date, "error": str(e)}
    headings, headers = [], []
    for page in doc.pages:
        lines = page.lines
        for i, ln in enumerate(lines):
            t = norm(ln.text)
            if is_heading(ln.text):
                headings.append(f"p{page.number}:{t}")
            if re.search(r"\bSYMBOLE\b", t):
                # header signature: this line + the 4 lines around it, words only (no numbers)
                block = lines[max(0, i - 3): i + 5]
                words = [w for b in block for w in norm(b.text).split() if not re.search(r"\d", w)]
                headers.append(f"p{page.number}:" + " ".join(words))
    return {
        "date": date, "pages": len(doc.pages), "locale": doc.locale,
        "headings": " | ".join(headings), "table_headers": " || ".join(headers), "error": "",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boc", type=Path, default=Path("boc"))
    ap.add_argument("--out", type=Path, default=Path("survey"))
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    files = sorted(args.boc.glob("boc_*.pdf"))
    args.out.mkdir(exist_ok=True)

    with ProcessPoolExecutor(args.workers) as ex:
        rows = list(ex.map(survey_one, files, chunksize=20))

    with open(args.out / "layout_survey.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "pages", "locale", "headings", "table_headers", "error"])
        w.writeheader()
        w.writerows(rows)

    def tally(key: str, sep: str, fname: str) -> None:
        stats: dict[str, list] = defaultdict(lambda: [None, None, 0])
        for r in rows:
            for item in filter(None, (r.get(key) or "").split(sep)):
                text = item.split(":", 1)[1].strip()
                s = stats[text]
                s[0] = s[0] or r["date"]
                s[1] = r["date"]
                s[2] += 1
        with open(args.out / fname, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["text", "first_date", "last_date", "count"])
            for text, (a, b, n) in sorted(stats.items(), key=lambda kv: kv[1][0]):
                w.writerow([text, a, b, n])
        print(f"{fname}: {len(stats)} distinct")

    tally("headings", " | ", "headings.csv")
    tally("table_headers", " || ", "table_headers.csv")
    errs = [r for r in rows if r.get("error")]
    locs = defaultdict(int)
    for r in rows:
        locs[r.get("locale")] += 1
    print(f"{len(rows)} PDFs surveyed, {len(errs)} errors, locales: {dict(locs)}")
    for r in errs:
        print("  error", r["date"], r["error"])


if __name__ == "__main__":
    main()
