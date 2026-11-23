# BOC extraction → SQLite database (`brvm.db`)

The extraction is Python code that reads every downloaded BOC PDF (`boc/boc_YYYY-MM-DD.pdf`) and loads the daily data of all BRVM-listed assets into **`brvm.db`** (SQLite). It runs again whenever new PDFs arrive. Downloading is covered in [README.md](README.md), and the website quirks in [SITE_NOTES.md](SITE_NOTES.md).

> **State on 2026-11-18:** 2,525 bulletins (2016-08-01 → 2026-11-17) extracted in about 3½ minutes.
> * 2,524 bulletins are `ok`. The 1 `partial` is due to an 8 FCFA arithmetic error in BRVM's own total on 2017-11-29.
> * Database size: 194 MB.
> * The sum of the rows equals the TOTAL printed by BRVM in **2,521/2,521** bulletins for equities and **2,254/2,254** for bonds (volume).
>
> Full figures are in [qc_report.md](qc_report.md).

## Contents

1. [Quick start](#quick-start)
2. [What is extracted](#what-is-extracted)
3. [Files](#files)
4. [How the PDFs are read](#how-the-pdfs-are-read)
5. [Layout eras](#layout-eras)
6. [Database schema](#database-schema)
7. [Quality control](#quality-control)
8. [Known limitations](#known-limitations)
9. [Example queries](#example-queries)
10. [Maintenance: when BRVM changes its layout](#maintenance-when-brvm-changes-its-layout)

## Quick start

```powershell
.\.env\Scripts\pip install -r requirements.txt   # pymupdf, pytest, requests, beautifulsoup4

python extract_boc.py                  # new or changed PDFs only (incremental), 6 worker processes
python extract_boc.py --reprocess      # re-extract everything (e.g. after a parser change)
python extract_boc.py --date 2025-10-30
python extract_boc.py --from 2025-01-01 --to 2025-12-31
python extract_boc.py --qc             # writes qc_report.md
python -m pytest tests                 # unit and golden tests (11 tests)
python survey_layouts.py               # optional: layout survey of all PDFs -> survey/*.csv
```

**Daily routine** (after about 19:00 GMT, when the evening BOC is online):

```powershell
python download_all.py ; python extract_boc.py
```

Both steps are incremental. A PDF is re-extracted when:
* it is new;
* its size or modification time changed;
* `brvm_extract.PARSER_VERSION` changed.

## What is extracted

| BOC section | Table | One row per |
|---|---|---|
| Equity quotes (all compartments) | `equity_quotes` | bulletin × stock |
| Rights market (droits de souscription) | `right_quotes` | bulletin × right |
| Bond quotes (state, regional, private, sukuk, FCTC, GSS, convertible) | `bond_quotes` | bulletin × bond |
| Order book at the close (best bid/ask, residual quantities) | `order_book` | bulletin × market × security |
| Headline, compartment and sector indices | `index_values` | bulletin × index |
| Market figures (capitalisation, volumes, breadth, PER, yield, ratios) | `market_stats` | bulletin × key |
| Mutual funds (FCP/SICAV) net asset values | `fund_navs` | bulletin × fund |
| "Opérations en cours", "Avis", "Communiqués" | `corporate_notices` | bulletin × notice |
| Shareholder meetings (AGO/AGE) | `meeting_mentions`, view `general_meetings` | bulletin × meeting / meeting (deduplicated) |
| TOTAL lines printed in the BOC | `table_totals` | bulletin × total line |
| Master data (latest name, sector, bond terms) | `securities` | security |
| Processing status, warnings and checks | `documents`, `extraction_log` | bulletin / message |

The "plus fortes hausses / baisses" (top movers) block is **not** stored, because it can be derived from `equity_quotes`.

## Files

| File | Role |
|---|---|
| [extract_boc.py](extract_boc.py) | CLI: selects PDFs, runs workers, writes the DB |
| [survey_layouts.py](survey_layouts.py) | Layout survey of all PDFs (headings, table header signatures) → `survey/` |
| [brvm_extract/pdfdoc.py](brvm_extract/pdfdoc.py) | PDF loading (PyMuPDF): words with coordinates, lines, locale, rotation/scale normalisation, bilingual-file cut |
| [brvm_extract/values.py](brvm_extract/values.py) | Parsing of numbers, percentages and dates (French and English formats), flags NC/SP/ND… |
| [brvm_extract/columns.py](brvm_extract/columns.py) | Generic table reader: header anchors, column refinement, rows, groups, totals, page continuation |
| [brvm_extract/parsers/quotes.py](brvm_extract/parsers/quotes.py) | Equities, rights, bonds, order book |
| [brvm_extract/parsers/market.py](brvm_extract/parsers/market.py) | Indices and market statistics |
| [brvm_extract/parsers/funds.py](brvm_extract/parsers/funds.py) | Mutual fund NAVs |
| [brvm_extract/parsers/events.py](brvm_extract/parsers/events.py) | Notices and shareholder meetings |
| [brvm_extract/pipeline.py](brvm_extract/pipeline.py) | Runs all sections on one PDF, reconstructs clipped values, runs the checksums |
| [brvm_extract/db.py](brvm_extract/db.py) | SQLite schema, writes, `securities` rebuild |
| [brvm_extract/qc.py](brvm_extract/qc.py) | Quality report `qc_report.md` |
| [tests/](tests/) | `test_values.py` (parsing rules) and `test_golden.py` (real values from one bulletin per era) |

## How the PDFs are read

The BOC PDFs contain real text, so no OCR is needed. Plain text extraction does not work, though:
* `pdftotext -layout` interleaves the columns;
* `-raw` drops empty cells, which shifts every later value of the row.

The code therefore works on **words with their coordinates** (PyMuPDF, about 0.1 s per bulletin; pdfplumber was 40× slower).

1. **Page normalisation** (`pdfdoc._page`):
   * Rotated pages (`/Rotate 90`, the 2016–2018 fund pages) are mapped to displayed coordinates.
   * Pages drawn at 10× scale (some 2020–2022 fund pages, 5,950 × 8,420 pt) are scaled back to A4.
2. **Bilingual files:** if a PDF holds a second front page, only the first bulletin is kept (`pdfdoc.load`). For example, `boc_2017-12-20.pdf` also contains the English bulletin of 2017-12-19.
3. **Lines and numbers:** words are grouped into lines by vertical position. Number fragments split on the thousands separator are re-joined (`14` + `455` → `14 455`, `5,50` + `%`). The gap inside a number is about 2 pt; between columns it is 10 pt or more.
4. **Locale:** a document is `fr` (`1 234,56`) or `en` (`1,234.56`), from counts of each number pattern. Order-book prices always use comma thousands (`9,995 / 10,000`), even in French bulletins.
5. **Tables** (`columns.read_table`):
   1. **Header.** The header block is the set of lines around the line containing `Symbole`/`Symbol`.
   2. **Anchors.** Each column of the spec is matched to a header word, searched left to right, e.g. `Clôt.`/`Clos.` for the close. Each anchor must be at least 8 pt right of the previous one (12 pt for the day change, to avoid the `jour` of "Cours du jour").
   3. **Refined positions.** Column centres are refined from the data (median x of the values assigned to each column, two passes). Numbers are right-aligned and can sit far from their header.
   4. **Assignment.** Each value goes to the nearest column, so an empty cell never shifts the others (e.g. SICOR without volume).
   5. **Rows.** A row starts on a line whose first word is a symbol in the symbol column and that has values. Other lines (wrapped names, the sector code of the 2023+ layouts, numbers split over two lines) attach to the vertically nearest row.
   6. **Groups.** Headings (`COMPARTIMENT PRESTIGE`, `SECTEUR - FINANCES 58,91 points`, `OBLIGATIONS D'ETAT`, `FCTC D'ENTREPRISES`…) set the group of the following rows.
   7. **Totals.** `TOTAL` lines are kept as checksums. When their numbers are printed on the next line, they are taken from there.
   8. **Page continuation.** A table that reaches the bottom of a page continues on the next page, because the BOC does not repeat the header. It stops at a stop heading (`MARCHE DES…`, `OPCVM`, `ASSEMBLEES`…).
6. **Layout choice:** the old 2016–2017 column set is used when the header has `Moy.`/`Average` or `Bas`/`Haut`/`Low`/`High`. The layout is detected from the header, not from the date.

## Layout eras

From the [layout survey](survey_layouts.py) of all PDFs (`survey/headings.csv`, `survey/table_headers.csv`):

| Era (`documents.layout`) | Dates | Main features |
|---|---|---|
| **A** | 2016-08-01 → 2017-12-18 | Free-text front page ("RÉSUMÉ DE LA COTE"). Equity columns include average price, price limits low/high and compartment (1er/2ème). Sector indices appear only in the group headings. Fund pages rotated. |
| **B** | 2017-12-19 → 2022-12-30 | "BULLETIN OFFICIEL DE LA COTE" layout. Indicators on page 1. Sector groups. Third compartment (BRVM PC). |
| **C** | 2023-01-02 → 2024-12-31 | Sector-code column (`SPU`, `FIN`, `AGR`…). Compartments PRESTIGE / PRINCIPAL. Compartment indices (base 02/01/2023). |
| **D** | 2025-01-02 → | New sector classification (`TEL`, `CB`, `CD`, `ENE`…), with old and new sector index tables in 2025. From 2026: bond categories CLASSIQUES / GSS / FCTC / SUKUK / CONVERTIBLES and "Indice Total Return". |

In addition:
* 25 bulletins are **English editions** (e.g. 2016-11-02, 2025-01-02). Their header and label words, number formats and dates (`17 May 24`) are all supported, and yields printed as fractions (`0.07`) are converted to percent.
* English sector names are mapped to the French ones (`TRANSPORTATION` → `TRANSPORT`…).

## Database schema

All dates are ISO text (`YYYY-MM-DD`). Prices and amounts are in FCFA, and percentages in percent units (`-7.45` = −7.45 %). A NULL means the cell is empty, or `NC`/`ND`/`-` in the PDF.

### `equity_quotes` — PK (date, symbol)

| Column | Meaning |
|---|---|
| `name` | Company name as printed (wrapped lines joined) |
| `group_label` | Group heading the row sits under (raw), e.g. `COMPARTIMENT PRESTIGE`, `SECTEUR - FINANCES` |
| `sector_code` | 2023+ sector code (`TEL`, `FIN`, `SPU`, `AGR`…) |
| `sector` | Sector from the group heading (2016–2022) |
| `compartment` | PREMIER / SECOND / TROISIEME (until 2022) or PRESTIGE / PRINCIPAL (2023+) |
| `prev_close` | Previous close |
| `open`, `close` | Opening and closing price of the session (NULL if not traded: see `status_flag`) |
| `avg_price` | Average price (era A only) |
| `change_pct` | Day change % |
| `volume`, `value` | Shares traded, value traded (FCFA) |
| `ref_price` | Reference price (base of the next session) |
| `ytd_pct` | Change since the start of the year % |
| `limit_low`, `limit_high` | Daily price limits (era A only) |
| `div_amount`, `div_date` | Last net dividend paid and its payment date |
| `net_yield` | Net yield % (dividend / price) |
| `per` | Price/earnings ratio |
| `status_flag` | Comma list: `NC` (not traded), `SP` (suspended), `VALUE-EST` / `VALUE-REC` (see below) |
| `page` | Page of the PDF |

### `bond_quotes` — PK (date, symbol)

| Column | Meaning |
|---|---|
| `name` | Bond name, e.g. `ETAT DU MALI 6,20 % 2022-2029` |
| `section` | Bond category heading, e.g. `OBLIGATIONS D'ETAT`, `OBLIGATIONS SOUVERAINES`, `FCTC D'ENTREPRISES` |
| `issuer`, `coupon_rate`, `issue_year`, `maturity_year` | Parsed from the name (NULL when the name is truncated or has no rate, e.g. `TAUX DE BASE + SPREAD`) |
| `nominal` | Outstanding nominal value per bond (decreases with amortisation) |
| `prev_price`, `price`, `ref_price` | Previous price, day price (NULL if not traded), reference price |
| `open`, `avg_price`, `change_pct`, `limit_low`, `limit_high` | Era A only |
| `volume`, `value` | Bonds traded, value traded |
| `accrued_coupon` | Accrued interest ("coupon couru") |
| `periodicity` | A (annual), S (semi-annual), T (quarterly), M… |
| `coupon_amount` | Next net coupon amount |
| `next_coupon_date` | Next payment date. `next_coupon_raw` keeps the printed text (era A prints periods like `28 mars/ 28 sep.`) |
| `amort_type` | IF (in fine), AC (constant amortisation), ACD (constant, deferred), AD (degressive) |
| `status_flag` | As in `equity_quotes` |

### `right_quotes` — PK (date, symbol)

Same price and volume columns as equities, plus:
* `change_origin_pct`: change since listing;
* `parity`: exercise ratio, e.g. `1 pour 5`;
* `start_date`, `end_date`: trading period.

### `order_book` — PK (date, market, symbol)

| Column | Meaning |
|---|---|
| `market` | `equities` / `rights` / `bonds` |
| `bid_qty`, `bid_price` | Residual quantity and best price on the buy side at the close |
| `ask_price`, `ask_qty` | Best price and residual quantity on the sell side |
| `ref_price` | Reference price |

### `index_values` — PK (date, family, index_name)

| Column | Meaning |
|---|---|
| `family` | `headline` (BRVM COMPOSITE, BRVM 10 [until 2022], BRVM 30, BRVM PRESTIGE…); `compartment` (BRVM PRESTIGE/PRINCIPAL tables, and from 2026 BRVM COMPOSITE TOTAL RETURN); `sector` (old classification, base 14/06/1999: BRVM INDUSTRIE, FINANCES, SERVICES PUBLICS…, 2016 → 2025); `sector_new` (new classification, base 02/01/2025: BRVM TELECOMMUNICATIONS, SERVICES FINANCIERS…, 2025 →). The family is decided from the table's base date, so each series is continuous. |
| `value`, `change_pct`, `ytd_pct` | Level, day change %, change since 1 January % |
| `nb_companies`, `volume`, `value_traded`, `avg_per`, `base` | From the index tables (eras B–D). `base` is e.g. `14 Juin 1999` |

The same index can appear in two families (e.g. `BRVM PRESTIGE` as `headline` and as `compartment`). Filter on `family` to get one series.

### `market_stats` — PK (date, key)

Long table: `value` (number), `unit`, `raw` (printed text).

| Keys | Meaning |
|---|---|
| `equity_market_cap`, `bond_market_cap` | Capitalisation (FCFA). Era A prints billions, which are converted |
| `equity_volume`, `equity_value`, `bond_volume`, `bond_value` | Session totals |
| `equity_nb_traded`, `equity_nb_up`, `equity_nb_down`, `equity_nb_unchanged` (same with `bond_`) | Number of securities traded / rising / falling / unchanged |
| `*_change_pct` | Day change % of the figure above, when printed |
| `market_per`, `market_yield`, `market_return` | Market average PER, yield, return (%) |
| `nb_listed_companies`, `nb_bond_lines`, `nb_brokers` | Counts (brokers = participating SGIs) |
| `avg_volume_per_session_ytd`, `avg_value_per_session_ytd` | Year-to-date averages per session |
| `liquidity_ratio`, `satisfaction_ratio`, `trend_ratio`, `coverage_ratio`, `turnover_rate`, `risk_premium` | Market ratios (%). Definitions are on the BOC indicators page |

### `fund_navs` — PK (date, fund_name)

| Column | Meaning |
|---|---|
| `manager`, `depositary` | Management company and depositary (carried forward within their group) |
| `category` | A (actions), OCT, OMLT, OATC, D (diversified), C (contractual)… |
| `origin_value` | Value at inception |
| `nav_prev`, `nav_prev_date` | Previous NAV and its date |
| `nav`, `nav_date` | Current NAV and its date (NULL = `ND`, not available) |
| `inception_date` | Inception date (`inception_raw` keeps the printed text) |
| `perf_origin_pct`, `perf_period_pct` | Change since inception %, change since the previous NAV % |
| `frequency` | Quotidiennes / Hebdomadaires / Mensuelles |

NAVs are often published with a delay. Use `nav_date` / `nav_prev_date`, not the bulletin `date`, as the valuation date. If two funds share a name, the second is stored as `name [manager]`.

### `corporate_notices` — PK (date, kind, seq)

| Column | Meaning |
|---|---|
| `kind` | `operation` (opérations en cours), `avis` (BRVM notices, e.g. dividend payment), `communique` (company releases) |
| `company`, `reference`, `nature`, `subject` | Issuer, reference number (e.g. `20251030-2`), type, description |

### `meeting_mentions` — PK (date, company, meeting_date, nature) and the view `general_meetings`

Every bulletin repeats the list of shareholder meetings:
* `meeting_mentions` stores each listing (`time`, `place`) for each bulletin `date`. It is cleaned and reloaded with the bulletin, like the other dated tables.
* **`general_meetings`** is a view with one row per meeting: `company`, `meeting_date`, `nature`, `time`, `place`, `first_seen` / `last_seen` (first and last bulletin listing it) and `n_bulletins`.

Some 2025 bulletins embed a font without a usable character map, so the text comes out shifted (`$)5,&$ */2%$/` for `AFRICA GLOBAL`). Such company names are detected and skipped, with a warning in `extraction_log`. The readable listing of the same meeting from other bulletins is kept. Unreadable words are also removed from `nature`.

### Technical tables

* `documents`: one row per PDF.
  * `layout`, `locale`, `pages`, `status` (`ok` / `partial` / `error`), `n_warnings`;
  * `parser_version`, `file_size`, `file_mtime` (used for incremental runs).
* `extraction_log`: every warning and check result per bulletin, with `section` and `level` (`info` / `warning` / `error`).
* `table_totals`: TOTAL lines printed in the BOC.
  * `level`: `group` (e.g. COMPARTIMENT PRINCIPAL), `category` (e.g. TOTAL - OBLIGATIONS CLASSIQUES) or `grand` (TOTAL - Marché des actions/obligations);
  * `volume`, `value`.
* `securities`: rebuilt after each run from the latest quote of each symbol.
  * `asset_type`, `name`, `country` (equities, from the name suffix: CI, SN, BF, BJ, ML, NE, TG), `sector`, `compartment`;
  * bond terms; `first_date`, `last_date`.

## Quality control

For each bulletin (`pipeline.qc_checks`):
* **Checksums:** Σ volume and Σ value of the rows are compared with the printed grand total. The comparison allows for:
  * ±2 FCFA of rounding in BRVM's totals;
  * a printed total that BRVM itself clipped (e.g. `28 387 215` for `28 387 215 284`);
  * totals that include estimated values.
* **Price consistency:** close against prev × (1 + change). Differences are logged at `info` level; they are normal on ex-dividend days.
* **Clipped values:** some traded values are too wide for their column and are clipped in the PDF itself (`15 000 000 0` for 15,000,000,000). Such values are replaced:
  * by volume × price, flagged `VALUE-EST`;
  * exactly, as printed total − other rows, when only one value of the table is affected, flagged `VALUE-REC`.

  25 values are flagged, out of about 370,000 quote rows.
* **Duplicates:** a symbol listed twice in a table (some 2026 FCTC/SUKUK lines) is kept once, and the duplicate is logged.
* The **QC report** (`python extract_boc.py --qc` → [qc_report.md](qc_report.md)) shows:
  * status per era and rows per table and year;
  * checksum results and warning patterns;
  * bulletins not fully extracted, and coverage gaps.
* **Tests** (`python -m pytest tests`, 11 tests):
  * parsing rules for French/English numbers, dates and flags;
  * golden values from 2017-01-02 (era A), 2019-06-14 (B), 2023-04-03 (C), 2025-01-02 (English edition) and 2025-10-30 (D);
  * the bilingual file of 2017-12-20;
  * the rotated and 10×-scaled fund pages.

## Known limitations

* **Prices are not adjusted** for splits and reverse splits (there was a wave of splits in 2016–2018, and SONATEL split 1:10 on 2026-10-23). The notebook [brvm_database_showcase.ipynb](brvm_database_showcase.ipynb) (section 4) shows how to detect them and adjust: a jump of more than ±40 % in `ref_price` from one session to the next is impossible under BRVM's ±7.5 % daily limit. Around a split the bulletin can be inconsistent for a few days (e.g. `prev_close` still at the old price), so use `ref_price`.
* **Typos in the bulletins are kept as printed.** For example, the bond capitalisation of 2024-11-11 (`10,503,545,90,495`) and 2025-01-16 (billions instead of trillions), or a few misprinted fund NAVs. Filter outliers in analyses (`drop_spikes()` in the notebook).
* **Funds:** the fund page exists from October 2016. 78 bulletins have no fund data (mostly before October 2016).
* **Notices:** in era A they are free text ("Informations : opérations en cours"). Only the tables from 2017-12 onwards are extracted.
* **Rights:** the rights market is often empty (179 rows in total).
* **Names:** values printed under a non-standard heading in a bond name (e.g. truncated `2023-2` instead of `2023-2030`) give `maturity_year` NULL.
* **Headline index:** missing on 2021-08-16 (unusual front page). Use `index_values` with family `compartment`/`sector`, or the previous day.
* **Fund names:** they change spelling over time (`FCP "BRM DYNAMIQUE"` vs `FCP BRM DYNAMIQUE`). Quotes are removed, but no further harmonisation is done.
* **Missing bulletins:** dates whose PDF is missing from the site (see [SITE_NOTES.md](SITE_NOTES.md#known-gaps)) have no data at all.

## Example queries

```sql
-- SONATEL daily close and volume
SELECT date, close, ref_price, volume, value FROM equity_quotes WHERE symbol = 'SNTS' ORDER BY date;

-- Last price of every stock (close if traded, else reference price)
SELECT q.symbol, s.name, q.date, COALESCE(q.close, q.ref_price) AS price, q.per, q.net_yield
FROM equity_quotes q JOIN securities s USING (symbol)
WHERE q.date = (SELECT MAX(date) FROM equity_quotes);

-- BRVM Composite history
SELECT date, value, change_pct, ytd_pct FROM index_values
WHERE family = 'headline' AND index_name = 'BRVM COMPOSITE' ORDER BY date;

-- Government bonds of one issuer with their accrued coupon on a date
SELECT symbol, name, coupon_rate, maturity_year, nominal, ref_price, accrued_coupon, next_coupon_date
FROM bond_quotes WHERE date = '2025-10-30' AND issuer LIKE 'ETAT DU SENEGAL%' ORDER BY maturity_year;

-- Market breadth over time
SELECT date,
       MAX(CASE WHEN key = 'equity_nb_up'   THEN value END) AS up,
       MAX(CASE WHEN key = 'equity_nb_down' THEN value END) AS down
FROM market_stats GROUP BY date ORDER BY date;

-- NAV series of one fund (valuation date, not bulletin date)
SELECT DISTINCT nav_date, nav FROM fund_navs WHERE fund_name = 'FCP AAM OBLIGATIS' AND nav IS NOT NULL ORDER BY nav_date;

-- Dividend history per stock (each change of the 'last dividend' columns)
SELECT symbol, div_date, MAX(div_amount) FROM equity_quotes WHERE div_date IS NOT NULL GROUP BY symbol, div_date;
```

From Python / pandas:

```python
import sqlite3, pandas as pd
con = sqlite3.connect("brvm.db")
px = pd.read_sql("SELECT date, symbol, close, ref_price FROM equity_quotes", con, parse_dates=["date"])
prices = px.pivot(index="date", columns="symbol", values="ref_price")
```

## Maintenance: when BRVM changes its layout

1. Run `python extract_boc.py` and then `--qc`. A new layout shows up as:
   * `partial` documents;
   * `header anchors not found` warnings;
   * checksum failures.
2. Run `python survey_layouts.py` and look in `survey/table_headers.csv` / `survey/headings.csv` for the new header words or section names.
3. Usually only regexes need updating:
   * column header words in `parsers/quotes.py` (`EQ_NEW`, `BOND_NEW`, `BOOK`…);
   * group headings or stop words in `columns.TableSpec`;
   * stat labels in `parsers/market.STAT_KEYS`.
4. Add a golden test for the new layout in `tests/test_golden.py`, bump `PARSER_VERSION` in `brvm_extract/__init__.py`, and run `python extract_boc.py`. All PDFs are then re-extracted with the new parser.
