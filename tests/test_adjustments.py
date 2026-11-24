"""Corporate actions and split-adjusted prices (brvm_extract.adjustments)."""

import sqlite3
from pathlib import Path

import pytest

from brvm_extract.adjustments import _same_company, detect, factors, label, snap_ratio

DB = Path(__file__).resolve().parent.parent / "brvm.db"


def test_snap_ratio():
    assert snap_ratio(0.0474) == 1 / 20        # 1:20 split with a -5 % move the same day
    assert snap_ratio(0.104405) == 1 / 10      # SONATEL 2026
    assert snap_ratio(1.91) == 2.0             # 2:1 reverse split
    assert snap_ratio(0.0578) == 1 / 17        # no standard ratio within 8 %: nearest whole number
    assert snap_ratio(0.43) == 0.43            # nothing close: kept as observed
    assert label(0.1) == "1:10" and label(2.0) == "2:1" and label(1 / 64) == "1:64"


def test_detect_split_and_misprint():
    prices = [100, 101, 100, 25, 100, 102, 10.3, 10.4, 10.2]  # misprint on day 3, 1:10 split on day 6
    rows = [(f"2025-01-{i + 1:02d}", p) for i, p in enumerate(prices)]
    actions, anomalies = detect(rows)
    assert [(a["date"], a["ratio"]) for a in actions] == [("2025-01-07", 0.1)]
    assert [a["date"] for a in anomalies] == ["2025-01-04"]


def test_factors():
    acts = [{"date": "2020-01-10", "ratio": 0.5}, {"date": "2024-06-01", "ratio": 0.1}]
    assert factors(acts) == [("0000-01-01", "2020-01-10", 0.05), ("2020-01-10", "2024-06-01", 0.1),
                             ("2024-06-01", "9999-12-31", 1.0)]


def test_company_matching():
    assert _same_company("BOA - MALI", "BOAM", "BANK OF AFRICA ML")
    assert not _same_company("BOA - MALI", "BOAC", "BANK OF AFRICA CI")
    assert _same_company("SIB", "SIBC", "SOCIETE IVOIRIENNE DE BANQUE")
    assert _same_company("ECOBANK CI", "ECOC", "ECOBANK COTE D'IVOIRE")
    assert not _same_company("SODECI", "SIVC", "AIR LIQUIDE CI")


@pytest.mark.skipif(not DB.exists(), reason="brvm.db not built")
def test_database_adjusted_view():
    con = sqlite3.connect(DB)
    ca = dict(((s, d), (lab, src)) for s, d, lab, src in
              con.execute("SELECT symbol, date, label, source FROM corporate_actions"))
    assert ca[("SNTS", "2026-10-23")] == ("1:10", "notice")
    assert ca[("PRSC", "2019-10-24")] == ("1:64", "notice")   # official ratio, not the rounded 1:60
    # SONATEL the day before its split: 42 000 printed -> 4 200 adjusted, volume x10
    ref, adj, vol, adj_vol = con.execute(
        """SELECT ref_price, adj_ref_price, volume, adj_volume FROM equity_quotes_adjusted
           WHERE symbol = 'SNTS' AND date = '2026-10-22'""").fetchone()
    assert (ref, adj, adj_vol) == (42000, 4200, vol * 10)
    # misprinted session: no adjusted price
    assert con.execute("""SELECT price_anomaly, adj_ref_price FROM equity_quotes_adjusted
                          WHERE symbol = 'STBC' AND date = '2018-07-12'""").fetchone() == (1, None)


def test_dividend_detection_rules():
    from brvm_extract.dividends import detect
    # (date, adj_ref_price, adj_prev_close, div_amount, adj_div_amount, div_date, status_flag)
    rows = [
        ("2024-05-02", 1000, 1000, 50, 50, "2023-05-10", None),
        ("2024-05-03", 960, 1000, 60, 60, "2024-05-07", "EX-DIV"),       # 1. flagged ex-dividend session
        ("2024-05-06", 970, 960, 60, 60, "2024-05-07", None),
        ("2024-05-07", 975, 970, 3, 3, "2024-05-07", None),               # restated after a split: ignored
        ("2024-05-08", 980, 975, 3, 3, "2024-05-07", None),
        ("2024-05-09", 985, 980, 3, 3, "2025-05-09", None),               # misprinted date, seen once: ignored
        ("2024-05-10", 990, 985, 3, 3, "2024-05-07", None),
        ("2025-05-05", 1100, 1100, 3, 3, "2024-05-07", None),
        ("2025-05-06", 1030, 1100, 3, 3, "2024-05-07", None),             # 2. drop of 70 ~ the 72 dividend
        ("2025-05-07", 1040, 1030, 3, 3, "2024-05-07", None),
        ("2025-05-20", 1050, 1040, 72, 72, "2025-05-12", None),           # shown only after the payment
        ("2025-05-21", 1050, 1050, 72, 72, "2025-05-12", None),
        ("2025-05-22", 1050, 1050, 72, 72, "2025-05-12", None),
    ]
    ev = detect(rows)
    assert [(e["ex_date"], e["div_date"], e["div_amount"], e["method"]) for e in ev] == [
        ("2024-05-03", "2024-05-07", 60, "flag"), ("2025-05-06", "2025-05-12", 72, "price_drop")]
