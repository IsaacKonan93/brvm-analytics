# BRVM web app (Streamlit, FR/EN)

A public website for analysing the BRVM data in `brvm.db`. It is built with [Streamlit](https://streamlit.io) and Plotly, has a French/English switch, and is designed to be hosted for free on **Streamlit Community Cloud**.

> **This describes version 1.** A page-by-page rebuild is in progress, and deployment is on hold until it is finished. The plan and the status are in [WEBAPP_ROADMAP.md](WEBAPP_ROADMAP.md).

> **Before going public:** the data is republished from the BRVM *Bulletins Officiels de la Cote*. Check BRVM's terms of use for redistributing their market data. Every page shows the source and a "not investment advice" notice.

## Contents

1. [Run it locally](#run-it-locally)
2. [Pages](#pages)
3. [How it works](#how-it-works)
4. [Daily briefing rules](#daily-briefing-rules)
5. [Put it online (Streamlit Community Cloud)](#put-it-online-streamlit-community-cloud)
6. [Daily data updates online](#daily-data-updates-online)
7. [Changing the app](#changing-the-app)
8. [Tests](#tests)

## Run it locally

```powershell
cd C:\Users\isaac.konan\Documents\BRVM
.\.env\Scripts\streamlit run webapp/streamlit_app.py
```

Then open <http://localhost:8501>.
* Locally the app reads `brvm.db` directly, so it is always up to date.
* To try it on the slim online database instead:

  ```powershell
  $env:BRVM_DB = "C:\Users\isaac.konan\Documents\BRVM\brvm_app.db"
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
| **Stock explorer** | Stock picker; `?symbol=SNTS` in the URL opens that stock directly. KPIs: last adjusted price and day change, YTD, 1-year return (with dividends reinvested by default), P/E, net yield, last dividend. Price chart with a volume panel below: with dividends reinvested it shows two lines, the price with dividends reinvested and the split-adjusted price, so the gap between them is the dividends. Dividends per year (adjusted). Splits, with the BRVM notice as evidence. Latest order book (best bid/ask, spread). Notices and shareholder meetings of the company. |
| **Compare & screen** | *Compare:* up to 8 stocks over YTD / 1Y / 3Y / 5Y / All, rebased to 100, with dividends reinvested by default. Return, annualised volatility and maximum drawdown. Correlation heatmap of daily returns. *Screener:* every listed stock on the last session, with filters on sector, compartment, country, P/E range, minimum yield and minimum average daily value traded over 3 months. Sortable, CSV export. |
| **Bonds** | Every listed bond on the last session, with filters on issuer, category and maturity: coupon, maturity, nominal, price, accrued coupon, next coupon, amortisation. Coupon vs maturity chart, colored by issuer when 3 or fewer issuers are selected. History of one bond (price, accrued coupon). Value traded per year, equities vs bonds. |
| **Official bulletins (BOC)** | Pick a date to open that session's BOC on brvm.org. On a holiday or weekend, the page says there was no bulletin and offers the previous one. Below that, the list of bulletins of a year, filterable by month: date, weekday, status, link. CSV export. |
| **Mutual funds** | Ranking of the funds with a recent NAV: latest NAV and its date, 1-year and 3-year performance (based on the NAV dates, since NAVs are often published late). Filters on category and manager. NAV chart of up to 4 funds, rebased to 100, with misprinted values filtered out. |

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
| [webapp/views/](webapp/views/) | One module per page (`overview.py`, `stock.py`, `compare.py`, `bonds.py`, `funds.py`, `bulletins.py`), each with a `render()` function. `common.py` has the table, CSV and chart helpers |
| [webapp/app_lib/data.py](webapp/app_lib/data.py) | Every database query. The database is opened **read-only**. Queries are cached and keyed on the latest bulletin date, so a new bulletin refreshes everything |
| [webapp/app_lib/briefing.py](webapp/app_lib/briefing.py) | The daily briefing: notable events of a session, upcoming events read from the notices, the written summary (text templates, no AI) |
| [webapp/app_lib/i18n.py](webapp/app_lib/i18n.py) | French/English labels (`LABELS`), sector / country / fund-category names, number formats (FR `1 234,56`, EN `1,234.56`; amounts `13 277 Mds` / `13.28 tn`) |
| [webapp/app_lib/charts.py](webapp/app_lib/charts.py) | Plotly charts with the project's validated palette: fixed series order, one y-axis per chart (price and volume are two stacked panels), diverging blue↔red with a gray midpoint |
| [.streamlit/config.toml](.streamlit/config.toml) | Theme. Primary color `#2a78d6`; light/dark follows the visitor's setting. The navigation bar (sidebar) is **Indigo dye `#00416A`** with white text in both modes, a lighter indigo `#0A5A8C` for widgets and the selected page, and light-blue accents and links (`#8CC8F2`, `#A9D8FF`) |
| [webapp/requirements.txt](webapp/requirements.txt) | Packages installed by Streamlit Cloud |
| [publish_app_data.py](publish_app_data.py) | Builds and uploads the slim database |

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

## Put it online (Streamlit Community Cloud)

You need to do steps 1, 2 and 4 yourself, because they create accounts and credentials in your name. Step 3 I can do with you.

1. **GitHub account and repository**
   * Create a free account on <https://github.com>.
   * Create a new repository, for example `brvm-analytics`.
     * *Public* is simplest: the code contains no secrets.
     * *Private* also works: Streamlit Cloud can deploy private repositories. The data file then needs a read token in the app secrets (step 4).
   * Do not add a README or license, since the project already has them.

2. **Token for the daily data upload**
   * GitHub → Settings → Developer settings → *Fine-grained personal access tokens* → Generate new token.
   * Settings: *Only select repositories* → `brvm-analytics`; *Repository permissions* → **Contents: Read and write**; expiration up to 1 year (put a reminder to renew it).
   * Store it **once** as a Windows user environment variable. Never put it in a file of the project:

     ```powershell
     [Environment]::SetEnvironmentVariable("BRVM_GITHUB_TOKEN", "<paste the token>", "User")
     [Environment]::SetEnvironmentVariable("BRVM_GITHUB_REPO", "<your-github-name>/brvm-analytics", "User")
     ```

     Open a new terminal afterwards so that it sees the variables.

3. **Push the code and publish the data**

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
