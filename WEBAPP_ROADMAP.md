# Web app roadmap: the plan for the rebuild

This file is the plan for the next version of the web app: what it will offer, what has been decided, and where the work stands. The current version (v1) is described in [WEBAPP.md](WEBAPP.md). Decisions are also logged by date in [JOURNAL.md](JOURNAL.md).

Status markers used below:
* **proposed**: suggested, waiting for the user's decision;
* **decided**: agreed, to be built;
* **done**: built and checked.

## Contents

1. [Goal](#goal)
2. [Status of the rebuild](#status-of-the-rebuild)
3. [Decisions](#decisions)
4. [Features](#features)
5. [Priorities](#priorities)
6. [Keeping the site up to date](#keeping-the-site-up-to-date)
7. [Open questions](#open-questions)

## Goal

The site should give **up-to-date information about the BRVM online**. It has two jobs:

1. **A daily BRVM briefing**: what happened at today's session, refreshed every evening.
2. **Analysis on 10 years of clean history** (since 2016-08-01): split-adjusted prices, total return with dividends, liquidity and valuation. The BRVM website itself does not offer this.

**The official bulletin is always one click away:** the app links to the BOC PDF on brvm.org for any session it shows. This is a feature requested by the user.

## Status of the rebuild

The approach was **decided** on 2026-11-23: revise the existing app page by page. The foundation is kept as it is:
* the data access, `webapp/app_lib/data.py`;
* the French/English switch and number formats, `webapp/app_lib/i18n.py`;
* the chart style, `webapp/app_lib/charts.py`;
* the theme, `.streamlit/config.toml`.

For each page, the user reviews it in the browser and says what to keep, change, move or remove. Then the next page.

| Page | Review status |
|---|---|
| Market overview | **Accepted as is** (2026-11-23). It is now the daily briefing: the written summary, Highlights and Upcoming were added on 2026-11-24 (step 2), waiting for the user's review. |
| Stock explorer | Presented on 2026-11-23. The features decided on 2026-11-24 change it substantially, so it will be reviewed **once rebuilt**. |
| Compare & screen | Not reviewed; the performance table and simulator are added to it |
| Bonds | Not reviewed |
| Mutual funds | Not reviewed |
| Official bulletins (BOC) | **New**, built on 2026-11-24 (step 1); waiting for the user's review |

* **2026-11-23:** the review was paused while the user thought about the app as a whole.
* **2026-11-24:** the open questions were answered (see [Decisions](#decisions)). The next step is to build the decided features.
* **2026-11-24:** step 1, the BOC links, is built and tested. It is waiting for the user's review in the browser.
* **2026-11-24:** step 2, the daily briefing, is built and tested. It is waiting for the user's review in the browser.
* **2026-11-24:** the navigation bar is now Indigo dye `#00416A` (user's request).
* **2026-11-24:** step 3, total return, is built and tested. It is waiting for the user's review in the browser.
* **Deployment online is on hold** until the user says the rebuild is finished. Until then, nothing is pushed to GitHub or published. The deployment steps stay in [WEBAPP.md → Put it online](WEBAPP.md#put-it-online-streamlit-community-cloud).

## Decisions

Taken on 2026-11-24.

| Question | Decision |
|---|---|
| Features of the first version | All four proposed groups: **daily briefing + events**, **stronger stock page**, **performance table + screener**, **simulator + market structure**. The **BOC links** are included as requested. |
| How returns are shown | **Total return by default**, with dividends reinvested. A switch shows price only. |
| Bulletins page | **A date picker plus a list** of recent bulletins, filterable by month and year. |
| Where the daily update runs online | **Decided at deployment.** It stays on this PC for now; GitHub Actions is the alternative (see [Keeping the site up to date](#keeping-the-site-up-to-date)). |

## Features

### 1. Links to the official bulletins (BOC)

Requested by the user.

| Feature | Detail | Status |
|---|---|---|
| **Bulletins page** | A date picker gives the bulletin of that session directly. Below it, a list of the recent bulletins, filterable by month and year, with the link to the PDF on brvm.org. Days without a bulletin (holidays, closures) are marked. | built, to review |
| **"📄 BOC" link everywhere** | Every date shown in the app gets a link to that day's bulletin: a session, a split, a notice. Dividend dates are payment dates, which are not bulletin dates, so they have no link. | built, to review |
| **Link, don't re-host** | The app points to BRVM's own files instead of serving copies. This is safer for licensing. | built, to review |

Technical notes, checked on 2026-11-24:
* **Where the links are.** The brvm.org address of each PDF is in `boc/manifest.csv`, column `url`:
  * 2,524 of the 2,529 downloaded bulletins have it.
  * The 5 without one are 2016-11-07, 2016-12-15, 2017-02-01, 2025-10-30 and 2025-12-01. They were downloaded before the manifest recorded addresses, so their links will be read again from brvm.org.
* **The link cannot be guessed from the date.** 1,136 addresses carry a suffix (e.g. `boc_20261123_2.pdf`), and some have typos. It must be stored. See [SITE_NOTES.md → PDF filenames](SITE_NOTES.md#pdf-filenames).
* **Some brvm.org pages link the wrong file.** For those days, the app links the file that was actually checked. See [SITE_NOTES.md → Pages that link the wrong file](SITE_NOTES.md#pages-that-link-the-wrong-file). The daily page itself can also be linked; its address format is in [SITE_NOTES.md → Daily page URL](SITE_NOTES.md#daily-page-url-slug).
* **Database change (built).** The links are in a new table, `bulletins`: one row per weekday since 2016-08-01, with `status` and `url`. It is rebuilt from the manifest after every extraction run. This was chosen over the planned `documents.url` column for two reasons: it also records the days without a bulletin, which the page needs, and it survives re-extractions. The slim online database keeps it, and its build checks that the links are there. See [EXTRACTION.md → Technical tables](EXTRACTION.md#technical-tables).
* **The 5 missing links were found** on brvm.org on 2026-11-24. All 2,529 bulletins now have their address. `download_all.py` looks up any future missing one by itself.

### 2. Daily briefing (home page, updated each evening)

| Feature | Detail | Status |
|---|---|---|
| **Session summary** | Indices, market cap, value traded, rising/falling stocks, top gainers and losers, most traded. This is the current Market overview, which was accepted. | done (v1) |
| **Written summary FR/EN** | Generated from the figures with text templates, not AI. Example from 2026-11-23: *"The BRVM Composite fell 3.32 % to 476.54 points (BRVM 30: −3.30 %). Year to date: +37.83 %. 1 stock up, 40 down, 5 unchanged. Equity value traded: 1.43 bn FCFA, 51 % below its 3-month average…"* | built, to review |
| **Notable events of the day** | New 52-week highs and lows; stocks at the ±7.5% daily limit; unusual volume (5× the 3-month average); new BRVM notices; splits. The "limit" rule is a move of 7 % or more, because of price ticks. The rules are in [WEBAPP.md → Daily briefing rules](WEBAPP.md#daily-briefing-rules). | built, to review |
| **Upcoming events** | General meetings, plus the dividend payments, splits and first listings announced in the bulletins' operation notices with a future date. Each comes with the 📄 bulletin announcing it. | built, to review |
| **Weekly and monthly recap** | The same blocks over a week or a month. | proposed (after v1) |

### 3. Analysis

| Feature | Detail | Status |
|---|---|---|
| **Total return** | Performance with dividends reinvested, **shown by default** everywhere returns appear, with a switch to price only. BRVM stocks often yield 6–10%, so price-only charts understate returns. Built on 2026-11-24. The new table `dividend_events` places each dividend on its ex-dividend session, and the app reinvests it there. A **Performance** switch in the sidebar (*Dividends reinvested* / *Price only*) drives the stock page and the comparison. See [EXTRACTION.md → Dividends and total return](EXTRACTION.md#dividends-and-total-return-dividend_events--pk-symbol-div_date). | built, to review |
| **Dividends** | Calendar and history per stock: amount, growth, yield. | decided |
| **Liquidity** | Average daily value traded, share of sessions with trades, bid-ask spread. Many BRVM stocks rarely trade. | decided |
| **Valuation over time** | History of a stock's P/E and yield, compared with its sector. | decided |
| **Performance table** | Every stock over 1W / 1M / YTD / 1Y / 3Y / 5Y, sortable. It sits with the existing screener and comparison tool. | decided |
| **Investment simulator** | "1,000,000 FCFA invested in stock X on date Y is worth … today", with or without dividends. | decided |
| **Market structure** | Capitalisation by country and sector. Share of the 5 largest companies (SONATEL alone weighs a lot). Treemap of the market coloured by the day's change. | decided |
| **Bonds** | Upcoming coupon and redemption dates; amounts outstanding by issuer. | proposed (after v1) |
| **Funds** | The NAV ranking. | done (v1) |

### 4. Later

| Feature | Why later |
|---|---|
| Bond yield to maturity | Needs the full repayment schedule of each bond, which the bulletins only give in part. |
| Email alerts | Needs user accounts and a server that sends mail. Streamlit Community Cloud alone cannot do it. |
| Portfolio tracking | Needs user accounts to save portfolios. |

## Priorities

Updated on 2026-11-24 with the user's decisions.

1. **First version of the rebuild** (decided), in the proposed build order. Each step is reviewed in the browser by the user before the next one.
   1. **BOC links:**
      * the `url` in the database and the slim database, and the 5 missing links;
      * the Bulletins page;
      * the "📄 BOC" link on dates.
   2. **Daily briefing:**
      * the written summary, notable events and upcoming events;
      * added to the Market overview.
   3. **Total return:**
      * a total-return series per stock in the data layer;
      * the price/total-return switch.
   4. **Stronger stock page:**
      * total return, dividends, liquidity, valuation history;
      * then the user's review of the page.
   5. **Performance table + screener**, and the **investment simulator**, on the Compare & screen page.
   6. **Market structure**: country/sector breakdown, concentration, treemap.
   7. **Review of the Bonds and Mutual funds pages.**
2. **Then:** the weekly and monthly recap, bond schedules.
3. **Later:** bond yield to maturity, email alerts, portfolio tracking.
4. **Finally:** deployment online.

## Keeping the site up to date

Today the online data would depend on **this PC**:

```
~18:15  BRVM publishes the bulletin
 20:00  the scheduled task on this PC downloads and extracts it, then publishes the slim database
~20:30  the online app has picked it up (re-check every 30 min)
```

If the PC is off or the user is away, the site stops updating. The 09:00 and logon runs only catch up once the PC is back on.

**Alternative:** run the daily download and extraction in the cloud with **GitHub Actions**, which is free for a public repository. The site would then update every evening even with the PC switched off. The PC would keep its own copy for local work.

**Decision (2026-11-24):** this will be chosen at deployment.

## Open questions

The questions of 2026-11-24 are answered; see [Decisions](#decisions). Still to settle later:

1. Where the daily update runs online, at deployment.
2. Which "after v1" items to add, and when: the weekly and monthly recap, bond schedules.
