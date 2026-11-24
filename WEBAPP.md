# BRVM web app (Streamlit, FR/EN)

A public website for analysing the BRVM data in `brvm.db`. It is built with [Streamlit](https://streamlit.io) and Plotly, has a French/English switch, and is designed to be hosted for free on **Streamlit Community Cloud**.

> **This describes version 1.** A page-by-page rebuild is in progress, and deployment is on hold until it is finished. The plan and the status are in [WEBAPP_ROADMAP.md](WEBAPP_ROADMAP.md).

> **Before going public:** the data is republished from the BRVM *Bulletins Officiels de la Cote*. Check BRVM's terms of use for redistributing their market data. Every page shows the source and a "not investment advice" notice.

## Contents

1. [Run it locally](#run-it-locally)
2. [Pages](#pages)
3. [How it works](#how-it-works)
4. [Daily briefing rules](#daily-briefing-rules)
5. [Stock page rules](#stock-page-rules)
6. [Market structure rules](#market-structure-rules)
7. [Compare & screen rules](#compare--screen-rules)
8. [Bonds and funds rules](#bonds-and-funds-rules)
9. [Put it online (Streamlit Community Cloud)](#put-it-online-streamlit-community-cloud)
10. [Daily data updates online](#daily-data-updates-online)
11. [Changing the app](#changing-the-app)
12. [Tests](#tests)

## Run it locally

```powershell
cd $env:USERPROFILE\Documents\BRVM
.\.env\Scripts\streamlit run webapp/streamlit_app.py
```

Then open <http://localhost:8501>.
* Locally the app reads `brvm.db` directly, so it is always up to date.
* To try it on the slim online database instead:

  ```powershell
  $env:BRVM_DB = "$env:USERPROFILE\Documents\BRVM\brvm_app.db"
  .\.env\Scripts\streamlit run webapp/streamlit_app.py
  ```

  Build `brvm_app.db` first with `python publish_app_data.py --dry-run`.

## Pages

The sidebar has two switches, both kept in the URL so links can be shared as they are:
* **Language**, *Français / English* (`?lang=en`).
* **Performance**, *Dividends reinvested* (default) or *Price only* (`?basis=tr` / `?basis=price`). With dividends reinvested, returns are total returns: the net dividend is reinvested on its ex-dividend session (see [EXTRACTION.md → Dividends and total return](EXTRACTION.md#dividends-and-total-return-dividend_events--pk-symbol-div_date)). The switch drives the stock page (chart, YTD and 1-year return) and the comparison (rebased chart, return, volatility, drawdown, correlation). Daily changes, the movers and the BRVM indices stay as BRVM publishes them, on price.

Wherever a session date is shown, a **📄 BOC** link opens that day's official bulletin on brvm.org: the sidebar "Data as of", the overview and bonds session, the stock's last session, its order book, its splits and its notices. The app links to BRVM's own files and does not re-host them. Every chart has hover tooltips, and every table can be sorted and downloaded as CSV.

| Page | What it shows |
|---|---|
| **Market overview** | Session picker (default: last session). **Daily briefing:** a written summary of the session in French or English; *Highlights* (52-week highs and lows, moves close to the ±7.5 % limit, unusual trading, splits, new notices); *Upcoming* (general meetings, dividend payments, splits and first listings announced in the bulletins), each with the 📄 bulletin announcing it. Rules: [Daily briefing rules](#daily-briefing-rules). Headline indices (BRVM Composite, BRVM 30, BRVM Prestige; BRVM 10 before 2023) with day and year-to-date change. Equity and bond market cap, value traded, rising / falling / unchanged. Composite history with range buttons (1M → All). Top gainers and losers. Most traded stocks. Sector indices since 1 January. Market cap of equities vs bonds over time. Value traded per month with its 12-month average. |
| **Market structure** | Session picker (since 2019). Equity market cap, listed companies, weight of the largest company and of the top 5. **Treemap** of the market: one rectangle per stock, area = capitalisation, colour = day change (blue up, red down, grey unchanged), grouped by sector or country. Capitalisation by sector and by country (% of the market). Concentration since 2019: month-end weight of the largest stock and of the top 5. Table of every stock: rank, capitalisation, weight, number of shares, price, change; CSV export. Rules: [Market structure rules](#market-structure-rules). |
| **Stock explorer** | Stock picker; `?symbol=SNTS` in the URL opens that stock directly. Caption: country, sector, compartment, last session with its 📄 BOC. KPIs: last adjusted price and day change, YTD and 1-year return (dividends reinvested by default), P/E, net yield, last dividend. Price chart with a volume panel below; with dividends reinvested it shows the price with dividends reinvested next to the split-adjusted price. Four tabs: **Dividends**: a dividend announced and not yet paid; trailing 12-month yield, 5-year growth of the yearly dividend, years with a dividend; dividend per payment year; every dividend with its ex-date (📄 BOC), payment date, amount as printed, adjusted amount and yield at the ex-date. **Liquidity**, over 3 months, 1 year or 3 years: average value and volume per session, share of sessions with trades, liquidity rank among the listed stocks; value traded per month; order book at the close and the bid-ask spread over the last 90 sessions. **Valuation**: P/E and net yield since 2016 against the median of the stock's sector and of the market. **Events**: splits, notices, shareholder meetings. Rules: [Stock page rules](#stock-page-rules). |
| **Compare & screen** | Four tabs, all following the Performance switch. *Compare:* up to 8 stocks over YTD / 1Y / 3Y / 5Y / All, rebased to 100; return, annualised volatility and maximum drawdown; correlation heatmap of daily returns. *Performance:* every listed stock over 1 week, 1 month, YTD, 1, 3 and 5 years (plus 3 and 5 years per year), with filters on sector and country and a bar chart ranking the stocks over the chosen horizon; sortable, CSV export. *Screener:* every listed stock on the last session, with filters on sector, country, compartment, P/E range, minimum yield and minimum average daily value traded over 3 months, and its 1-year return; sortable, CSV export. *Simulator:* an amount invested in one stock on a chosen date, and its value today with dividends reinvested, with dividends taken in cash, on price only, and in the BRVM Composite; chart and table with gain and gain per year. Rules: [Compare & screen rules](#compare--screen-rules). |
| **Bonds** | Headline figures: bond market cap, value traded, bonds traded today and in the last 3 months. Every listed bond on the last session, with filters on issuer (one per state: *State: Côte d'Ivoire*…), category (sovereign, corporate, regional financial institutions, securitisation, GSS, convertible) and maturity: coupon, maturity, price in % of nominal and in FCFA, nominal, accrued coupon, next coupon, amortisation, **last trade** and sessions traded in 3 months. Coupon vs maturity chart, colored by issuer when 3 or fewer issuers are selected. History of one bond (price in % of nominal, accrued coupon). Value traded per year, equities vs bonds. Rules: [Bonds and funds rules](#bonds-and-funds-rules). |
| **Official bulletins (BOC)** | Pick a date to open that session's BOC on brvm.org. On a holiday or weekend, the page says there was no bulletin and offers the previous one. Below that, the list of bulletins of a year, filterable by month: date, weekday, status, link. CSV export. |
| **Mutual funds** | Ranking of the funds with a recent NAV: latest NAV and its date, 1-year and 3-year performance (based on the NAV dates, since NAVs are often published late). Filters on category and manager. NAV chart of up to 4 funds, rebased to 100, with misprinted values filtered out. Misprinted NAV dates are left out, and a fund whose NAV changed level (e.g. a change of unit) has no performance, with a note. Rules: [Bonds and funds rules](#bonds-and-funds-rules). |

Not in this first version: bond yield-to-maturity, portfolio tracking, alerts. The features planned for the next version are listed in [WEBAPP_ROADMAP.md → Features](WEBAPP_ROADMAP.md#features).

## How it works

```
brvm.db (this PC, updated by daily_update.py)
   ├─ locally: read directly by the app
   └─ publish_app_data.py ──> brvm_app.db.zip ──> GitHub release "data-latest"
                                                      └─ downloaded by the online app (re-checked every 30 min)
```

| File | Role |
|---|---|
| [webapp/streamlit_app.py](webapp/streamlit_app.py) | Entry point: language switch, navigation, "data as of" date, footer |
| [webapp/views/](webapp/views/) | One module per page (`overview.py`, `structure.py`, `stock.py`, `compare.py`, `bonds.py`, `funds.py`, `bulletins.py`), each with a `render()` function. `common.py` has the table, CSV and chart helpers |
| [webapp/app_lib/data.py](webapp/app_lib/data.py) | Every database query. The database is opened **read-only**. Queries are cached and keyed on the latest bulletin date, so a new bulletin refreshes everything |
| [webapp/app_lib/briefing.py](webapp/app_lib/briefing.py) | The daily briefing: notable events of a session, upcoming events read from the notices, the written summary (text templates, no AI) |
| [webapp/app_lib/i18n.py](webapp/app_lib/i18n.py) | French/English labels (`LABELS`), sector / country / fund-category names, number formats (FR `1 234,56`, EN `1,234.56`; amounts `13 277 Mds` / `13.28 tn`) |
| [webapp/app_lib/charts.py](webapp/app_lib/charts.py) | Plotly charts with the project's validated palette: fixed series order, one y-axis per chart (price and volume are two stacked panels), diverging blue↔red with a gray midpoint |
| [.streamlit/config.toml](.streamlit/config.toml) | Theme. Primary color `#2a78d6`; light/dark follows the visitor's setting. The navigation bar (sidebar) is **Indigo dye `#00416A`** with white text in both modes, a lighter indigo `#0A5A8C` for widgets and the selected page, and light-blue accents and links (`#8CC8F2`, `#A9D8FF`) |
| [webapp/requirements.txt](webapp/requirements.txt) | Packages installed by Streamlit Cloud |
| [publish_app_data.py](publish_app_data.py) | Builds and uploads the slim database |
| [fetch_shares.py](fetch_shares.py) | Daily snapshot of the number of shares of every stock from brvm.org (market structure) |

**Which database the app uses,** in this order:
1. `BRVM_DB`: a path, from an environment variable or Streamlit secret;
2. `brvm.db` in the project folder (local use);
3. `BRVM_DATA_URL`: the published zip (online). If a later check fails, the app keeps serving the previous copy.

**The slim database** (`publish_app_data.py`) is 112 MB, or about 20 MB zipped, compared with 194 MB for the full one. It is the full database minus:
* the extraction logs and TOTAL lines;
* the 64,000 daily meeting mentions, replaced by one row per meeting;
* the order book older than 90 sessions;
* duplicate fund NAVs.

Its integrity is checked before upload.

## Daily briefing rules

The Market overview computes the briefing for the chosen session, so any past session can be replayed. The rules are in [webapp/app_lib/briefing.py](webapp/app_lib/briefing.py):

| Item | Rule |
|---|---|
| Written summary | Composite (and BRVM 30) change and level, year-to-date change, rising / falling / unchanged, equity value traded against its average of the previous 63 sessions (about 3 months), the share of the most traded stock when it is 25 % or more, the top gainer and loser. |
| 52-week high / low | Split-adjusted reference price above the highest (below the lowest) of the previous 365 days, for stocks listed for at least a year. |
| Close to the daily limit | Change of 7 % or more either way. The BRVM limit is ±7.5 %, but prices move in ticks, so a stock at the limit often shows −7.33 % or +7.41 %. |
| Unusual trading | Value traded at least 5 times its average of the previous 63 sessions. |
| Splits | Corporate actions (see [EXTRACTION.md](EXTRACTION.md#splits-and-adjusted-prices-corporate_actions-price_anomalies-adjustment_factors-view-equity_quotes_adjusted)) taking effect that day. |
| New notices | Notices of the day's bulletin that were not in the previous bulletin. |
| Upcoming | General meetings dated after the session and already announced. Operation notices of the last 15 bulletins whose text gives a future date ("le 27/10/2026", "le 1er décembre 2026"): dividend payments, splits, first listings. Other operations are shown with their original French text. |

**Calibration on 2026:** about 1 unusual-trading event and 1 limit move per session, and 3 to 4 new 52-week highs on average during that rising year.

**2016–2017 bulletins** have no market statistics. The rising/falling counts and the value traded are then computed from the quotes, which give the same values as BRVM's figures where both exist.

## Stock page rules

The functions are in [webapp/app_lib/data.py](webapp/app_lib/data.py): `dividend_history`, `dividend_stats`, `liquidity_table`, `spreads` and `valuation_history`.

| Item | Rule |
|---|---|
| Dividends | From `dividend_events` (see [EXTRACTION.md → Dividends and total return](EXTRACTION.md#dividends-and-total-return-dividend_events--pk-symbol-div_date)): net amounts after withholding tax, adjusted for splits. |
| Yield at ex-date | Adjusted dividend / adjusted close of the previous session. |
| Trailing 12-month yield | Dividends gone ex in the last 365 days / last adjusted price. BRVM's published yield uses the last dividend even when it is older, e.g. STAC: 3.03 % published, 0 % here, because its last dividend was in 2022. |
| Dividend growth | Yearly dividend (by payment year) of the last payment year against 5 years earlier, per year. It can be high after a cut: SGBC paid 206 to 368 FCFA in 2019–2021, then 2,299 in 2026. |
| Announced dividend | A dividend or split notice of the last bulletins with a future date, matched to the company by name (as for the daily briefing). |
| Liquidity | Over the chosen period. Every session counts, including those without trades (value 0). Rank by average value traded among the stocks quoted on the last session. |
| Spread | (best ask − best bid) / mid price at the close, over the last 90 sessions with both a bid and an ask. The slim online database keeps 90 sessions of order book, so this works online too. |
| Valuation | P/E and net yield as printed by BRVM. P/E below 0 or above 100 and yields above 30 % are left out. The sector is the stock's **current** sector over the whole history: BRVM's sector codes only exist since 2023 and changed in 2025. The medians include the stock itself. |

## Market structure rules

| Item | Rule |
|---|---|
| Capitalisation of a stock | Number of shares × split-adjusted reference price of the session (`market_structure` in [webapp/app_lib/data.py](webapp/app_lib/data.py)). The bulletins only give the market total, so the number of shares comes from brvm.org's *Capitalisations* page, through a daily snapshot ([fetch_shares.py](fetch_shares.py)). On 2026-11-23 the stocks add up to exactly BRVM's published total (18,688 bn FCFA). |
| Older sessions | The latest share counts are used, with prices adjusted to today's share basis. This assumes no new shares were issued since. From 2019 the rebuilt month-end total stays within −0.7 % to +3.6 % of BRVM's figure. Before 2019 the gap reaches 12 %, because shares were issued since, so the page starts in 2019. As snapshots accumulate, future share issues will be recorded. |
| Treemap | Area = capitalisation. Colour = day change on the diverging scale red ← grey (0) → blue, clipped at ±7.5 % (the daily limit). A sector or country rectangle is coloured by the capitalisation-weighted change of its stocks. |
| Concentration | Month-end weight of the largest stock and of the 5 largest, in % of the rebuilt total. |
| Free float | brvm.org also gives a free-float capitalisation, but its values look doubtful (SONATEL 2.2 %), so the app does not show it. |

## Compare & screen rules

| Item | Rule |
|---|---|
| Performance horizons | `performance_table` in [webapp/app_lib/data.py](webapp/app_lib/data.py). Return from the last session on or before the start of the horizon (1 week, 1 month, 31 December of last year, 1, 3 or 5 years earlier) to the last session. A stock listed for less time has no value for that horizon. On *Price only*, the YTD column equals the yearly change printed by BRVM, checked for every stock. |
| Per year | 3 and 5 years: (1 + return) ^ (1 / years) − 1. |
| Simulator | `simulate` in [webapp/views/compare.py](webapp/views/compare.py). Purchase at the reference price of the first session from the chosen date; fractional shares; no brokerage fees. Four scenarios: *dividends reinvested* (total return), *dividends taken in cash* (shares × price + net dividends received so far), *price only*, and the same amount in the BRVM Composite, which is a price index without dividends. |

## Bonds and funds rules

| Item | Rule |
|---|---|
| Bond issuer | `bond_issuer` in [webapp/app_lib/data.py](webapp/app_lib/data.py). The bulletins name the same state in several ways (TPCI, "TPCI (TAUX DE BASE + SPREAD) %", TPNE and "TRESOR PUBLIC DU NIGER", TPBF, "ETAT DU BURKINA" and its diaspora bonds…), so sovereign bonds are grouped by state. Other issuers lose the *green / social / gender bond* labels (SOCIAL BOND CRRH-UEMOA → CRRH-UEMOA). Result: 37 issuers instead of 43, with Côte d'Ivoire at 70 bonds. |
| Bond category | `bond_category`: the 35 section names used since 2016 (French and English) are mapped to 7 short categories: sovereign, corporate, regional financial institutions, securitisation (FCTC), green/social/sustainability (GSS), convertible, sukuk. |
| Price in % of nominal | Reference price / nominal × 100. The nominal is the remaining one, which falls as an amortising bond is repaid (e.g. 4,000 FCFA instead of 10,000), so the % compares across bonds. |
| Bond liquidity | Last session with a volume, and number of sessions with a volume over the last 3 months. On 2026-11-23, 10 of 210 bonds traded, and 144 traded at least once in 3 months. |
| Fund NAV dates | A NAV dated after its bulletin is a misprint (67 rows dated 5025 instead of 2025) and is left out. |
| Fund NAV level break | After removing isolated misprints, a move of more than ×1.5 (or ÷1.5) between two NAV dates that lasts is treated as a change of unit, not a performance (e.g. SICAV Abdou DIOUF in 2026: 17.6 M → 1.85 M). A performance whose period contains such a break is not computed, and a note names the fund. 4 funds have one since 2016. |
| Fund category | The printed codes are normalised: ACTION → A, DIVERSIFIE → D, "A MOYEN ET LON" → OMLT, OPCR / RISQUE → capital risque, "b" → unknown. Each fund gets its latest known category. |

## Put it online (Streamlit Community Cloud)

You need to do steps 1, 2 and 4 yourself, because they create accounts and credentials in your name. Step 3 I can do with you.

**Decisions taken on 2026-11-24:**
* **Public repository.** The code contains no secrets.
* **Generic paths in the docs:** `$env:USERPROFILE\Documents\BRVM`, so no personal user name is published.
* **Commits under your name with your GitHub no-reply email**, so your personal email is not published.
* **The daily update stays on this PC.** The site updates on the days the PC is on. Moving it to GitHub Actions is possible later (see [WEBAPP_ROADMAP.md](WEBAPP_ROADMAP.md#keeping-the-site-up-to-date)).
* **Check BRVM's terms of use before sharing the link** (see the note at the top of this file).

1. **GitHub account and repository**
   * Create a free account on <https://github.com>.
   * Create a new repository, for example `brvm-analytics`.
     * *Public* is simplest: the code contains no secrets.
     * *Private* also works: Streamlit Cloud can deploy private repositories. The data file then needs a read token in the app secrets (step 4).
   * Do not add a README or license, since the project already has them.
   * **No-reply email:** GitHub → Settings → *Emails* → tick *Keep my email addresses private*, and copy the address shown, of the form `12345678+name@users.noreply.github.com`. Before the first push, the commits are rewritten to use it, and the project's git settings use it for the next commits.

2. **Token for the daily data upload**
   * GitHub → Settings → Developer settings → *Fine-grained personal access tokens* → Generate new token.
   * Settings: *Only select repositories* → `brvm-analytics`; *Repository permissions* → **Contents: Read and write**; expiration up to 1 year (put a reminder to renew it).
   * Store it **once** as a Windows user environment variable. Never put it in a file of the project:

     ```powershell
     [Environment]::SetEnvironmentVariable("BRVM_GITHUB_TOKEN", "<paste the token>", "User")
     [Environment]::SetEnvironmentVariable("BRVM_GITHUB_REPO", "<your-github-name>/brvm-analytics", "User")
     ```

     Open a new terminal afterwards so that it sees the variables.

3. **Set the commit identity, push the code and publish the data**

   Done once, before the first push, while nothing is published yet. It rewrites the author email of the existing commits, then makes the project use the no-reply email:

   ```powershell
   git config user.email "<your no-reply address>"
   git filter-branch -f --env-filter 'export GIT_AUTHOR_EMAIL="<your no-reply address>"; export GIT_COMMITTER_EMAIL="<your no-reply address>"' -- --all
   git log --format="%an <%ae>" | Sort-Object -Unique    # check: only the no-reply address
   ```

   Then:

   ```powershell
   git remote add origin https://github.com/<your-github-name>/brvm-analytics.git
   git push -u origin main
   .\.env\Scripts\python.exe publish_app_data.py      # creates the release "data-latest" and uploads the data
   ```

   It prints the public URL of the data file:
   `https://github.com/<your-github-name>/brvm-analytics/releases/download/data-latest/brvm_app.db.zip`

4. **Deploy on Streamlit Community Cloud**
   * Go to <https://share.streamlit.io>, sign in with GitHub, then **Create app** → *Deploy a public app from GitHub*.
   * Repository `brvm-analytics`, branch `main`, main file path **`webapp/streamlit_app.py`**. Choose an app URL (e.g. `brvm-analytics.streamlit.app`).
   * *Advanced settings*:
     * Python 3.12;
     * **Secrets**:

       ```toml
       BRVM_DATA_URL = "https://github.com/<your-github-name>/brvm-analytics/releases/download/data-latest/brvm_app.db.zip"
       # only for a private repository: a fine-grained token with "Contents: Read-only" on the repo
       # BRVM_DATA_TOKEN = "github_pat_..."
       ```
   * **Deploy.** The first start takes a few minutes (it installs the packages, then downloads the data).

## Daily data updates online

Once `BRVM_GITHUB_TOKEN` is set, the daily update ([UPDATE.md](UPDATE.md)) gets a 6th step: **publish web data**.
* When there is a new bulletin, it rebuilds the slim database and replaces the release file.
* The online app notices within 30 minutes and shows the new "data as of" date.
* `logs/web_published.txt` records the last date published. If an upload fails, it is retried at the next run.
* Without a token, the step prints `publish skipped` and does nothing.

Notes about Streamlit Community Cloud (free tier):
* An app with no visitors for several days is put to sleep. The next visitor clicks "wake up" and waits about a minute.
* It has about 1 GB of memory, which is enough for this app.
* Code changes go online automatically when you `git push`.

## Changing the app

* **A label or translation:** edit `LABELS` in `webapp/app_lib/i18n.py`. Each entry is `key: (French, English)`; the test `test_translations_complete` fails if one side is empty.
* **A new chart on a page:** add a query function in `data.py` (decorated with `@st.cache_data`, first argument `v = data.as_of()`), then call a helper from `charts.py` in the page's `render()`.
* **A new page:** create `webapp/views/<name>.py` with `render()`, add a `st.Page(...)` line in `streamlit_app.py`, and add its title label `page_<name>`.
* **Chart rules:**
  * keep the series colors in the `SERIES` order;
  * never use two y-axes;
  * legends for 2 or more series, end labels for up to 4.

## Tests

```powershell
.\.env\Scripts\python.exe -m pytest tests
```

`tests/test_webapp.py` checks:
* the translations and number formats;
* values from the data layer, e.g. SONATEL's adjusted price on 2026-10-22 = 4,200 and the Composite on 2025-10-30 = 344.36;
* every page rendered in French and English with no error;
* the full app with the language switch.
