"""Download BRVM "Bulletin Officiel de la Cote" (BOC) PDFs and find the oldest one available.

Usage:
    python brvm_boc.py download 2025-10-30                 # one date
    python brvm_boc.py download 2025-10-01 2025-10-31      # date range (weekdays only)
    python brvm_boc.py oldest [--since 2010]               # search for the oldest BOC on the site

Options:
    --out DIR   output directory for PDFs (default: ./boc)
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://www.brvm.org"
PAGE_TMPL = BASE + "/fr/bulletin-officiel-de-la-cote-du-{day}-{month}-{year}"
FILES = BASE + "/sites/default/files/"
MONTHS_FR = [
    "janvier", "fevrier", "mars", "avril", "mai", "juin",
    "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
]
# Suffixes seen on directly-named PDFs: boc_20200110.pdf, boc_20170110_0.pdf, boc_20251030_2.pdf, boc_20261111_2_0.pdf
PDF_SUFFIXES = ["_2", "", "_0", "_1", "_2_0", "_3"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
TIMEOUT = 30
DELAY = 0.3  # seconds between requests, to be polite to the server

_local = threading.local()


def session() -> requests.Session:
    """One requests.Session per thread, with retries on transient errors."""
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        retry = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET", "HEAD"))
        s.mount("https://", HTTPAdapter(max_retries=retry))
        _local.session = s
    return s


def _request(method: str, url: str, **kw) -> requests.Response | None:
    time.sleep(DELAY)
    try:
        return session().request(method, url, timeout=TIMEOUT, allow_redirects=True, **kw)
    except requests.RequestException as e:
        print(f"  ! request failed: {url} ({e})", file=sys.stderr)
        return None


# ---------------------------------------------------------------- URL resolution

def page_url_candidates(d: dt.date) -> list[str]:
    """Page URLs to try for a date. The day is usually zero-padded ('03'), sometimes not ('2', seen in 2021);
    the 1st of a month is written '1er', '01' or '1' depending on the period."""
    days = ["1er", "01", "1"] if d.day == 1 else list(dict.fromkeys([f"{d.day:02d}", str(d.day)]))
    return [PAGE_TMPL.format(day=x, month=MONTHS_FR[d.month - 1], year=d.year) for x in days]


SEARCH_TMPL = BASE + "/fr/search/node/{query}"
_SLUG_RE = re.compile(r'href="(https://www\.brvm\.org/fr/bulletin-officiel-de-la-cote-du-(\d+)(?:er)?-([a-z]+)-(\d{4})(?:-\d+)?)"')


def search_page_urls(d: dt.date) -> list[str]:
    """Last resort: ask the site's search engine for the day's BOC page (catches non-standard slugs)."""
    query = requests.utils.quote(f"bulletin officiel cote {d.day} {MONTHS_FR[d.month - 1]} {d.year}")
    r = _request("GET", SEARCH_TMPL.format(query=query))
    if r is None:
        raise NetworkError("search unreachable")
    if r.status_code != 200:
        return []
    urls = []
    for url, day, month, year in _SLUG_RE.findall(r.text):
        if int(day) == d.day and month == MONTHS_FR[d.month - 1] and int(year) == d.year and url not in urls:
            urls.append(url)
    return urls


def pdf_url_guesses(d: dt.date) -> list[str]:
    return [f"{FILES}boc_{d:%Y%m%d}{s}.pdf" for s in PDF_SUFFIXES]


def _pdf_from_page(html: str, d: dt.date) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    link = soup.select_one('div.field-name-field-fichier-boc a[href$=".pdf"]') \
        or soup.select_one('article a[href$=".pdf"]')
    if not link:
        return None
    date_span = soup.select_one('span[property="dc:date"]')
    if date_span and date_span.get("content", "")[:10] not in ("", d.isoformat()):
        print(f"  ! page date {date_span['content'][:10]} differs from requested {d}", file=sys.stderr)
    href = link["href"]
    # Some pages link another day's PDF (e.g. the 2017-04-17 page links boc_20170414.pdf):
    # reject a link whose filename carries a different date.
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", href.rsplit("/", 1)[-1])
    if m and m.group(0) != f"{d:%Y%m%d}":
        print(f"  ! page for {d} links another day's PDF ({href.rsplit('/', 1)[-1]}), ignored", file=sys.stderr)
        return None
    return href if href.startswith("http") else BASE + href


class NetworkError(Exception):
    """The site could not be reached, so 'no BOC' cannot be concluded."""


def find_pdf_url(d: dt.date) -> str | None:
    """Return the PDF URL of the BOC for date d, or None if none is published.

    Raises NetworkError if nothing was found AND at least one request errored (timeout,
    connection error, 5xx): in that case the absence of a BOC is not proven.
    """
    errored = False
    # 1. The day's page: the authoritative link (PDF filenames are inconsistent).
    for url in page_url_candidates(d):
        r = _request("GET", url)
        if r is None or r.status_code >= 500:
            errored = True
        elif r.status_code == 200:
            pdf = _pdf_from_page(r.text, d)
            if pdf:
                return pdf
    # 2. Fallback: some PDFs exist without a page under the standard slug.
    for url in pdf_url_guesses(d):
        r = _request("HEAD", url)
        if r is None or r.status_code >= 500:
            errored = True
        elif r.status_code == 200:
            return url
    # 3. Last resort: the site search, which finds pages with non-standard slugs.
    try:
        tried = set(page_url_candidates(d))
        for url in search_page_urls(d):
            if url in tried:
                continue
            r = _request("GET", url)
            if r is None or r.status_code >= 500:
                errored = True
            elif r.status_code == 200:
                pdf = _pdf_from_page(r.text, d)
                if pdf:
                    h = _request("HEAD", pdf)
                    if h is not None and h.status_code == 200:
                        return pdf
    except NetworkError:
        errored = True
    if errored:
        raise NetworkError(f"network errors while looking up {d}")
    return None


def boc_exists(d: dt.date) -> bool:
    """Cheap existence check (HEAD only) used by the oldest-date search."""
    for url in page_url_candidates(d) + pdf_url_guesses(d):
        r = _request("HEAD", url)
        if r is not None and r.status_code == 200:
            return True
    return False


# ---------------------------------------------------------------- download

@dataclass
class FetchResult:
    date: dt.date
    status: str            # downloaded | present | weekend | not_found | failed
    url: str | None = None
    path: Path | None = None
    size: int = 0

    def message(self) -> str:
        if self.status == "downloaded":
            return f"{self.date}: {self.url} -> {self.path} ({self.size / 1024:.0f} KB)"
        if self.status == "present":
            return f"{self.date}: already downloaded -> {self.path}"
        if self.status == "weekend":
            return f"{self.date}: weekend, no BOC"
        if self.status == "not_found":
            return f"{self.date}: no BOC found (market holiday or not published)"
        return f"{self.date}: download failed ({self.url or 'site unreachable'})"


def fetch_boc(d: dt.date, out_dir: Path) -> FetchResult:
    """Download the BOC for date d into out_dir/boc_YYYY-MM-DD.pdf, without printing."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"boc_{d.isoformat()}.pdf"
    if target.exists() and target.stat().st_size > 0:
        return FetchResult(d, "present", path=target, size=target.stat().st_size)
    if d.weekday() >= 5:
        return FetchResult(d, "weekend")

    try:
        url = find_pdf_url(d)
    except NetworkError:
        return FetchResult(d, "failed")
    if not url:
        return FetchResult(d, "not_found")

    r = _request("GET", url, stream=True)
    if r is None or r.status_code != 200:
        return FetchResult(d, "failed", url=url)
    tmp = target.with_suffix(".part")
    try:
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(64 * 1024):
                f.write(chunk)
    except requests.RequestException:
        tmp.unlink(missing_ok=True)
        return FetchResult(d, "failed", url=url)
    with open(tmp, "rb") as f:
        is_pdf = f.read(4) == b"%PDF"
    if not is_pdf:
        tmp.unlink()
        return FetchResult(d, "failed", url=url)
    tmp.replace(target)
    return FetchResult(d, "downloaded", url=url, path=target, size=target.stat().st_size)


def download_boc(d: dt.date, out_dir: Path) -> Path | None:
    res = fetch_boc(d, out_dir)
    print(res.message())
    return res.path


def download_range(start: dt.date, end: dt.date, out_dir: Path) -> None:
    ok = missing = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            if download_boc(d, out_dir):
                ok += 1
            else:
                missing += 1
        d += dt.timedelta(days=1)
    print(f"\nDone: {ok} downloaded/present, {missing} weekdays without a BOC.")


# ---------------------------------------------------------------- oldest search

def _month_samples(year: int, month: int, n: int = 6) -> list[dt.date]:
    """Up to n weekdays spread across a month."""
    days = []
    for day in (2, 6, 10, 14, 18, 22, 26):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        if d.month == month and d not in days:
            days.append(d)
    return days[:n]


def _month_has_boc(ym: tuple[int, int]) -> bool:
    return any(boc_exists(d) for d in _month_samples(*ym))


def find_oldest(since_year: int = 2010, workers: int = 6) -> tuple[dt.date, str] | None:
    today = dt.date.today()
    months = [(y, m) for y in range(since_year, today.year + 1) for m in range(1, 13)
              if dt.date(y, m, 1) <= today]

    # Coarse pass: first month (chronologically) with any BOC, checked 12 months at a time in parallel.
    first_month = None
    with ThreadPoolExecutor(workers) as ex:
        for i in range(0, len(months), 12):
            chunk = months[i:i + 12]
            print(f"  scanning {chunk[0][0]}-{chunk[0][1]:02d} .. {chunk[-1][0]}-{chunk[-1][1]:02d}")
            hits = [ym for ym, has in zip(chunk, ex.map(_month_has_boc, chunk)) if has]
            if hits:
                first_month = hits[0]
                break
    if first_month is None:
        return None

    # Fine pass: every weekday from the start of the previous month up to the end of the hit month.
    y, m = first_month
    start = dt.date(y - 1, 12, 1) if m == 1 else dt.date(y, m - 1, 1)
    end = dt.date(y + 1, 1, 1) if m == 12 else dt.date(y, m + 1, 1)
    days = [start + dt.timedelta(i) for i in range((end - start).days)]
    days = [d for d in days if d.weekday() < 5]
    print(f"  first month with a BOC: {y}-{m:02d}; checking every weekday from {start}")
    with ThreadPoolExecutor(workers) as ex:
        found = [d for d, has in zip(days, ex.map(boc_exists, days)) if has]
    if not found:
        return None
    oldest = found[0]
    try:
        return oldest, find_pdf_url(oldest) or "?"
    except NetworkError:
        return oldest, "?"


# ---------------------------------------------------------------- CLI

def _date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date '{s}', expected YYYY-MM-DD")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="BRVM Bulletin Officiel de la Cote downloader")
    sub = p.add_subparsers(dest="cmd", required=True)

    dl = sub.add_parser("download", help="download the BOC for a date or a date range")
    dl.add_argument("start", type=_date, help="date YYYY-MM-DD")
    dl.add_argument("end", type=_date, nargs="?", help="optional end date YYYY-MM-DD (inclusive)")
    dl.add_argument("--out", type=Path, default=Path("boc"), help="output directory (default: ./boc)")

    old = sub.add_parser("oldest", help="search for the oldest BOC available on the site")
    old.add_argument("--since", type=int, default=2010, help="year to start searching from (default: 2010)")

    args = p.parse_args(argv)

    if args.cmd == "download":
        if args.end:
            if args.end < args.start:
                p.error("end date is before start date")
            download_range(args.start, args.end, args.out)
            return 0
        return 0 if download_boc(args.start, args.out) else 1

    if args.cmd == "oldest":
        print(f"Searching for the oldest BOC since {args.since} ...")
        res = find_oldest(args.since)
        if not res:
            print("No BOC found.")
            return 1
        d, url = res
        print(f"\nOldest BOC available: {d} ({d:%A})\n  {url}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
