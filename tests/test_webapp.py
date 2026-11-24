"""Web app: data-layer values, translations, and every page rendered in French and English."""

import sys
from pathlib import Path

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


@pytest.mark.parametrize("page", ["overview", "stock", "compare", "bonds", "funds", "bulletins"])
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
