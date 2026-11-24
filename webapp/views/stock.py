"""Stock explorer: adjusted price and volume, returns, valuation, dividends, splits, order book, notices."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import charts, data
from app_lib.i18n import COUNTRIES, SECTOR_CODES, fmt_amount, fmt_date, fmt_num, fmt_pct, name_of, t
from views.common import boc_md, chart, table, with_boc


def _return(series: pd.Series, days: int) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    past = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
    return (s.iloc[-1] / past.iloc[-1] - 1) * 100 if len(past) else None


def _ytd(series: pd.Series) -> float | None:
    """Change since the last session of the previous year."""
    s = series.dropna()
    if s.empty:
        return None
    before = s[s.index.year < s.index[-1].year]
    return (s.iloc[-1] / before.iloc[-1] - 1) * 100 if len(before) else None


def render():
    v = data.as_of()
    st.title(t("page_stock"))
    stocks = data.stocks(v)
    stocks = pd.concat([stocks[stocks["last_date"] == pd.Timestamp(v)], stocks[stocks["last_date"] != pd.Timestamp(v)]])
    symbols = stocks["symbol"].tolist()
    names = dict(zip(stocks["symbol"], stocks["name"]))
    wanted = st.query_params.get("symbol", "SNTS")
    sym = st.selectbox(t("choose_stock"), symbols, index=symbols.index(wanted) if wanted in symbols else 0,
                       format_func=lambda s: f"{names[s]} ({s})", key="stock_symbol")
    st.query_params["symbol"] = sym
    info = stocks.set_index("symbol").loc[sym]
    h = data.stock_history(v, sym)
    if h.empty:
        st.info(t("no_data"))
        return
    last = h.iloc[-1]
    divs = data.dividends(v, sym)

    st.caption(" · ".join(filter(None, [name_of(COUNTRIES, info["country"]), str(info["compartment"] or ""),
                                         f"{t('session')} : {fmt_date(h.index[-1])}", boc_md(h.index[-1])])))
    k = st.columns(6)
    k[0].metric(t("last_price"), fmt_num(last["adj_ref_price"]), fmt_pct(last["change_pct"]), border=True)
    perf = h[data.perf_column()]
    tr = data.basis() == "tr"
    k[1].metric(t("ytd_tr" if tr else "ytd_pct"), fmt_pct(_ytd(perf) if tr else last["ytd_pct"]), border=True)
    k[2].metric(t("return_1y_tr" if tr else "return_1y"), fmt_pct(_return(perf, 365)), border=True)
    k[3].metric(t("per"), fmt_num(last["per"], 2), border=True)
    k[4].metric(t("yield"), fmt_pct(last["net_yield"], 2, signed=False), border=True)
    k[5].metric(t("last_div"), fmt_num(divs["div"].iloc[-1], 2) if len(divs) else "—",
                fmt_date(divs["div_date"].iloc[-1]) if len(divs) else None, delta_color="off", border=True)

    prices = {t("tr_price"): h["tr_price"], t("adj_price"): h["adj_ref_price"]} if tr else h["adj_ref_price"]
    chart(charts.price_volume(prices, h["adj_volume"], t("adj_price"), t("volume_adj")))
    st.caption(t("basis_note_tr" if tr else "basis_note_price"))

    left, right = st.columns(2)
    with left:
        st.subheader(t("dividends"))
        if len(divs):
            by_year = divs.assign(year=divs["div_date"].dt.year.astype(str)).groupby("year")["adj_div"].sum()
            chart(charts.bars(pd.DataFrame({t("dividends"): by_year}), height=300))
        else:
            st.info(t("no_data"))
    with right:
        st.subheader(t("splits"))
        sp = data.splits(v, sym)
        if len(sp):
            table(with_boc(sp), {"date": ("date", "date"), "boc": ("boc", "link"), "label": ("ratio", "text"),
                                 "source": ("source", "text"), "evidence": ("evidence", "text")})
        else:
            st.info(t("no_splits"))
        st.subheader(t("order_book"))
        ob = data.order_book(v, sym)
        if len(ob):
            o = ob.iloc[0]
            spread = (o["ask_price"] - o["bid_price"]) / ((o["ask_price"] + o["bid_price"]) / 2) * 100 \
                if o["ask_price"] and o["bid_price"] else None
            c = st.columns(3)
            c[0].metric(t("bid"), fmt_num(o["bid_price"]), f"{t('bid_qty')} {fmt_num(o['bid_qty'])}",
                        delta_color="off")
            c[1].metric(t("ask"), fmt_num(o["ask_price"]), f"{t('ask_qty')} {fmt_num(o['ask_qty'])}",
                        delta_color="off")
            c[2].metric(t("spread"), fmt_pct(spread, 2, signed=False) if spread is not None else "—")
            st.caption(f"{fmt_date(o['date'])} · {boc_md(o['date'])}")
        else:
            st.info(t("no_data"))

    with st.expander(t("notices"), expanded=False):
        n = data.notices_for(v, sym, names[sym])
        if len(n):
            n = n.assign(kind=n["kind"].map(lambda k: t(f"kind_{k}")))
            table(with_boc(n), {"date": ("date", "date"), "boc": ("boc", "link"), "kind": ("kind", "text"), "reference": ("reference", "text"),
                      "nature": ("nature", "text"), "subject": ("subject", "text")})
        else:
            st.info(t("no_data"))
    with st.expander(t("meetings"), expanded=False):
        m = data.meetings_for(v, sym, names[sym])
        if len(m):
            table(m, {"meeting_date": ("date", "date"), "nature": ("nature", "text"), "time": ("time", "text"),
                      "place": ("place", "text")})
        else:
            st.info(t("no_data"))
