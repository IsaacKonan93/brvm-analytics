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
