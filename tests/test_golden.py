"""Golden tests: values read from real bulletins of each layout era (checked against the PDFs).

Skipped when the PDF is not present in boc/.
"""

import datetime as dt
from pathlib import Path

import pymupdf
import pytest

from brvm_extract.pdfdoc import load
from brvm_extract.parsers.events import parse_events
from brvm_extract.parsers.funds import parse_funds
from brvm_extract.parsers.market import parse_market
from brvm_extract.parsers.quotes import parse_bonds, parse_equities, parse_order_book

pymupdf.TOOLS.mupdf_display_errors(False)
BOC = Path(__file__).resolve().parent.parent / "boc"


def doc(date: str):
    f = BOC / f"boc_{date}.pdf"
    if not f.exists():
        pytest.skip(f"{f.name} not downloaded")
    return load(f), dt.date.fromisoformat(date)


def by_symbol(rows):
    return {r["symbol"]: r for r in rows}


def grand(totals, table="equities"):
    return next(t for t in totals if t["level"] == "grand" and t["table"] == table)


def test_2025_10_30_equities_and_bonds():
    d, date = doc("2025-10-30")
    eq, tot, _ = parse_equities(d, date)
    q = by_symbol(eq)
    assert len(eq) == 47
    s = q["SLBC"]
    assert (s["prev_close"], s["open"], s["close"], s["change_pct"], s["volume"], s["value"]) == \
        (19885, 21375, 21375, 7.49, 97, 2073375)
    assert q["SNTS"]["sector_code"] == "TEL" and q["SNTS"]["compartment"] == "PRESTIGE"
    assert q["SICC"]["volume"] is None and q["SICC"]["per"] == 109.12          # empty cells stay empty
    assert q["BNBC"]["per"] == 1806.93                                          # number split over 2 lines
    assert sum(r["volume"] or 0 for r in eq) == grand(tot)["volume"] == 788168
    bo, btot, _ = parse_bonds(d, date)
    b = by_symbol(bo)["EOM.O4"]
    assert (b["price"], b["volume"], b["value"], b["accrued_coupon"], b["periodicity"], b["coupon_amount"],
            b["next_coupon_date"], b["amort_type"]) == (4000, 14, 56000, 78.36, "A", 260.0, "2026-07-12", "AC")
    assert b["issuer"] == "ETAT DU MALI" and b["coupon_rate"] == 6.5 and b["maturity_year"] == 2027
    assert sum(r["volume"] or 0 for r in bo) == grand(btot, "bonds")["volume"] == 1124


def test_2025_10_30_order_book_market_funds_events():
    d, date = doc("2025-10-30")
    ob, _ = parse_order_book(d, date)
    c = next(r for r in ob if r["symbol"] == "CBIBF" and r["market"] == "equities")
    assert (c["bid_qty"], c["bid_price"], c["ask_price"], c["ask_qty"], c["ref_price"]) == (10, 9995, 10000, 2660, 9995)
    m = parse_market(d, date)
    idx = {(r["family"], r["index_name"]): r for r in m["index_values"]}
    comp = idx[("headline", "BRVM COMPOSITE")]
    assert (comp["value"], comp["change_pct"], comp["ytd_pct"]) == (344.36, 0.15, 24.76)
    tel = idx[("sector_new", "BRVM TELECOMMUNICATIONS")]
    assert (tel["nb_companies"], tel["value"], tel["volume"], tel["avg_per"]) == (3, 95.65, 10270, 9.84)
    stats = {r["key"]: r["value"] for r in m["market_stats"]}
    assert stats["equity_market_cap"] == 13276985405819 and stats["nb_bond_lines"] == 176
    f = {r["fund_name"]: r for r in parse_funds(d, date)["fund_navs"]}
    a = f["FCP AAM OBLIGATIS"]
    assert (a["manager"], a["category"], a["nav"], a["nav_date"], a["perf_origin_pct"]) == \
        ("AFRICABOURSE ASSET MANAGEMENT", "OATC", 9194.95, "2025-10-29", 83.9)
    ev = parse_events(d, date)
    assert any(n["reference"] == "20251030-2" and n["company"] == "SOGB" for n in ev["corporate_notices"])
    assert any(g["company"] == "SITAB" and g["meeting_date"] == "2025-07-30" for g in ev["meeting_mentions"])


def test_2017_01_02_old_layout():
    d, date = doc("2017-01-02")
    eq, tot, _ = parse_equities(d, date)
    s = by_symbol(eq)["SNTS"]
    assert (s["prev_close"], s["open"], s["close"], s["avg_price"], s["limit_low"], s["limit_high"],
            s["volume"], s["compartment"]) == (25000, 24000, 24495, 24001, 22660, 26330, 2390, "PREMIER")
    assert sum(r["volume"] or 0 for r in eq) == 105528
    bo, _, _ = parse_bonds(d, date)
    b = by_symbol(bo)["BHB.O1"]
    assert (b["nominal"], b["ref_price"], b["accrued_coupon"], b["coupon_amount"], b["next_coupon_date"]) == \
        (10000, 10000, 133.6, 587.5, "2017-10-11")


def test_2019_and_2023_layouts():
    d, date = doc("2019-06-14")
    eq, tot, _ = parse_equities(d, date)
    assert sum(r["volume"] or 0 for r in eq) == grand(tot)["volume"] == 49520
    assert by_symbol(eq)["SNTS"]["close"] == 16865
    d, date = doc("2023-04-03")
    eq, tot, _ = parse_equities(d, date)
    q = by_symbol(eq)
    assert q["SNTS"]["sector_code"] == "SPU" and q["SNTS"]["close"] == 15785
    assert q["ETIT"]["name"] == "ECOBANK TRANS. INCORP. TG"          # wrapped name
    assert len(eq) == 46


def test_english_edition_2025_01_02():
    d, date = doc("2025-01-02")
    assert d.locale == "en"
    eq, tot, _ = parse_equities(d, date)
    s = by_symbol(eq)["SNTS"]
    assert (s["close"], s["volume"], s["value"], s["div_date"]) == (24000, 559, 13335660, "2024-05-17")
    assert s["net_yield"] == 7.0                                         # printed as a fraction (0.07)
    assert sum(r["volume"] or 0 for r in eq) == 63375


def test_bilingual_file_keeps_first_bulletin():
    d, date = doc("2017-12-20")
    assert len(d.pages) == 10                     # pages 11-20 are the English bulletin of 2017-12-19
    eq, tot, _ = parse_equities(d, date)
    assert sum(r["volume"] or 0 for r in eq) == grand(tot)["volume"] == 373289


def test_rotated_and_scaled_fund_pages():
    d, date = doc("2017-10-16")                   # fund page with /Rotate 90
    f = {r["fund_name"]: r for r in parse_funds(d, date)["fund_navs"]}
    assert f["FCP AAM OBLIGATIS"]["nav"] == 6904.65
    d, date = doc("2020-11-16")                   # fund page drawn at 10x scale
    f = {r["fund_name"]: r for r in parse_funds(d, date)["fund_navs"]}
    assert f["FCP AAM CAPITAL SUR"]["nav_prev"] == 7268.25 and len(f) > 80
