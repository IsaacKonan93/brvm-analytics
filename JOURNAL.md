# Project journal

This file is a dated log of the project's requests, decisions and their reasons. The newest entry is at the bottom. Each entry links to the detailed docs. Entries from 2026-11-18 to 2026-11-23 were reconstructed from the working sessions.

From 2026-11-24, everything is documented in the project, including plans, proposals and decisions, not only the code. Each working session adds its entry here.

## 2026-11-18: downloader and archive

* **Request:** download the BOC PDF of a given date from brvm.org, and find the oldest available date.
  * Done in [brvm_boc.py](brvm_boc.py).
  * The oldest BOC on brvm.org is **2016-08-01**.
  * The site's quirks (page addresses, file names, wrong links) are written up in [SITE_NOTES.md](SITE_NOTES.md).
* **Request:** document everything in .md files. This applies from now on, see [README.md](README.md).
* **Request:** download every available bulletin.
  * Done with [download_all.py](download_all.py) and its manifest `boc/manifest.csv`.
  * Two bulletins can't be downloaded: 2018-12-06 and 2018-12-07, because the links are broken on BRVM's side.

## 2026-11-18 → 2026-11-20: database

* **Request:** extract the stocks, bonds and everything else in the bulletins into a database of daily information on every BRVM-listed asset.
* **User choices:**
  * every section of the bulletin;
  * **SQLite** (`brvm.db`);
  * the processing always delivered as reusable Python code.
* **Done:** the package [brvm_extract/](brvm_extract/) and [extract_boc.py](extract_boc.py), documented in [EXTRACTION.md](EXTRACTION.md). The quality report is in [qc_report.md](qc_report.md).
  * 2,527 of 2,528 bulletins are fully extracted.
  * The one partial bulletin is due to an 8 FCFA error in BRVM's own figures.
* **Request:** a notebook to show how to use the database. Done: [brvm_database_showcase.ipynb](brvm_database_showcase.ipynb).

## 2026-11-18 → 2026-11-23: daily update

* **Request:** update the database every day.
  * Done with [daily_update.py](daily_update.py) and the Windows scheduled task "BRVM daily update", Monday to Friday at **20:00** (the user chose this time).
  * See [UPDATE.md](UPDATE.md).
* **2026-11-23:**
  * Added the 09:00 and at-logon triggers, so missed runs catch up (user said yes).
  * The task now runs without a window, because closing the console was killing the runs (`0xC000013A`).

## 2026-11-23: backup, git, split-adjusted prices

* **Request:** "do" the suggested next steps.
* **Backup:**
  * The user chose a **local folder only**: `Documents\BRVM_backups`.
  * A weekly backup is taken, and the last 4 are kept. Tool: [backup_db.py](backup_db.py).
* **Git:** the code is versioned. The data, PDFs and virtual environment are excluded.
* **Splits:**
  * Detected from the reference-price jumps, then confirmed with BRVM's notices.
  * Result: the table `corporate_actions` and the view `equity_quotes_adjusted`.
  * See [EXTRACTION.md → Splits](EXTRACTION.md#splits-and-adjusted-prices-corporate_actions-price_anomalies-adjustment_factors-view-equity_quotes_adjusted).

## 2026-11-23: web app v1

* **Request:** the user plans an app for data analysis on the database, as a **web page**.
* **User choices:**
  * **public** on the internet;
  * pages: market overview, stock explorer, compare & screen, bonds & funds;
  * **Streamlit**, hosted on **Streamlit Community Cloud**;
  * a **French/English** switch.
* **Done:**
  * 5 pages in [webapp/](webapp/);
  * a slim online database, built by [publish_app_data.py](publish_app_data.py);
  * tests in `tests/test_webapp.py`;
  * the guide [WEBAPP.md](WEBAPP.md).
* **Reminder given:** check BRVM's terms of use before the public launch.

## 2026-11-23: rebuild decided, deployment on hold

* **Decision:** rebuild the web app step by step **before** putting it online. Deployment is on hold until the user says the rebuild is finished.
* **Approach chosen:** revise the existing app page by page. The data, language and chart foundation is kept.
* **Market overview:** accepted as is.
* **Stock explorer:** presented for review.
* **Pause:** the user wants to think about the app as a whole before continuing.
* Status: [WEBAPP_ROADMAP.md → Status of the rebuild](WEBAPP_ROADMAP.md#status-of-the-rebuild).

## 2026-11-24: analysis proposal and documentation rule

* **Question from the user:** what analysis can the web app provide? It should give up-to-date BRVM information online, and **link to the existing BOC PDFs directly on brvm.org**.
* **Proposal written up** in [WEBAPP_ROADMAP.md](WEBAPP_ROADMAP.md):
  * a daily briefing;
  * BOC links everywhere and a Bulletins page;
  * total return, an investment simulator, liquidity, dividends, market structure, a performance table, bond schedules;
  * the priorities;
  * the option of running the daily update in GitHub Actions.
* **Checked:** the brvm.org links of 2,524 of the 2,529 bulletins are already stored in the manifest. 1,136 of them carry a suffix, so they can't be guessed from the date.
* **Rule from the user:** document everything from now on (plans, proposals, decisions) in .md files in the project. This journal and the roadmap were created for that.
* **Waiting for the user:** the answers to the roadmap's [open questions](WEBAPP_ROADMAP.md#open-questions).

## 2026-11-24: open questions answered

* **First version:** all four feature groups were chosen:
  * daily briefing + events;
  * stronger stock page;
  * performance table + screener;
  * simulator + market structure.

  The BOC links are included as requested.
* **Returns:** total return (dividends reinvested) is shown **by default**, with a switch to price only. The reason is that BRVM yields of 6–10% make price-only returns misleading.
* **Bulletins page:** a date picker plus a list of recent bulletins, filterable by month and year.
* **Daily update online:** decided at deployment, either this PC or GitHub Actions.
* **Stock explorer:** its review is moved until after it is rebuilt with the new features.
* **Not chosen for now:** the weekly and monthly recap, bond schedules. They stay as "after v1".
* The build order and the decisions are in [WEBAPP_ROADMAP.md → Decisions](WEBAPP_ROADMAP.md#decisions) and [Priorities](WEBAPP_ROADMAP.md#priorities).

## 2026-11-24: step 1 built, links to the official bulletins

* **Request:** start the rebuild with step 1, the BOC links (user said yes).
* **Database:** a new table, `bulletins`, built from `boc/manifest.csv`. It has one row per weekday, with `published` / `none` / `unavailable` and the brvm.org address. Schema version 3.
  * It is preferred to the planned `documents.url` column because it also records the days without a bulletin.
  * The 5 missing addresses were found again on brvm.org, so all 2,529 bulletins have their link.
  * `download_all.py` now fills any missing address by itself.
* **App:**
  * a new page, **Official bulletins (BOC)**: a date picker opens that session's PDF, or explains a holiday or weekend and offers the previous bulletin; below it, a list per year and month;
  * **📄 BOC** links next to the session dates: sidebar, overview, bonds, stock page, order book, splits, notices.
* **Checks:**
  * 33 tests pass. The new test covers the suffixed link of 2026-11-23, the broken links of 2018-12-06, and Christmas 2025.
  * The page renders in FR and EN on the full and the slim database.
* **Waiting for the user:** the review of step 1 in the browser.
