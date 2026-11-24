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

## 2026-11-24: step 2 built, daily briefing

* **Request:** step 2 (user: "step 2").
* **Built:** the module `webapp/app_lib/briefing.py`, shown on the Market overview for any chosen session:
  * **the written summary**, FR/EN, from text templates;
  * **Highlights**: 52-week highs and lows, moves close to the limit, unusual trading, splits, new notices;
  * **Upcoming**: meetings, plus the dividend payments, splits and first listings parsed from the operation notices.
* **Choices made while building:**
  * **"Close to the limit" means 7 % or more**, not exactly 7.5 %: prices move in ticks, so a stock at the limit shows e.g. −7.33 %.
  * **The thresholds were measured on 2026:** 5× the 3-month value gives about one event per session.
  * **Notices repeated with a garbled company name** (font decoding) are merged with the readable one.
  * **Splits announced in notices** get their own label.
* **Fix found on the way:** the 2016–2017 bulletins have no market statistics, so the overview showed 0 / 0 / 0 stocks rising/falling and no value traded. These are now computed from the quotes, which give the same values as BRVM's own figures where both exist.
* **Checks:**
  * 35 tests pass. The new ones cover notice parsing, the summary of 2026-10-20, ONATEL's 52-week high, SONATEL's unusual volume, the upcoming dividend and split, and the 2017 fallback.
  * The overview renders on the slim database in both languages.
* **Rules documented** in [WEBAPP.md → Daily briefing rules](WEBAPP.md#daily-briefing-rules).
* **Waiting for the user:** the review of step 2 in the browser.

## 2026-11-24: navigation bar in Indigo dye

* **Request:** change the theme of the navigation bar to Indigo dye, before continuing the rebuild.
* **Done** in `.streamlit/config.toml`, section `[theme.sidebar]`:
  * background Indigo dye `#00416A` with white text (contrast about 10.7:1), the same in light and dark mode;
  * `#0A5A8C` for widgets and the selected page;
  * light-blue accents and links (`#8CC8F2`, `#A9D8FF`) so the language switch and the 📄 BOC link stay readable.
* The rest of the app keeps its theme. The charts keep the validated palette.
* **Waiting for the user:** a check of the colours in the browser, then step 3 (total return).

## 2026-11-24: step 3 built, total return

* **Request:** step 3 (user: "step 3").
* **Finding:**
  * The bulletin flags the ex-dividend session with "(d)". The new dividend appears that day, and BRVM lowers the reference price by about the dividend. SONATEL on 2025-05-19: −1 655, exactly the dividend.
  * Complications:
    * amounts restated after splits;
    * 2016–2017 bulletins filling the dividend column only after the payment;
    * misprinted payment dates.
* **Built:**
  * **The table `dividend_events`** ([brvm_extract/dividends.py](brvm_extract/dividends.py)), refreshed after each extraction. It holds 325 events: 278 from the flag, 39 from a price drop matching the dividend, 7 from the first appearance, 1 from the largest drop. Three real dividends could not be placed.
  * **`total_return_index`** in the app: the net dividend is reinvested on its ex-dividend session.
  * **A Performance switch in the sidebar:** *Dividends reinvested* (default, as decided) / *Price only*, kept in the URL (`?basis=`).
    * Stock page: YTD and 1-year return follow the switch. The chart shows the price with dividends reinvested next to the adjusted price.
    * Comparison: the rebased chart, return, volatility, drawdown and correlation follow the switch.
    * BRVM indices, daily changes and movers stay on price, as BRVM publishes them.
* **Checks:**
  * 40 tests pass. The new ones cover the formula on a synthetic case, SONATEL's 2025 ex-date and amount, a flat total return on the ex-day, the 10-year gap, both bases on the pages, and the detection rules (flag, restatement, misprint, price drop).
  * Orders of magnitude: dividends add 4 to 8 % a year on top of the price return, consistent with BRVM yields.
* **Docs:** [EXTRACTION.md → Dividends and total return](EXTRACTION.md#dividends-and-total-return-dividend_events--pk-symbol-div_date), [WEBAPP.md → Pages](WEBAPP.md#pages).
* **Waiting for the user:** the review of step 3, then step 4 (stronger stock page).

## 2026-11-24: step 4 built, stronger stock page

* **Request:** step 4 (user: "step 4").
* **Built:** below the price chart, the stock page now has four tabs:
  * **Dividends:** the dividend announced and not yet paid; trailing 12-month yield; 5-year dividend growth; years paid; dividend per year; every dividend with its ex-date (📄 BOC) and yield at the ex-date.
  * **Liquidity** (3 months / 1 year / 3 years): value and volume per session, share of sessions traded, liquidity rank among the 48 listed stocks, value per month, order book and spread over 90 sessions.
  * **Valuation:** P/E and net yield since 2016 against the sector and market medians.
  * **Events:** splits, notices, meetings, which were already on the page.
* **Choices made while building:**
  * **The sector is the stock's current sector over the whole history,** because BRVM's sector codes only exist since 2023 and changed in 2025.
  * **P/E and yields are cleaned for charts and medians:** P/E outside 0 to 100 and yields above 30 % are left out (the printed P/E reaches 1,920).
  * **The 12-month yield counts the last 365 days only,** unlike BRVM's yield, which keeps the last dividend even when it is old (STAC: 3.03 % published, 0 % here).
* **Checked against the data:**
  * SONATEL's 12-month yield equals BRVM's 4.46 %.
  * SGBC's 2019–2021 dividend cut is real: the amounts are printed and visible in the price drops.
* **Checks:**
  * 41 tests pass.
  * The page renders for five stocks: two large payers, one without a dividend since 2022, one without any dividend, one delisted. It renders on the full and the slim database, in both languages.
* **Rules documented** in [WEBAPP.md → Stock page rules](WEBAPP.md#stock-page-rules).
* **Waiting for the user:** the review of the stock page (steps 3 and 4), then step 5 (performance table and investment simulator).

## 2026-11-24: step 5 built, performance table and investment simulator

* **Request:** step 5 (user: "step 5").
* **Built:** the Compare & screen page now has four tabs:
  * **Compare:** as before.
  * **Performance:** every listed stock over 1W, 1M, YTD, 1Y, 3Y and 5Y, plus 3Y and 5Y per year; a ranking chart over the chosen horizon; filters on sector and country; CSV export.
  * **Screener:** the existing tab plus the 1-year return, which follows the switch.
  * **Simulator:** an amount in one stock from a chosen date, with four scenarios:
    * dividends reinvested;
    * dividends taken in cash;
    * price only;
    * the same amount in the BRVM Composite.
  * Everything follows the Performance switch (dividends reinvested by default).
* **Checks:**
  * On *Price only*, the YTD column equals BRVM's printed yearly change for every stock. This confirms the split adjustments and the method.
  * Example: 1,000,000 FCFA in SONATEL on 2021-11-23 is worth today:
    * 4.19 M FCFA with dividends reinvested (+319.5 %, the same as the table's 5-year figure);
    * 3.40 M with dividends in cash;
    * 2.83 M on price only;
    * 2.47 M in the Composite.
  * 43 tests pass. The new ones cover the performance table against BRVM and the simulator on a synthetic case.
* **Fix found on the way:** 6 stocks had no country because their names carry no country suffix (CORIS BANK INTERNATIONAL, SUCRIVOIRE, SIB, ERIUM, SIEM, TRITURAF), so the country filters missed them. The country is now taken from the BRVM symbol suffix when the name has none (CBIBF → BF, SCRC → CI). This rule agrees with the name rule for all 45 stocks that have both.
* **Rules documented** in [WEBAPP.md → Compare & screen rules](WEBAPP.md#compare--screen-rules).
* **Waiting for the user:** the review of step 5, then step 6 (market structure).

## 2026-11-24: step 6 built, market structure

* **Request:** step 6 (user: "step 6").
* **Problem:** the bulletins give only the total equity market cap, not the capitalisation or number of shares of each stock.
  * A regression of the daily total on the prices was tried and **rejected**. It gave negative share counts, errors up to 2 %, and SIB at 87 million shares instead of 100 million.
* **Solution:** brvm.org's *Capitalisations* page lists, for the 48 stocks, the number of shares, price, free-float and total capitalisation.
  * A new script, [fetch_shares.py](fetch_shares.py), keeps a snapshot per day in `boc/shares_outstanding.csv`. It runs once a day as a new, non-blocking step 2 of the daily update.
  * The snapshots are loaded into a new table, `shares_outstanding`.
  * First snapshot: 2026-11-24.
* **Checks of the approach:**
  * Shares × our split-adjusted prices give exactly BRVM's total on 2026-11-23 (18,688 bn FCFA).
  * With today's share counts, the gap to BRVM's month-end total stays within −0.7 % to +3.6 % since 2019, but reaches 12 % in 2016–2017 because shares were issued since. **The page starts in 2019.**
* **Built:** a new page, **Market structure**, after the overview:
  * headline figures (SONATEL 20.9 % of the market, top 5 52.0 %);
  * a treemap (area = capitalisation, colour = day change, grouped by sector or country);
  * capitalisation by sector and by country (Côte d'Ivoire 58 %, Sénégal 23 %);
  * concentration since 2019;
  * a table of every stock, with CSV export.
* **Choice:** the free-float figures of brvm.org look doubtful (SONATEL 2.2 %), so they are stored but not shown.
* **Checks:**
  * 47 tests pass. The new ones cover the rebuilt total against BRVM, SONATEL's 1 billion shares, the concentration gap, and the page parser on a saved sample.
  * The page renders in FR/EN on the full and the slim database.
  * The treemap could not be looked at as an image here (Plotly image export not installed): to be checked in the browser.
* **Docs:**
  * [WEBAPP.md → Market structure rules](WEBAPP.md#market-structure-rules);
  * [UPDATE.md](UPDATE.md), step 2;
  * [EXTRACTION.md → Technical tables](EXTRACTION.md#technical-tables).
* **Waiting for the user:** the review of step 6, then step 7 (review of the Bonds and Mutual funds pages).

## 2026-11-24: step 7, review of the Bonds and Mutual funds pages

* **Request:** step 7 (user: "step 7").
* **Review:** I audited both pages on the real data and reported 8 findings.
* **The user chose all 7 proposed changes:**
  * Funds:
    1. ignore impossible NAV dates (67 rows printed 5025 instead of 2025);
    2. flag NAV level breaks: SICAV Abdou DIOUF showed −89 % after its NAV went from 17.6 M to 1.85 M, and now has no performance, with a note;
    3. normalise categories (ACTION, DIVERSIFIE, O, OPCR, RISQUE, "b").
  * Bonds:
    4. one issuer per state (TPNE = Trésor public du Niger…): 37 issuers instead of 43;
    5. 7 short FR/EN categories from 35 section names;
    6. price in % of nominal;
    7. liquidity and headline figures: last trade, sessions traded in 3 months, bonds traded today (10 of 210) and in 3 months (144 of 210).
* **Not changed:** about 5 % of bonds have no maturity year because their names are truncated in the bulletin. A note explains it.
* **Bug found while testing:** for non-state issuers the empty country became `NaN`, which counts as true, so every company was labelled "État : ". Fixed, with a test.
* **Checks:**
  * 49 tests pass.
  * 81 funds now have a 1-year performance, against 78 before, because the future dates were hiding real NAVs.
  * Both pages render in FR/EN on the full and the slim database.
* **Rules documented** in [WEBAPP.md → Bonds and funds rules](WEBAPP.md#bonds-and-funds-rules).
* **Status:** all the steps of the first version are built. **Waiting for the user:** a check of the pages in the browser (steps 1–7), then deployment (step 8).

## 2026-11-24: step 8 started, deployment

* **Request:** step 8 (user: "step 8"). This lifts the hold on deployment decided on 2026-11-23.
* **Check before publishing:**
  * The 56 tracked files contain no secrets.
  * The biggest file is the notebook (1 MB).
  * Two personal details would have been published: the Windows user name, in 9 example paths across 5 files, and the personal email, on the 14 commits.
* **User's decisions:**
  * **Public** repository.
  * **Replace the paths** with `$env:USERPROFILE\Documents\BRVM` or relative paths. Done: README, UPDATE.md, WEBAPP.md, EXTRACTION.md, and the notebook, whose code now prints only the file name.
  * **Commits under the user's name with the GitHub no-reply email.** To do before the first push, once the address is known.
  * **The daily update stays on this PC** for now. GitHub Actions is possible later.
* **Steps for the user** ([WEBAPP.md → Put it online](WEBAPP.md#put-it-online-streamlit-community-cloud)):
  1. create the GitHub account and the empty public repository, and copy the no-reply email;
  2. create the fine-grained token (Contents read/write on that repository only) and store it with the repository name as user environment variables.
* **Then Claude:**
  * rewrites the commit email;
  * adds the remote and pushes;
  * runs the first `publish_app_data.py`;
  * guides the Streamlit Community Cloud setup.
* **Reminder:** check BRVM's terms of use before sharing the link.

## 2026-11-24: code pushed and data published

* **User:**
  * created the GitHub account `IsaacKonan93` and the public, empty repository `IsaacKonan93/brvm-analytics`;
  * stored the token and the repository name as user environment variables.
* **Commit identity:**
  * All 15 commits were rewritten to `Isaac Konan <192088093+IsaacKonan93@users.noreply.github.com>`, with the numeric id read from GitHub's public API. This was done before the first push.
  * The files are unchanged: there is no diff between the old and the new last commit.
  * The local backup refs of the old history were deleted, and the project's git settings now use the no-reply address.
* **Push:** `main` is at <https://github.com/IsaacKonan93/brvm-analytics>.
  * 56 files, no data, PDF, log or virtual environment.
  * GitHub shows only the no-reply address.
  * The token was passed to git for that command only and is not stored in the git settings.
* **Data:** the first `publish_app_data.py` created the release `data-latest` and uploaded `brvm_app.db.zip` (21 MB, last bulletin 2026-11-23).
  * Public URL: `https://github.com/IsaacKonan93/brvm-analytics/releases/download/data-latest/brvm_app.db.zip`.
  * Downloaded anonymously and opened by the app's own download code: integrity ok, the new tables are present, and the copy is reused on the next check.
* **Checked for Streamlit Cloud:** the app imports without PyMuPDF and BeautifulSoup, which Cloud does not install (only `webapp/requirements.txt`).
* **From now on:** the 20:00 task publishes the new data each evening (step 6 of the daily update), since the token is set.
* **Waiting for the user:** the deployment on share.streamlit.io (WEBAPP.md, step 4). Then check the public URL and its "data as of" date.

## 2026-11-24: site online

* **User:** deployed the app on Streamlit Community Cloud: **<https://brvm-analytics.streamlit.app/>**.
* **Checked from outside** (no browser in this session):
  * The app's health endpoint answers `ok`.
  * The data file of the release has been downloaded twice: once by the earlier test, and once by the app at start-up.
  * The address returns a redirect to a script, which is normal: Streamlit Cloud sets a cookie first.
* **Not checkable from here:** how the pages display. To be checked by the user in the browser:
  * the "data as of" date (23 Nov 2026, then 24 Nov after tonight's publish);
  * every page in both languages;
  * the treemap.
* **Still open:** BRVM's terms of use, to check before sharing the link.
