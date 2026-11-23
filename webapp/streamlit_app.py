"""BRVM web app (Streamlit). Run locally from the project folder:

    .\\.env\\Scripts\\streamlit run webapp/streamlit_app.py

See WEBAPP.md for the pages, the data source and the deployment on Streamlit Community Cloud.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]  # app modules + the brvm_extract package

import streamlit as st  # noqa: E402

from app_lib import data  # noqa: E402
from app_lib.i18n import LANGS, fmt_date, t  # noqa: E402
from views import bonds, compare, funds, overview, stock  # noqa: E402

st.set_page_config(page_title="BRVM", page_icon=":material/monitoring:", layout="wide")

# language: ?lang=fr|en in the URL, kept in the session
if "lang" not in st.session_state:
    q = st.query_params.get("lang")
    st.session_state.lang = q if q in LANGS else "fr"

with st.sidebar:
    st.radio(t("language"), list(LANGS), format_func=LANGS.get, horizontal=True, key="lang")
st.query_params["lang"] = st.session_state.lang

pages = [
    st.Page(overview.render, title=t("page_overview"), icon=":material/monitoring:", url_path="overview", default=True),
    st.Page(stock.render, title=t("page_stock"), icon=":material/query_stats:", url_path="stock"),
    st.Page(compare.render, title=t("page_compare"), icon=":material/compare_arrows:", url_path="compare"),
    st.Page(bonds.render, title=t("page_bonds"), icon=":material/account_balance:", url_path="bonds"),
    st.Page(funds.render, title=t("page_funds"), icon=":material/savings:", url_path="funds"),
]
page = st.navigation(pages)

try:
    v = data.as_of()
except Exception as e:  # no database reachable
    st.error(f"Database unavailable / base de données indisponible: {e}")
    st.stop()

with st.sidebar:
    st.caption(t("app_title"))
    st.markdown(f"**{t('data_as_of', date=fmt_date(v))}**")

page.run()

st.divider()
st.caption(t("footer"))
