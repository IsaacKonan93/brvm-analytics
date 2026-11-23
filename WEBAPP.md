# BRVM web app (Streamlit, FR/EN)

A public website for analysing the BRVM data in `brvm.db`. It is built with [Streamlit](https://streamlit.io) and Plotly, has a French/English switch, and is designed to be hosted for free on **Streamlit Community Cloud**.

> **Before going public:** the data is republished from the BRVM *Bulletins Officiels de la Cote*. Check BRVM's terms of use for redistributing their market data. Every page shows the source and a "not investment advice" notice.

## Contents

1. [Run it locally](#run-it-locally)
2. [Pages](#pages)
3. [How it works](#how-it-works)
4. [Put it online (Streamlit Community Cloud)](#put-it-online-streamlit-community-cloud)
5. [Daily data updates online](#daily-data-updates-online)
6. [Changing the app](#changing-the-app)
7. [Tests](#tests)

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

The language switch (Français / English) is in the sidebar. The URL keeps it (`?lang=en`), so links can be shared in either language. Every chart has hover tooltips, and every table can be sorted and downloaded as CSV.

| Page | What it shows |
|---|---|
| **Market overview** | Session picker (default: last session). Headline indices (BRVM Composite, BRVM 30, BRVM Prestige; BRVM 10 before 2023) with day and year-to-date change. Equity and bond market cap, value traded, rising / falling / unchanged. Composite history with range buttons (1M → All). Top gainers and losers. Most traded stocks. Sector indices since 1 January. Market cap of equities vs bonds over time. Value traded per month with its 12-month average. |
| **Stock explorer** | Stock picker; `?symbol=SNTS` in the URL opens that stock directly. KPIs: last adjusted price and day change, YTD, 1-year return, P/E, net yield, last dividend. Split-adjusted price with a volume panel below. Dividends per year (adjusted). Splits, with the BRVM notice as evidence. Latest order book (best bid/ask, spread). Notices and shareholder meetings of the company. |
| **Compare & screen** | *Compare:* up to 8 stocks over YTD / 1Y / 3Y / 5Y / All, rebased to 100. Return, annualised volatility and maximum drawdown. Correlation heatmap of daily returns. *Screener:* every listed stock on the last session, with filters on sector, compartment, country, P/E range, minimum yield and minimum average daily value traded over 3 months. Sortable, CSV export. |
| **Bonds** | Every listed bond on the last session, with filters on issuer, category and maturity: coupon, maturity, nominal, price, accrued coupon, next coupon, amortisation. Coupon vs maturity chart, colored by issuer when 3 or fewer issuers are selected. History of one bond (price, accrued coupon). Value traded per year, equities vs bonds. |
| **Mutual funds** | Ranking of the funds with a recent NAV: latest NAV and its date, 1-year and 3-year performance (based on the NAV dates, since NAVs are often published late). Filters on category and manager. NAV chart of up to 4 funds, rebased to 100, with misprinted values filtered out. |

Not in this first version: bond yield-to-maturity, portfolio tracking, alerts.

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
| [webapp/views/](webapp/views/) | One module per page (`overview.py`, `stock.py`, `compare.py`, `bonds.py`, `funds.py`), each with a `render()` function. `common.py` has the table, CSV and chart helpers |
| [webapp/app_lib/data.py](webapp/app_lib/data.py) | Every database query. The database is opened **read-only**. Queries are cached and keyed on the latest bulletin date, so a new bulletin refreshes everything |
| [webapp/app_lib/i18n.py](webapp/app_lib/i18n.py) | French/English labels (`LABELS`), sector / country / fund-category names, number formats (FR `1 234,56`, EN `1,234.56`; amounts `13 277 Mds` / `13.28 tn`) |
| [webapp/app_lib/charts.py](webapp/app_lib/charts.py) | Plotly charts with the project's validated palette: fixed series order, one y-axis per chart (price and volume are two stacked panels), diverging blue↔red with a gray midpoint |
| [.streamlit/config.toml](.streamlit/config.toml) | Theme (primary color `#2a78d6`; light/dark follows the visitor's setting) |
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
