# Web app roadmap: the plan for the rebuild

This file is the plan for the next version of the web app: what it should offer, what has been decided, and where the review stands. The current version (v1) is described in [WEBAPP.md](WEBAPP.md). Decisions are also logged by date in [JOURNAL.md](JOURNAL.md).

Status markers used below:
* **proposed**: suggested, waiting for the user's decision;
* **decided**: agreed, to be built;
* **done**: built and checked.

## Contents

1. [Goal](#goal)
2. [Status of the rebuild](#status-of-the-rebuild)
3. [Features](#features)
4. [Priorities](#priorities)
5. [Keeping the site up to date](#keeping-the-site-up-to-date)
6. [Open questions](#open-questions)

## Goal

The site should give **up-to-date information about the BRVM online**. It has two jobs:

1. **A daily BRVM briefing**: what happened at today's session, refreshed every evening.
2. **Analysis on 10 years of clean history** (since 2016-08-01): split-adjusted prices, dividends, liquidity and valuation. The BRVM website itself does not offer this.

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
| Market overview | **Accepted as is** (2026-11-23) |
| Stock explorer | Presented on 2026-11-23, review pending |
| Compare & screen | Not reviewed |
| Bonds | Not reviewed |
| Mutual funds | Not reviewed |

* **2026-11-23:** the review was **paused**. The user wants to think about the app as a whole before continuing. The feature proposal below was written for that.
* **Deployment online is on hold** until the user says the rebuild is finished. Until then, nothing is pushed to GitHub or published. The deployment steps stay in [WEBAPP.md → Put it online](WEBAPP.md#put-it-online-streamlit-community-cloud).

## Features

All items are **proposed** (2026-11-24) unless marked otherwise.

### 1. Links to the official bulletins (BOC)

Requested by the user.

| Feature | Detail |
|---|---|
| **Bulletins page** | A calendar or list of every session since 2016-08-01, with a link to the PDF on brvm.org. Days without a bulletin (holidays, closures) are marked. |
| **"📄 BOC" link everywhere** | Every date shown in the app gets a link to that day's bulletin: a session, a split, a dividend, a notice. |
| **Link, don't re-host** | The app points to BRVM's own files instead of serving copies. This is safer for licensing. |

Technical notes, checked on 2026-11-24:
* **Where the links are.** The brvm.org address of each PDF is in `boc/manifest.csv`, column `url`:
  * 2,524 of the 2,529 downloaded bulletins have it.
  * The 5 without one are 2016-11-07, 2016-12-15, 2017-02-01, 2025-10-30 and 2025-12-01. They were downloaded before the manifest recorded addresses, so their links will be read again from brvm.org.
* **The link cannot be guessed from the date.** 1,136 addresses carry a suffix (e.g. `boc_20261123_2.pdf`), and some have typos. It must be stored. See [SITE_NOTES.md → PDF filenames](SITE_NOTES.md#pdf-filenames).
* **Some brvm.org pages link the wrong file.** For those days, the app links the file that was actually checked. See [SITE_NOTES.md → Pages that link the wrong file](SITE_NOTES.md#pages-that-link-the-wrong-file). The daily page itself can also be linked; its address format is in [SITE_NOTES.md → Daily page URL](SITE_NOTES.md#daily-page-url-slug).
* **Database change.** The links go into the database: a `url` column in `documents`, filled from the manifest. The slim online database ([publish_app_data.py](publish_app_data.py)) must keep this column.

### 2. Daily briefing (home page, updated each evening)

| Feature | Detail |
|---|---|
| **Session summary** | Indices, market cap, value traded, rising/falling stocks, top gainers and losers, most traded. This is the current Market overview, which was accepted. |
| **Written summary FR/EN** | Generated from the figures with text templates, not AI. Example: *"The Composite fell 0.21% to 492.89. 19 stocks up, 19 down. Most traded: SONATEL…"* |
| **Notable events of the day** | New 52-week highs and lows; stocks at the ±7.5% daily limit; unusual volume (5× the 3-month average); new BRVM notices; splits. |
| **Upcoming events** | General meetings and dividend payment dates, taken from the bulletins. |
| **Weekly and monthly recap** | The same blocks over a week or a month. |

### 3. Analysis

| Feature | Detail |
|---|---|
| **Total return** | Performance with dividends reinvested. BRVM stocks often yield 6–10%, so price-only charts understate returns. It is computed from the split-adjusted prices and dividends already in the database (`equity_quotes_adjusted`). |
| **Investment simulator** | "1,000,000 FCFA invested in stock X on date Y is worth … today", with or without dividends. |
| **Liquidity** | Average daily value traded, share of sessions with trades, bid-ask spread. Many BRVM stocks rarely trade. |
| **Dividends** | Calendar and history per stock: amount, growth, yield. |
| **Valuation over time** | History of a stock's P/E and yield, compared with its sector. |
| **Market structure** | Capitalisation by country and sector. Share of the 5 largest companies (SONATEL alone weighs a lot). Treemap of the market coloured by the day's change. |
| **Performance table** | Every stock over 1W / 1M / YTD / 1Y / 3Y / 5Y, sortable. It sits with the existing screener and comparison tool. |
| **Bonds** | Upcoming coupon and redemption dates; amounts outstanding by issuer. |
| **Funds** | The NAV ranking, already in v1. |

### 4. Later

| Feature | Why later |
|---|---|
| Bond yield to maturity | Needs the full repayment schedule of each bond, which the bulletins only give in part. |
| Email alerts | Needs user accounts and a server that sends mail. Streamlit Community Cloud alone cannot do it. |
| Portfolio tracking | Needs user accounts to save portfolios. |

## Priorities

Proposed on 2026-11-24, waiting for the user's decision.

1. **First version:**
   * the daily briefing with notable and upcoming events;
   * BOC links: the Bulletins page and the link on every date;
   * the stock page with total return, dividends and liquidity;
   * the performance table and screener.
2. **Then:** the investment simulator, market structure and the treemap, bond schedules, the weekly and monthly recap.
3. **Later:** bond yield to maturity, email alerts, portfolio tracking.

## Keeping the site up to date

Today the online data would depend on **this PC**:

```
~18:15  BRVM publishes the bulletin
 20:00  the scheduled task on this PC downloads and extracts it, then publishes the slim database
~20:30  the online app has picked it up (re-check every 30 min)
```

If the PC is off or the user is away, the site stops updating. The 09:00 and logon runs only catch up once the PC is back on.

**Alternative (proposed):** run the daily download and extraction in the cloud with **GitHub Actions**, which is free for a public repository. The site would then update every evening even with the PC switched off. The PC would keep its own copy for local work. To be decided at deployment.

## Open questions

For the user, before the rebuild resumes:

1. Which features go into the first version? (See [Priorities](#priorities).)
2. Should prices be shown as **total return** (dividends reinvested) by default, or price only, with a switch?
3. Bulletins page: a **calendar** view or a **list** with a search by date?
4. Daily update: keep it on this PC, or move it to **GitHub Actions**? (Decided at deployment.)
5. Stock explorer: the v1 review is still pending.
