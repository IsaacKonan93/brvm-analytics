# Extraction quality report

Generated 2026-11-23 12:08 from `brvm.db`.

## Documents

| Layout | ok | partial | error |
|---|---|---|---|
| A | 312 | 1 | 0 |
| B | 1249 | 0 | 0 |
| C | 496 | 0 | 0 |
| D | 470 | 0 | 0 |

2528 bulletins from 2016-08-01 to 2026-11-20.

## Rows per table and year

| Table | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| equity_quotes | 3009 | 10679 | 10935 | 11289 | 11546 | 11500 | 11442 | 11362 | 11458 | 11743 | 10429 |
| bond_quotes | 2941 | 9918 | 9883 | 12307 | 17135 | 22667 | 25381 | 30419 | 36259 | 41384 | 44075 |
| right_quotes | 0 | 0 | 0 | 39 | 0 | 22 | 0 | 0 | 90 | 0 | 28 |
| order_book | 4262 | 19587 | 20822 | 23610 | 28675 | 34061 | 36814 | 41709 | 47751 | 53042 | 54277 |
| index_values | 565 | 1941 | 2187 | 2223 | 2259 | 2248 | 2250 | 2958 | 2967 | 4731 | 2864 |
| market_stats | 220 | 1037 | 9686 | 10066 | 10265 | 10252 | 10314 | 10187 | 10268 | 10257 | 8838 |
| fund_navs | 2386 | 13328 | 16377 | 18606 | 21165 | 23275 | 24437 | 25106 | 26027 | 29032 | 25584 |
| corporate_notices | 0 | 34 | 1008 | 1108 | 1365 | 1449 | 1381 | 1128 | 1646 | 1584 | 1703 |

`general_meetings`: 514 distinct meetings; `securities`: 345 securities.

## Checksums (sum of rows vs TOTAL printed in the BOC)

* **equities**: 2524 bulletins with a printed grand total; volume matches in 2524, value matches (±2 FCFA) in 2524.
* **bonds**: 2257 bulletins with a printed grand total; volume matches in 2257, value matches (±2 FCFA) in 2252.
* 25 traded values were clipped in the PDF and estimated (VALUE-EST) or reconstructed (VALUE-REC).

## Warnings by pattern

| Count | Pattern | First date |
|---|---|---|
| 16 | events: meeting skipped, unreadable company name (font without character map): 'BOA - MALI' | 2017-12-19 |
| 16 | bonds: TPCI.ON: traded value 'N' unreadable/clipped in the PDF; estimated as volume x price = N | 2018-01-10 |
| 11 | events: meeting skipped, unreadable company name (font without character map): '$)N&$ */N%$/ /N*,N&N&,' | 2025-06-04 |
| 8 | events: meeting skipped, unreadable company name (font without character map): 'BERNABE - CI' | 2017-12-19 |
| 8 | events: meeting skipped, unreadable company name (font without character map): "BOA - COTE D'IVOIRE" | 2017-12-19 |
| 8 | events: meeting skipped, unreadable company name (font without character map): 'BOA - SENEGAL' | 2017-12-19 |
| 8 | events: meeting skipped, unreadable company name (font without character map): 'N$/(N(N*,(N$N(N* &,' | 2025-06-04 |
| 6 | events: meeting skipped, unreadable company name (font without character map): 'N$/(N(N*,(N$N(N* N' | 2025-06-12 |
| 5 | events: meeting skipped, unreadable company name (font without character map): '(N<N$&.$*,N* N(N&,' | 2025-03-28 |
| 5 | events: meeting skipped, unreadable company name (font without character map): "/N(N( N$N$/( 'N%(N" | 2025-06-13 |
| 4 | bonds: bonds: duplicate row for FNSBC.ON(page N) ignored | 2026-05-21 |
| 2 | rights: pNrights: header anchors not found: ['avg_price', 'change_origin_pct'] | 2016-11-02 |
| 2 | bonds: pNbonds: header anchors not found: ['avg_price'] | 2016-11-02 |
| 2 | bonds: SUKCI.SN: traded value 'N' unreadable/clipped in the PDF; estimated as volume x price = N | 2021-01-20 |
| 2 | events: meeting skipped, unreadable company name (font without character map): "(N&, ([ $,N/,N'( &," | 2025-12-10 |
| 2 | events: meeting skipped, unreadable company name (font without character map): "(N&, (([ $,N/,N'( &,)" | 2025-12-15 |
| 2 | bonds: bonds: duplicate row for SUKSN.SN(page N) ignored | 2026-03-13 |
| 2 | bonds: bonds: duplicate row for SUKTG.SN(page N) ignored | 2026-03-13 |
| 2 | bonds: bonds: duplicate row for FCAGS.ON(page N) ignored | 2026-05-21 |
| 2 | bonds: bonds: duplicate row for FNSBB.ON(page N) ignored | 2026-05-21 |
| 2 | bonds: bonds: duplicate row for FSNLC.ON(page N) ignored | 2026-05-21 |
| 2 | bonds: bonds: duplicate row for FSNTS.ON(page N) ignored | 2026-05-21 |
| 1 | qc: bonds: sum of value N!= printed total N(TOTAL-MARCHE DES OBLIGATIONS) | 2017-11-29 |
| 1 | equities: ONTBF: traded value 'N' unreadable/clipped in the PDF; estimated as volume x price = N | 2018-04-17 |
| 1 | equities: CBIBF: traded value 'N' unreadable/clipped in the PDF; estimated as volume x price = N | 2020-09-09 |
| 1 | market: no headline index found on the front page | 2021-08-16 |
| 1 | equities: ORGT: traded value 'N' unreadable/clipped in the PDF; estimated as volume x price = N | 2022-08-24 |
| 1 | bonds: FNSBC.ON: traded value 'N' unreadable/clipped in the PDF; estimated as volume x price = N | 2024-02-26 |
| 1 | bonds: TPBF.ON: traded value 'N' unreadable/clipped in the PDF; estimated as volume x price = N | 2025-03-21 |
| 1 | events: meeting skipped, unreadable company name (font without character map): '$)NI&$ G/N%$/ /NGINTI&N&I' | 2025-06-10 |
| 1 | events: meeting skipped, unreadable company name (font without character map): 'TNT$/ENENGIEN$NETING &I' | 2025-06-10 |
| 1 | events: meeting skipped, unreadable company name (font without character map): 'TNT$/ENENGIEN$NETING N' | 2025-06-10 |
| 1 | events: meeting skipped, unreadable company name (font without character map): '%,,& %N' | 2025-06-13 |
| 1 | events: meeting skipped, unreadable company name (font without character map): 'ENCI (Ex AIR LIQUIDE CI)' | 2025-12-09 |
| 1 | bonds: bonds: duplicate row for FCAS.ON(page N) ignored | 2026-05-21 |
| 1 | bonds: bonds: duplicate row for FORBC.ON(page N) ignored | 2026-05-21 |
| 1 | bonds: bonds: duplicate row for FORBT.ON(page N) ignored | 2026-05-21 |
| 1 | bonds: bonds: duplicate row for FSNBBF.ON(page N) ignored | 2026-05-21 |
| 1 | bonds: bonds: duplicate row for FTIMC.ON(page N) ignored | 2026-05-21 |
| 1 | events: meeting skipped, unreadable company name (font without character map): 'A)RICA G/OBA/ /OGINICNCI' | 2026-09-09 |

## Documents not fully extracted

* **2017-11-29** (partial): bonds: sum of value 32954408 != printed total 32954400 (TOTAL-MARCHE DES OBLIGATIONS)

## Coverage gaps

* Bulletins without equity quotes: 0 []
* Bulletins without fund NAVs: 78 (the fund page starts in October 2016)
* Bulletins without headline index: 1
