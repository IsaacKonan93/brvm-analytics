# brvm.org: how BOC pages and files are laid out

Notes from probing <https://www.brvm.org> in November 2026, written while building [brvm_boc.py](brvm_boc.py). They explain why the script works the way it does. Update them if the site changes.

The site runs on **Drupal 7**. Each BOC is a node of type `bulletin-officiel`.

## Listing page: cannot be paged

`https://www.brvm.org/fr/bulletins-officiels-de-la-cote`

- It shows only the **~10 most recent** BOCs, plus a featured one (31 Dec 2025 at the time of writing).
- There is no visible pager. The Drupal Views settings mention `views_load_more` (view `bulletin`, displays `panel_pane_1` and `panel_pane_7`), but:
  - `?page=N` on the listing URL returns the same first page whatever `N` is;
  - `POST /fr/views/ajax` with `view_name=bulletin&view_display_id=panel_pane_1&page=N` also returns the first page.
- So **the archive cannot be crawled from the listing**. The script builds each date's page URL itself.

## Daily page URL (slug)

```
https://www.brvm.org/fr/bulletin-officiel-de-la-cote-du-{DAY}-{MONTH}-{YEAR}
```

| Part | Rule | Examples |
|---|---|---|
| `DAY` | Usually a 2-digit zero-padded day; **sometimes unpadded** (seen in 2021) | `03-novembre-2025`, `2-juin-2021` |
| `DAY` for the 1st | `1er` **or** `01`, depending on the period | `1er-decembre-2025` ✅, `01-fevrier-2017` ✅, `1-decembre-2025` ❌, `01-decembre-2025` ❌ |
| Optional suffix | `-0`, `-1`… added by Drupal when a slug already exists | `15-juin-2021-0` |
| `MONTH` | French, lowercase, **no accents** | `janvier fevrier mars avril mai juin juillet aout septembre octobre novembre decembre` |
| `YEAR` | 4 digits | `2025` |

Dates with no trading (weekends, holidays) return **404**.

### Site search

When the slug can't be guessed, the Drupal search finds the page:

```
https://www.brvm.org/fr/search/node/bulletin%20officiel%20cote%202%20juin%202021
  -> https://www.brvm.org/fr/bulletin-officiel-de-la-cote-du-2-juin-2021
```

The script uses it as its last fallback (`search_page_urls`). It recovered 25 BOCs on 2026-11-18.

## Page content

What matters in the daily page HTML:

```html
<div class="field field-name-field-date-boc ...">
  <span class="date-display-single" property="dc:date" content="2025-10-30T18:15:00+00:00">Jeudi, 30 octobre, 2025 - 18:15</span>
</div>
...
<div class="field field-name-field-fichier-boc ...">
  <a href="https://www.brvm.org/sites/default/files/boc_20251030_2.pdf" type="application/pdf; length=857994">boc_20251030_2.pdf</a>
</div>
```

- PDF link: CSS selector `div.field-name-field-fichier-boc a[href$=".pdf"]`
- BOC date: `span[property="dc:date"]`, attribute `content` (ISO 8601). The script compares it with the requested date and prints a warning if they differ.

## PDF filenames

All files are under `https://www.brvm.org/sites/default/files/`. The names are **not consistent**:

| Pattern | Example | Seen in |
|---|---|---|
| `boc_YYYYMMDD.pdf` | `boc_20200110.pdf`, `boc_20160801.pdf` | 2016–2020 |
| `boc_YYYYMMDD_0.pdf` | `boc_20161114_0.pdf`, `boc_20170110_0.pdf` | 2016–2017 |
| `boc_YYYYMMDD_2.pdf` | `boc_20251030_2.pdf`, `boc_20170213_2.pdf` | 2017 → today (the usual form now) |
| `boc_YYYYMMDD_2_0.pdf` | `boc_20261111_2_0.pdf` | re-uploads (Drupal adds `_0` to avoid overwriting a file) |
| long name | `bulletin_officiel_de_la_cote_du_07_nov_2016.pdf` | late 2016 |
| upload timestamp | `boc_20210602_02-06-2021_a_19.22.54.pdf`, `boc_20210702_a_18.49.22.pdf`, `boc_20211103_a_18h57.pdf`, `boc_20211008a_17.55.05.pdf` | May–Nov 2021 |
| typos | `boc_20210603-_20210603_...pdf`, `boc_202201044_2.pdf`, `boc_2024052_2.pdf`, `boc_20250510_2.pdf` (for 12 May 2025) | occasional |
| no date at all | `boc_fr.pdf` (2022-06-08), `boc_fr_2.pdf` (2023-05-26) | occasional |
| English edition | `boc_eng_20261002.pdf` | 2026-10-02 (only version online) |

The `_0`, `_1` suffixes are what Drupal adds when a file with the same name already exists. That is why **reading the link from the page is the reliable method**, and guessing filenames is only a fallback.

## Mismatches between pages and files

In a day-by-day scan of Nov 2016 to Feb 2017, the two sources often disagreed:

| Date | Page under standard slug | `boc_YYYYMMDD.pdf` | Actual file |
|---|---|---|---|
| 2016-11-07 | ✅ | ❌ | `bulletin_officiel_de_la_cote_du_07_nov_2016.pdf` |
| 2016-11-14 | ✅ | ❌ | `boc_20161114_0.pdf` |
| 2016-12-15 | ❌ | ✅ | `boc_20161215.pdf` (no page found) |
| 2016-12-19, 2016-12-22 | ❌ | ✅ | PDF only |
| 2017-01-20 → 01-27 | ✅ | ❌ | `boc_201701xx_0.pdf` |
| 2017-02-01 | `01` slug only | ✅ | `boc_20170201.pdf` |

This is why the script tries the page first and then falls back to guessing the filename.

## Pages that link the wrong file

Some daily pages link **another day's PDF**. The script now rejects a link whose filename carries a different date.

| Page date | Linked file | What it really is |
|---|---|---|
| 2017-04-17 (Easter Monday, no trading) | `boc_20170414.pdf` | Copy of 14 Apr 2017 |
| 2018-02-08 | `boc_20180207.pdf` | 7 Feb; the real 8 Feb file is `boc_20180208.pdf` (found by filename guess) |
| 2021-01-08 | `boc_20210107_0.pdf` | Re-upload of 7 Jan. No 8 Jan file exists |
| 2021-06-15 | `boc_20210614_14-06-2021_a_17.54.33.pdf` | 14 June, which has no page of its own; the real 15 June file was found by filename guess |
| 2022-11-01 (All Saints' Day, no trading) | `boc_20221102_2.pdf` | Copy of 2 Nov 2022 |

## Broken links

| Date | Page | Linked PDF |
|---|---|---|
| 2018-12-06 | ✅ | `boc_20181206.pdf` → **404** |
| 2018-12-07 | ✅ | `boc_20181207.pdf` → **404** |

No other filename was found for these two dates. They stay `failed` in the manifest, so every run retries them in case BRVM fixes the files.

## Page date field vs. BOC date

On 68 pages the `dc:date` field is **one day after** the BOC date (e.g. the 2016-10-05 page says `2016-10-06`). It looks like a publication timestamp rather than the trading date. In 64 of those cases the PDF filename matched the requested date, so the script trusts the URL and filename, not `dc:date`. The 4 others are in the table above.

## Server reliability

On 2026-11-18, brvm.org stopped accepting connections for a few minutes (connect timeouts, around the 7–16 Dec 2016 requests). The script retries 3 times with backoff. If a date still can't be reached, it is recorded as `failed`, never as `not_found`.

## Oldest available BOC

**Monday 1 August 2016** → `https://www.brvm.org/sites/default/files/boc_20160801.pdf`

How it was established:

1. Wednesdays from Jan 2010 to Nov 2016 were checked (page slug and `boc_YYYYMMDD{,_0,_2}.pdf`). Nothing was found before **August 2016**.
2. Every day from 1 June to 11 August 2016 was checked. The first hit was **2016-08-01**, followed by 08-02, 03, 04, 05, 09, 10, 11 (08-08 is missing).
3. Confirmed with `python brvm_boc.py oldest` on 2026-11-18.

BRVM began trading in 1998, but **bulletins older than August 2016 are not on the current website**, or at least not at any URL following these patterns.

## Known gaps

After the full download and retries (slug variants, filename guesses and site search):

- **23 Aug → 30 Sep 2016.** All 28 weekdays are missing (plus 8 and 15 Aug). This is a real gap on the website.
- **From 2017 onwards:** 10–16 missing weekdays a year, all consistent with market holidays. The full list is in `boc/manifest.csv` (`status = not_found`).
- **Untested ideas** if more need recovering:
  - the English pages (`/en/...`);
  - asking BRVM directly for the 2016 gap and the two broken 2018 files.

## Reproducing these checks

Quick status-code check from a shell:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -A "Mozilla/5.0" \
  "https://www.brvm.org/fr/bulletin-officiel-de-la-cote-du-30-octobre-2025"
```

Getting the PDF link from a page:

```bash
curl -sL -A "Mozilla/5.0" "https://www.brvm.org/fr/bulletin-officiel-de-la-cote-du-30-octobre-2025" \
  | grep -oE 'files/[^"]+\.pdf'
```
