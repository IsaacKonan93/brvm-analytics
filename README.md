# BRVM BOC: downloader and database

Python code that:
1. downloads the **Bulletin Officiel de la Cote (BOC)** PDFs published every trading day by the [BRVM](https://www.brvm.org) (Bourse Régionale des Valeurs Mobilières), and finds the oldest one available;
2. **extracts the daily data of all listed assets into a SQLite database, `brvm.db`.** The data covers equities, bonds, rights, order book, indices, market statistics, mutual funds, notices and shareholder meetings. See **[EXTRACTION.md](EXTRACTION.md)**.

Example source page: <https://www.brvm.org/fr/bulletin-officiel-de-la-cote-du-30-octobre-2025>

> **Oldest BOC available on brvm.org: Monday 1 August 2016** (`boc_20160801.pdf`, found on 2026-11-18).
>
> **Local archive (`boc/`, 2026-11-18): 2,525 PDFs (2.2 GB) covering 2016-08-01 → 2026-11-17.** See [Archive status](#archive-status).
>
> **Database `brvm.db` (2026-11-18): 2,524 of 2,525 bulletins fully extracted.** It holds 115,000 equity quotes, 252,000 bond quotes, 364,000 order-book lines, 28,000 index values, 91,000 market figures, 193,000 fund NAVs and 12,000 notices. See [EXTRACTION.md](EXTRACTION.md) and [qc_report.md](qc_report.md).

## Daily update

One command downloads the new bulletins, loads them into `brvm.db`, refreshes the QC report and makes a weekly backup. It takes about 10 seconds a day and catches up automatically after missed days:

```powershell
.\daily_update.cmd            # or: .\.env\Scripts\python.exe daily_update.py [--notebook]
```

It runs automatically through the Windows scheduled task "BRVM daily update": weekdays at 20:00 and 09:00, and at logon. See **[UPDATE.md](UPDATE.md)** for logs, backup and restore, and troubleshooting.

**Split-adjusted prices:** bulletin prices are printed unadjusted. The view `equity_quotes_adjusted` gives prices adjusted for the 50 splits since 2016, with official ratios from BRVM notices where available. Use it for returns and charts (see [EXTRACTION.md](EXTRACTION.md#splits-and-adjusted-prices-corporate_actions-price_anomalies-adjustment_factors-view-equity_quotes_adjusted)). To build an application on the database, see [EXTRACTION.md → Using the database from an application](EXTRACTION.md#using-the-database-from-an-application).

## Web app (Streamlit, French/English)

A website for analysing the data, with seven pages: market overview (with a daily briefing), market structure, stock explorer, compare & screen, bonds, mutual funds, and the official bulletins (links to every BOC PDF on brvm.org). It has a French/English switch, interactive charts and CSV exports. See **[WEBAPP.md](WEBAPP.md)**.

```powershell
.\.env\Scripts\streamlit run webapp/streamlit_app.py     # then open http://localhost:8501
```

To make it public on Streamlit Community Cloud (free), follow the step-by-step guide in [WEBAPP.md → Put it online](WEBAPP.md#put-it-online-streamlit-community-cloud). Once set up, the daily update also publishes the new data to the site each evening.

**Rebuild in progress (since 2026-11-23):** the app is being revised page by page, and deployment is on hold until that is finished. The plan, the feature proposals and the review status are in **[WEBAPP_ROADMAP.md](WEBAPP_ROADMAP.md)**. Every decision on the project is logged by date in [JOURNAL.md](JOURNAL.md).

## Using the database: showcase notebook

**[brvm_database_showcase.ipynb](brvm_database_showcase.ipynb)** is a guided tour of `brvm.db`. Each section answers a typical question with one SQL query and one table or chart:
* table contents and coverage, and the latest session snapshot (indices, market figures, top movers, most traded);
* split detection and split-adjusted prices (e.g. SONATEL's 1:10 split on 2026-10-23), and a stock deep dive with its dividend history;
* stock comparison and return correlations;
* BRVM Composite and its drawdown, and sector indices;
* market capitalisation, value traded and breadth;
* PER against dividend yield;
* bonds by issuer, coupon against maturity;
* bid-ask spreads;
* mutual fund categories and 1-year rankings;
* notices and shareholder meetings;
* data-quality checks, and a CSV export.

It is saved with its outputs, so it can be read directly in VS Code or Jupyter. To refresh it after new data, open it and *Run All*, or run:

```powershell
.\.env\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace brvm_database_showcase.ipynb
```

In VS Code, select the `.env` interpreter as the notebook kernel. The packages it needs are in `requirements.txt` (pandas, matplotlib, nbconvert, ipykernel).

## Contents

| File | Purpose |
|---|---|
| [JOURNAL.md](JOURNAL.md) | **Project journal:** dated log of requests, decisions and their reasons |
| [WEBAPP_ROADMAP.md](WEBAPP_ROADMAP.md) | **Web app plan:** goal, review status of each page, proposed features, priorities, open questions |
| [WEBAPP.md](WEBAPP.md) | **Web app (v1):** pages, how it works, running locally, putting it online, changing it |
| [webapp/](webapp/) | The Streamlit app (`streamlit_app.py`, `views/` pages, `app_lib/` data, translations, charts) |
| [fetch_shares.py](fetch_shares.py) | Daily snapshot of the number of shares of every listed stock from brvm.org (for the market structure) |
| [publish_app_data.py](publish_app_data.py) | Builds the slim database for the web app and publishes it to GitHub (daily) |
| [UPDATE.md](UPDATE.md) | **Daily update:** what it does, scheduling with Windows Task Scheduler, logs, troubleshooting |
| [backup_db.py](backup_db.py) | Weekly backup of `brvm.db` to `..\BRVM_backups` (verified, zipped, last 4 kept) |
| [data/corporate_actions_manual.csv](data/corporate_actions_manual.csv) | Manual corrections of split ratios |
| [.gitignore](.gitignore) | The code is versioned with git; data, venv and logs are excluded |
| [daily_update.py](daily_update.py), [daily_update.cmd](daily_update.cmd) | Daily update: download → extract → QC report (→ notebook), with lock and logs in `logs/` |
| [brvm_database_showcase.ipynb](brvm_database_showcase.ipynb) | **Showcase notebook:** how to query and chart the database (see above) |
| `exports/` | CSV files written by the notebook (e.g. `equity_prices_adjusted.csv`, split-adjusted prices: sessions × stocks) |
| [EXTRACTION.md](EXTRACTION.md) | **Extraction pipeline and database:** how it works, layout eras, full schema, quality control, example queries |
| [extract_boc.py](extract_boc.py) | Extraction CLI: PDFs → `brvm.db` (incremental, parallel) |
| [brvm_extract/](brvm_extract/) | Extraction package (PDF reading, table reader, section parsers, SQLite, QC) |
| [survey_layouts.py](survey_layouts.py) | Layout survey of all PDFs → `survey/*.csv` |
| [tests/](tests/) | Unit and golden tests (`python -m pytest tests`) |
| `brvm.db` | The SQLite database (194 MB) |
| [qc_report.md](qc_report.md) | Extraction quality report (`python extract_boc.py --qc`) |
| [brvm_boc.py](brvm_boc.py) | Download script (command line plus importable functions) |
| [download_all.py](download_all.py) | Bulk download of every available BOC (2016-08-01 → today), in parallel, resumable, with a manifest |
| `download_all.log`, `download_all_retry*.log` | Logs of the full run (2026-11-18) and the three retry passes that followed |
| `boc/manifest.csv` | One row per weekday: `date, status, url, file, size` |
| [requirements.txt](requirements.txt) | Python dependencies (download: `requests`, `beautifulsoup4`; extraction: `pymupdf`, `pytest`; notebook: `pandas`, `matplotlib`, `nbconvert`, `ipykernel`) |
| [SITE_NOTES.md](SITE_NOTES.md) | How brvm.org lays out BOC pages and files, and the quirks the script works around |
| [README.md](README.md) | This file |
| `boc/` | Default download folder (created automatically) |
| `.env/` | Python 3.14 virtual environment |

## Installation

```powershell
cd $env:USERPROFILE\Documents\BRVM
.\.env\Scripts\Activate.ps1          # activate the venv
pip install -r requirements.txt
```

You can also skip activation and call the venv's Python directly with `.\.env\Scripts\python.exe brvm_boc.py ...`.

## Usage

### Download the BOC for one date

```powershell
python brvm_boc.py download 2025-10-30
```
```
2025-10-30: https://www.brvm.org/sites/default/files/boc_20251030_2.pdf -> boc\boc_2025-10-30.pdf (838 KB)
```

### Download a date range (inclusive, weekdays only)

```powershell
python brvm_boc.py download 2025-10-01 2025-10-31
python brvm_boc.py download 2025-10-01 2025-10-31 --out D:\data\brvm\boc
```
Files already downloaded are skipped, so you can re-run a range safely to resume it. A summary line at the end gives how many files were downloaded and how many weekdays had no BOC.

### Find the oldest BOC available

```powershell
python brvm_boc.py oldest                 # searches from 2010 (about 6 minutes)
python brvm_boc.py oldest --since 2016    # faster when you know roughly where it is
```
```
Oldest BOC available: 2016-08-01 (Monday)
  https://www.brvm.org/sites/default/files/boc_20160801.pdf
```

### Download every available BOC

```powershell
python download_all.py                                    # 2016-08-01 -> today, 4 parallel workers
python download_all.py --start 2020-01-01 --end 2020-12-31
python download_all.py --find-oldest                      # search the oldest date first instead of using 2016-08-01
python download_all.py --workers 2 --out D:\brvm\boc
python download_all.py --retry-missing                    # also re-check dates previously marked not_found
```

- **Resumable.** PDFs already in the output folder are skipped, and dates the manifest marks `not_found` are not queried again unless you pass `--retry-missing`. If the run stops, launch the same command again and it continues where it stopped.
- **Keeping the archive up to date.** Run `python download_all.py` again, for example once a day after 19:00 GMT. It only fetches new dates. "Not found" dates from the last 5 days (`RECENT_DAYS`) are always re-checked, because the BOC is published in the evening (around 18:15 GMT) and a "not found" earlier in the day may just mean "not published yet".
- **Locked manifest.** If `manifest.csv` is open in another program (e.g. Excel), saving is retried for about a minute. If the file is still locked after that, the manifest is written to `manifest.locked-copy.csv` so no progress is lost.
- **Manifest.** `boc/manifest.csv` has one row per weekday, with these statuses:
  - `downloaded`: fetched during this run.
  - `present`: was already on disk.
  - `not_found`: holiday, or the site has no BOC for that date.
  - `failed`: network or server error. Re-run the command to retry.

  The manifest is saved every 25 dates and again at the end.
- **Progress.** Each line shows `[done/total eta N min]`. A summary at the end gives the counts per status and the total size.
- **Exit code.** `0` if no date failed, `2` if some downloads failed.
- **Load on the server.** Each worker waits 0.3 s before every request. Four workers send roughly 10 requests per second at most.

The full archive is about 2,700 weekdays and about 1.5–2 GB of PDFs.

### Options

| Command | Argument / option | Default | Meaning |
|---|---|---|---|
| `download` | `start` | required | Date `YYYY-MM-DD` |
| `download` | `end` | none | Optional end date for a range (inclusive) |
| `download` | `--out DIR` | `./boc` | Output folder |
| `oldest` | `--since YEAR` | `2010` | First year to scan |

### Output and messages

- Files are saved as `boc_YYYY-MM-DD.pdf` whatever the original filename on the server was (see [SITE_NOTES.md](SITE_NOTES.md#pdf-filenames)).
- Each file is checked to start with `%PDF` before it is saved. Partial downloads are written to a `.part` file first and renamed only when complete.
- Possible messages per date:
  - `weekend, no BOC`: Saturday or Sunday, so nothing is requested from the site.
  - `no BOC found (market holiday or not published)`: a weekday with no page and no PDF, usually a public holiday (e.g. 15 August).
  - `already downloaded`: the file exists in the output folder.
- Exit code for a single-date download: `0` if the PDF was saved or already present, `1` otherwise.

## How it works

For each date, `find_pdf_url(date)` runs these steps:

1. **Daily page (preferred).** It builds the page URL from the date, e.g. `.../fr/bulletin-officiel-de-la-cote-du-30-octobre-2025`, then reads the PDF link from the page's `fichier` field. The PDF filenames are not predictable, so reading the link from the page is the reliable method.
   - Day variants tried: zero-padded (`03`) and unpadded (`3`). For the 1st of a month: `1er`, `01` and `1`.
   - **Date check.** If the linked PDF's filename carries a different date, the link is ignored. Some pages link another day's PDF; for example, the 2017-04-17 page links `boc_20170414.pdf`.
2. **Direct PDF guess.** Some BOCs have a PDF but no page under the standard URL. In that case it sends `HEAD` requests to `/sites/default/files/boc_YYYYMMDD{_2,,_0,_1,_2_0,_3}.pdf` and keeps the first one that exists.
3. **Site search (last resort).** It queries `/fr/search/node/bulletin officiel cote {d} {mois} {yyyy}` and opens any result whose slug matches the date, including slugs with a `-0` suffix. This step recovered 25 BOCs from 2021–2026 that steps 1 and 2 missed.
4. If nothing is found, the date has no BOC. **However**, if a timeout, connection error or 5xx happened along the way, the date is reported as `failed` instead of "not found", so a re-run tries it again.

`find_oldest(since_year)` runs in two passes:

1. **Coarse pass.** For each month from `since_year` onwards, it checks up to 6 weekdays spread across the month, 12 months at a time in parallel (6 threads). It stops at the first month with any BOC.
2. **Fine pass.** It checks every weekday from the start of the previous month to the end of that month and returns the earliest date found.

The search queries the live site instead of returning a hard-coded date, so it will still be correct if BRVM adds older files.

### Being polite to the server

- Each request waits 0.3 s first (`DELAY` in the script).
- Transient errors (429, 5xx) are retried 3 times with exponential backoff.
- A browser-like `User-Agent` is sent, and the timeout is 30 s.

### Using it from Python

```python
import datetime as dt
from pathlib import Path
import brvm_boc

url = brvm_boc.find_pdf_url(dt.date(2025, 10, 30))        # -> 'https://www.brvm.org/sites/default/files/boc_20251030_2.pdf'
path = brvm_boc.download_boc(dt.date(2025, 10, 30), Path("boc"))
brvm_boc.download_range(dt.date(2025, 10, 1), dt.date(2025, 10, 31), Path("boc"))
oldest, url = brvm_boc.find_oldest(since_year=2016)
```

### Main functions

| Function | Role |
|---|---|
| `page_url_candidates(date)` | Daily page URLs to try for a date |
| `pdf_url_guesses(date)` | Direct PDF URLs to try as a fallback |
| `search_page_urls(date)` | Queries the site search for the date's page (non-standard slugs) |
| `find_pdf_url(date)` | Resolves the PDF URL (page, then guesses, then search). Returns `None` if there is no BOC; raises `NetworkError` if the site could not be reached |
| `boc_exists(date)` | Existence check using `HEAD` requests only, used by the oldest search |
| `fetch_boc(date, out_dir)` | Downloads and validates one PDF without printing; returns a `FetchResult` (`status`, `url`, `path`, `size`) |
| `download_boc(date, out_dir)` | Calls `fetch_boc`, prints the result, and returns the `Path` or `None` |
| `download_range(start, end, out_dir)` | Downloads every weekday in the range |
| `find_oldest(since_year)` | Two-pass search for the earliest BOC |

## Tested cases

Run on 2026-11-18. All passed.

| Command | Case covered | Result |
|---|---|---|
| `download 2025-10-30` | Standard page | `boc_20251030_2.pdf` |
| `download 2025-12-01` | 1st of the month, `1er` slug | `boc_20251201_2.pdf` |
| `download 2017-02-01` | 1st of the month, `01` slug | `boc_20170201.pdf` |
| `download 2016-12-15` | No page, found by the direct-PDF fallback | `boc_20161215.pdf` |
| `download 2016-11-07` | Old long filename | `bulletin_officiel_de_la_cote_du_07_nov_2016.pdf` |
| `download 2025-08-15` | Holiday (Assumption) | "no BOC found" |
| `download 2025-11-01` | Saturday | "weekend, no BOC" |
| `download 2025-10-30` again | Re-run | "already downloaded" |
| `download 2026-11-12 2026-11-17` | Range | 4 PDFs, 0 missing |
| `oldest` | Oldest search | `2016-08-01`, about 6 min |
| `fetch_boc` with the site unreachable | Network error | `failed`, not `not_found` |
| `find_pdf_url(2021-06-02)` | Unpadded-day slug | `boc_20210602_02-06-2021_a_19.22.54.pdf` |
| `find_pdf_url(2021-06-03)` | Site-search fallback | `boc_20210603-_20210603_03-06-2021_a_18.05.44.pdf` |
| `download_all.py` | Full archive | 2,525 PDFs (see [Archive status](#archive-status)) |

## Archive status

Full download run on 2026-11-18 with `download_all.py`, then three `--retry-missing` passes as the code was improved: 34.8 min for the first pass, about 4 min for each retry.

| Year | PDFs | No BOC (`not_found`) | Broken link (`failed`) |
|---|---|---|---|
| 2016 (from 1 Aug) | 74 | 36 | 0 |
| 2017 | 247 | 13 | 0 |
| 2018 | 243 | 16 | 2 |
| 2019 | 247 | 14 | 0 |
| 2020 | 251 | 11 | 0 |
| 2021 | 250 | 11 | 0 |
| 2022 | 250 | 10 | 0 |
| 2023 | 247 | 13 | 0 |
| 2024 | 249 | 13 | 0 |
| 2025 | 249 | 12 | 0 |
| 2026 (to 18 Nov) | 218 | 12 | 0 |
| **Total: 2,688 weekdays** | **2,525** (2.2 GB) | **161** | **2** |

- **`not_found`.** From 2017 onwards, 10–16 a year, which matches the public holidays of the UEMOA markets (1 Jan, Easter Monday, 1 May, Ascension, Whit Monday, 15 Aug, 1 Nov, 25 Dec, Tabaski, Maouloud, Ramadan feast, etc.). In 2016 there are 36, because 23 Aug → 30 Sep 2016 is missing from the site (see [SITE_NOTES.md](SITE_NOTES.md#known-gaps)). 2026-11-18 shows as not found only because that day's BOC wasn't published yet when the run finished.
- **`failed`.** 2018-12-06 and 2018-12-07: the pages exist, but the PDFs they link (`boc_20181206.pdf`, `boc_20181207.pdf`) return 404 on BRVM's server, and no other filename exists.
- **Checks done on the archive:**
  - Every file starts with `%PDF`.
  - No two files are identical (MD5 check). A duplicate for 2021-01-08 was found and removed.
  - Every source filename carrying a date matches its row in the manifest, except 2025-05-12 → `boc_20250510_2.pdf`, which is a filename typo on BRVM's side: the PDF's creation date is 2025-05-12.
  - Files with no date in their name (`boc_fr.pdf`, `boc_fr_2.pdf`, `boc_2024052_2.pdf`, the 2016 long names) were checked against the PDFs' internal creation or modification dates.
- **Manual fix:** 2021-06-14 has no page of its own. Its PDF (`boc_20210614_14-06-2021_a_17.54.33.pdf`) was linked from the 15 June page, so it was downloaded by hand and recorded in the manifest.

## Limitations

- **Missing dates.** The site is inconsistent. A BOC with neither a page under a standard URL, nor a guessable PDF name, nor a search result is reported as "no BOC found". See [SITE_NOTES.md](SITE_NOTES.md#known-gaps).
- **Site changes.** If BRVM changes its URL scheme or page template, update `PAGE_TMPL`, `MONTHS_FR`, `PDF_SUFFIXES`, `SEARCH_TMPL` or the CSS selector in `_pdf_from_page`.
- **Wrong files with no date in their name.** The filename date check cannot catch a page that links the wrong day's PDF when the filename carries no date (e.g. `boc_fr.pdf`). Those were checked by hand once (see above).
- **The 2026-10-02 file is the English edition** (`boc_eng_20261002.pdf`), the only version the site offers for that day.
- **French pages only.** The script uses the `/fr/` pages.
