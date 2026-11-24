"""Web app: data-layer values, translations, and every page rendered in French and English."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "webapp"), str(ROOT)]
DB = ROOT / "brvm.db"
pytestmark = pytest.mark.skipif(not DB.exists(), reason="brvm.db not built")


def test_translations_complete():
    from app_lib.i18n import LABELS
    assert all(len(v) == 2 and v[0] and v[1] for v in LABELS.values())


def test_number_formats():
    import streamlit as st
    from app_lib import i18n
    st.session_state.lang = "fr"
    assert i18n.fmt_num(1234.5, 1) == "1 234,5"
    assert i18n.fmt_pct(-0.21) == "-0,21 %"
    assert i18n.fmt_amount(13_276_985_405_819) == "13 277 Mds"
    st.session_state.lang = "en"
    assert i18n.fmt_num(1234.5, 1) == "1,234.5"
    assert i18n.fmt_amount(13_276_985_405_819) == "13.28 tn"


def test_data_layer_values():
    from app_lib import data
    v = data.as_of()
    h = data.stock_history(v, "SNTS")
    assert h.loc["2026-10-22", "adj_ref_price"] == 4200          # split-adjusted (42 000 printed, 1:10)
    hl = data.headline(v, "2025-10-30").set_index("index_name")
    assert hl.loc["BRVM COMPOSITE", "value"] == 344.36
    assert data.stats_on(v, "2025-10-30")["equity_market_cap"] == 13276985405819
    rk = data.fund_ranking(v)
    assert len(rk) > 50 and rk["perf_1y"].notna().sum() > 20


def test_bulletin_links():
    from app_lib import data
    v = data.as_of()
    b = data.bulletins(v).set_index("date")
    assert b.loc["2026-11-23", "url"] == "https://www.brvm.org/sites/default/files/boc_20261123_2.pdf"  # suffix: not guessable
    assert b.loc["2018-12-06", "status"] == "unavailable"            # broken link on brvm.org
    assert b.loc["2025-12-25", "status"] == "none"                   # Christmas
    published = b[b["status"] == "published"]
    assert len(published) >= 2529 and published["url"].notna().all()
    assert data.boc_url(v, "2025-10-30").endswith("boc_20251030_2.pdf")
    assert data.boc_url(v, "2025-12-25") is None


def test_briefing_parsing():
    import datetime as dt
    import streamlit as st
    from app_lib import briefing
    st.session_state.lang = "fr"
    assert briefing.event_date("Paiement de dividendes de 92 F CFA net par action, le 27/10/2026") == dt.date(2026, 10, 27)
    assert briefing.event_date("SOCIAL BOND AFINHAB 6,00 % 2026-2041 - Première cotation le 1er décembre 2026") == dt.date(2026, 12, 1)
    assert briefing.event_date("Avis sans date") is None
    assert briefing.describe_operation("Paiement de dividendes de 92 F CFA net par action, le 27/10/2026") ==         ("dividend", "Paiement de dividende : 92 FCFA net par action")
    assert briefing.describe_operation("Fractionnement des actions à raison de dix (10) actions nouvelles pour une (1) "
                                       "action ancienne le 26/10/2026")[0] == "split"
    st.session_state.lang = "en"
    assert briefing.describe_operation("Première cotation - TPCI 6 % 2026-2031 (TPCI.O1) - Première cotation le 2 mars 2026") ==         ("listing", "First listing: TPCI 6 % 2026-2031 (TPCI.O1)")


def test_briefing_values():
    import streamlit as st
    from app_lib import briefing, data
    v = data.as_of()
    st.session_state.lang = "fr"
    text = briefing.summary(v, "2026-10-20")
    assert "a reculé de 0,94 % à 524,52 points" in text and "SONATEL SN en représente 77 %" in text
    ev = briefing.notable(v, "2026-10-20")
    assert "ONATEL BF" in set(ev["highs"]["name"]) and "SONATEL SN" in set(ev["volume"]["name"])
    up = briefing.upcoming(v, "2026-10-20")
    assert {("TRACTAFRIC CI", "dividend"), ("SONATEL", "split")} <= set(zip(up["company"], up["kind"]))
    assert not up["company"].str.contains(r"[$%]").any()
    assert data.breadth(v, "2017-02-08") == (13, 13, 7)               # no statistics in 2017 bulletins: counted
    assert data.equity_value(v, "2026-11-23") == 1434490920


def test_total_return_index():
    import pandas as pd
    from app_lib.data import total_return_index
    idx = pd.to_datetime(["2025-05-16", "2025-05-19", "2025-05-20"])
    price = pd.Series([100.0, 95.0, 99.75], index=idx)          # ex-dividend on the 19th: -5 = the dividend
    divs = pd.Series([5.0], index=pd.to_datetime(["2025-05-19"]))
    tr = total_return_index(price, divs)
    assert list(tr.round(6)) == [100.0, 100.0, 105.0]           # flat on the ex-day, then +5 % on 100
    assert total_return_index(price, divs.iloc[:0]).equals(price)


def test_dividend_events_and_total_return():
    from app_lib import data
    v = data.as_of()
    ev = data.dividend_events(v)
    snts = ev[ev["symbol"] == "SNTS"].set_index("div_date")
    assert snts.loc["2025-05-22", "ex_date"].strftime("%Y-%m-%d") == "2025-05-19"   # flagged "(d)" session
    assert snts.loc["2025-05-22", "adj_div_amount"] == 165.5                       # 1 655 printed, 1:10 split
    assert len(ev) >= 320
    h = data.stock_history(v, "SNTS")
    assert abs(h.loc["2025-05-19", "tr_price"] / h.loc["2025-05-16", "tr_price"] - 1) < 1e-9  # dividend offsets the drop
    a, b = h.loc["2016-08-01"], h.iloc[-1]
    price_ret, total_ret = b["adj_ref_price"] / a["adj_ref_price"], b["tr_price"] / a["tr_price"]
    assert total_ret > price_ret * 1.8                          # ten years of ~8 % yields
    m = data.price_matrix(v, ("SNTS", "ORAC"), "2025-11-21", "tr")
    assert m.index.min().strftime("%Y-%m-%d") >= "2025-11-21" and m.notna().all().all()


def test_stock_page_data():
    from app_lib import data
    v = data.as_of()
    h = data.stock_history(v, "SNTS")
    s = data.dividend_stats(data.dividend_history(v, "SNTS"), h["adj_ref_price"].iloc[-1], v)
    assert round(s["ttm_yield"], 2) == h["net_yield"].iloc[-1]   # same as BRVM's yield when paid within a year
    assert s["by_year"][2026] == 174.0 and s["years_paid"] == 10
    sg = data.dividend_stats(data.dividend_history(v, "SGBC"), None, v)["by_year"]
    assert sg[2019] == 206.0                                    # the 2019-2021 cut, as printed and seen in prices
    lt = data.liquidity_table(v, 91)
    assert lt.loc["SNTS", "rank"] == 1 and len(lt) == 48
    val, sector, n = data.valuation_history(v, "SGBC")
    assert sector == "FIN" and n == 17 and val["per"].max() <= data.PER_MAX


def test_performance_table():
    from app_lib import data
    v = data.as_of()
    pr = data.performance_table(v, "price").set_index("symbol")
    brvm = data.equities_on(v, v).set_index("symbol")["ytd_pct"]
    both = pr["YTD"].round(2).to_frame().join(brvm).dropna()
    assert len(both) >= 45 and (both["YTD"] - both["ytd_pct"]).abs().max() < 0.01   # = BRVM's printed YTD
    tr = data.performance_table(v, "tr").set_index("symbol")
    assert tr.loc["SNTS", "5Y"] > pr.loc["SNTS", "5Y"] > 0
    assert abs((1 + tr.loc["SNTS", "5Y"] / 100) ** (1 / 5) - 1 - tr.loc["SNTS", "5Y_ann"] / 100) < 1e-9


def test_simulator():
    import pandas as pd
    import sys
    sys.path.insert(0, str(ROOT / "webapp"))
    from views.compare import simulate
    idx = pd.to_datetime(["2024-01-02", "2024-05-02", "2024-05-03", "2025-01-02"])
    h = pd.DataFrame({"adj_ref_price": [100.0, 110.0, 105.0, 120.0]}, index=idx)
    from app_lib.data import total_return_index
    divs = pd.DataFrame({"ex_date": pd.to_datetime(["2024-05-03"]), "adj_div_amount": [5.0]})
    h["tr_price"] = total_return_index(h["adj_ref_price"], divs.set_index("ex_date")["adj_div_amount"])
    composite = pd.Series([200.0, 210.0, 205.0, 220.0], index=idx)
    sim = simulate(h, divs, composite, 1000.0, pd.Timestamp("2024-01-01"))
    end = sim.iloc[-1]
    assert end["price"] == 1200.0                       # 10 shares x 120
    assert end["cash"] == 1250.0                        # + 10 shares x 5 FCFA dividend
    assert round(end["reinvested"], 6) == round(1000 * (110 / 100) * (110 / 110) * (120 / 105), 6)
    assert end["index"] == 1100.0 and end["dividends"] == 50.0


def test_market_structure():
    from app_lib import data
    v = data.as_of()
    if data.shares_latest(v).empty:
        pytest.skip("no share counts yet: run fetch_shares.py")
    ms = data.market_structure(v, v).set_index("symbol")
    brvm = data.stats_on(v, v)["equity_market_cap"]
    assert abs(ms["cap"].sum() / brvm - 1) < 0.005          # rebuilt total = BRVM's published capitalisation
    assert ms.loc["SNTS", "shares"] == 1e9 and ms["weight"].idxmax() == "SNTS"
    assert abs(ms["weight"].sum() - 100) < 1e-9
    ch = data.concentration_history(v)
    assert ch.index.min() >= pd.Timestamp(data.STRUCTURE_SINCE) and ch["gap_pct"].abs().max() < 5


def test_bond_issuers_and_categories():
    from app_lib.data import bond_category, bond_issuer
    assert bond_category("OBLIGATIONS SOUVERAINES") == "SOV" == bond_category("GOVERNMENT BONDS")
    assert bond_category("OBLIGATIONS GSS D·ENTREPRISES") == "GSS"
    assert bond_category("FCTC D'INSTITUTIONS FINANCIERES REGIONALES ET INTERNATIONALES") == "FCTC"
    assert bond_category("OBLIGATIONS D'INSTITUTIONS FINANCIERES REGIONALES ET INTERNATIONALES") == "FIN"
    assert bond_category("OBLIGATIONS CONVERTIBLES EN ACTIONS") == "CONV"
    assert bond_issuer("TPNE", "SOV") == bond_issuer("TRESOR PUBLIC DU NIGER", "SOV") == ("STATE:NE", "NE")
    assert bond_issuer("TPCI (TAUX DE BASE + SPREAD) %", "SOV") == ("STATE:CI", "CI")
    assert bond_issuer("ETAT DU BURKINA DIASPORA BONDS", "SOV") == ("STATE:BF", "BF")
    assert bond_issuer("SOCIAL BOND CRRH-UEMOA", "GSS") == ("CRRH-UEMOA", None)
    assert bond_issuer("BIDC-EBID GSS BOND", "GSS") == ("BIDC-EBID", None)
    assert bond_issuer("FCTC SONATEL C-1", "FCTC") == ("FCTC SONATEL C-1", None)   # not the state of Senegal
    import streamlit as st
    from views.bonds import issuer_label
    st.session_state.lang = "fr"
    assert issuer_label("STATE:NE", "NE") == "État : Niger"
    assert issuer_label("CRRH-UEMOA", float("nan")) == "CRRH-UEMOA"          # NaN country in a DataFrame


def test_fund_fixes():
    from app_lib import data
    v = data.as_of()
    nav = data.fund_navs(v)
    assert nav["nav_date"].max() <= pd.Timestamp(v)                 # 5025-12-05 misprints left out
    rk = data.fund_ranking(v).set_index("fund_name")
    assert rk["category"].dropna().isin(["A", "D", "OMLT", "OCT", "OATC", "M", "O", "R", "C"]).all()
    assert pd.notna(rk.loc["SICAV Abdou DIOUF", "nav_break"]) and pd.isna(rk.loc["SICAV Abdou DIOUF", "perf_1y"])
    assert rk["perf_1y"].min() > -50


@pytest.mark.parametrize("page", ["stock", "compare"])
def test_pages_render_price_basis(page):
    from streamlit.testing.v1 import AppTest

    def script(page, paths):
        import importlib
        import sys
        sys.path[:0] = paths
        import streamlit as st
        st.session_state.lang = "en"
        st.session_state.basis = "price"
        importlib.import_module(f"views.{page}").render()

    at = AppTest.from_function(script, args=(page, [str(ROOT / "webapp"), str(ROOT)]), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Price-only" in c.value for c in at.caption)


@pytest.mark.parametrize("page", ["overview", "structure", "stock", "compare", "bonds", "funds", "bulletins"])
@pytest.mark.parametrize("lang", ["fr", "en"])
def test_pages_render(page, lang):
    from streamlit.testing.v1 import AppTest

    def script(page, lang, paths):
        import importlib
        import sys
        sys.path[:0] = paths
        import streamlit as st
        st.session_state.lang = lang
        importlib.import_module(f"views.{page}").render()

    at = AppTest.from_function(script, args=(page, lang, [str(ROOT / "webapp"), str(ROOT)]), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    from app_lib.i18n import LABELS
    assert at.title[0].value == LABELS[f"page_{page}"][0 if lang == "fr" else 1]


def test_full_app_and_language_switch():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "webapp" / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception
    assert at.title[0].value == "Vue du marché"
    at.sidebar.radio[0].set_value("en").run()
    assert not at.exception and at.title[0].value == "Market overview"
