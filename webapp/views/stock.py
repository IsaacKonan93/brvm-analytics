"""Stock explorer: price (total return by default), then tabs for dividends, liquidity, valuation and events.

Rebuilt in step 4 of WEBAPP_ROADMAP.md. The data functions are in app_lib/data.py
(dividend_history, dividend_stats, liquidity_table, spreads, valuation_history).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import briefing, charts, data
from app_lib.i18n import COUNTRIES, SECTOR_CODES, fmt_amount, fmt_date, fmt_num, fmt_pct, name_of, t
from views.common import boc_md, chart, table, with_boc

LIQ_WINDOWS = {"3M": 91, "1Y": 365, "3Y": 3 * 365}


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


# ---------------------------------------------------------------- tabs

def _dividends_tab(v: str, sym: str, name: str, price: float | None):
    divs = data.dividend_history(v, sym)
    # announced and not yet paid (from the bulletins' operation notices, see app_lib/briefing.py)
    up = briefing.upcoming(v, v)
    if len(up):
        mine = up[up["kind"].isin(["dividend", "split"]) & up["company"].map(
            lambda c: bool(data._matching_companies([c], sym, name)))]
        for r in mine.itertuples():
            st.info(t("div_announced", label=r.label, date=fmt_date(r.date)))
    if divs.empty:
        st.info(t("no_dividend"))
        return
    s = data.dividend_stats(divs, price, v)
    k = st.columns(3)
    k[0].metric(t("ttm_yield"), fmt_pct(s["ttm_yield"], 2, signed=False), border=True)
    k[1].metric(t("div_cagr"), fmt_pct(s["cagr_5y"], 1), border=True)
    k[2].metric(t("years_paid"), str(s["years_paid"]), border=True)
    left, right = st.columns([2, 3])
    with left:
        by_year = s["by_year"]
        by_year.index = by_year.index.astype(str)
        chart(charts.bars(pd.DataFrame({t("dividends"): by_year}), t("div_per_year"), height=320))
    with right:
        hist = with_boc(divs.sort_values("ex_date", ascending=False), "ex_date")
        table(hist, {"ex_date": ("ex_date", "date"), "boc": ("boc", "link"), "div_date": ("pay_date", "date"),
                     "div_amount": ("div_printed", "num2"), "adj_div_amount": ("div_adj", "num2"),
                     "yield_ex": ("yield_ex", "pct")}, height=320, key="stock_divs")
    st.caption(t("div_note"))


def _liquidity_tab(v: str, sym: str):
    win = st.radio(t("period"), list(LIQ_WINDOWS), index=0, horizontal=True, format_func=t, key="liq_window")
    lt = data.liquidity_table(v, LIQ_WINDOWS[win])
    if sym in lt.index:
        r = lt.loc[sym]
        k = st.columns(4)
        k[0].metric(t("avg_value_day"), f"{fmt_amount(r['avg_value'])} FCFA", border=True)
        k[1].metric(t("traded_share"), fmt_pct(r["traded_pct"], 0, signed=False), border=True)
        k[2].metric(t("avg_volume_day"), fmt_num(r["avg_volume"]), border=True)
        k[3].metric(t("liq_rank"), t("liq_rank_first" if int(r["rank"]) == 1 else "liq_rank_val",
                                      rank=int(r["rank"]), n=len(lt)), border=True)
        st.caption(t("liq_note", n=len(lt)))
    else:
        st.info(t("not_listed"))

    left, right = st.columns(2)
    with left:
        mv = data.monthly_value_of(v, sym)
        mv = mv[mv.index > mv.index.max() - pd.DateOffset(months=36)] if len(mv) else mv
        if len(mv):
            chart(charts.bars(pd.DataFrame({t("value"): mv}), t("monthly_value_stock"), height=320))
    with right:
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
        sp = data.spreads(v, sym)
        if len(sp) >= 5:
            st.caption(t("avg_spread", pct=fmt_pct(sp["spread_pct"].mean(), 2, signed=False), n=len(sp)))
            chart(charts.lines({t("spread"): sp["spread_pct"]}, t("spread_hist"), height=240, hover_fmt=".2f",
                               end_labels=False))


def _valuation_tab(v: str, sym: str, name: str):
    val, sector, n = data.valuation_history(v, sym)
    if val.empty:
        st.info(t("no_data"))
        return
    sec_name = name_of(SECTOR_CODES, sector) if sector else "—"
    last = val.iloc[-1]  # last session, as in the tiles above (BRVM leaves P/E blank when not meaningful)
    k = st.columns(4)
    k[0].metric(t("per"), fmt_num(last["per"], 2), border=True)
    k[1].metric(t("sector_per_median"), fmt_num(last["sector_per"], 2), border=True)
    k[2].metric(t("yield"), fmt_pct(last["net_yield"], 2, signed=False), border=True)
    k[3].metric(t("sector_yield_median"), fmt_pct(last["sector_net_yield"], 2, signed=False), border=True)
    lbl_sector = t("sector_median", sector=sec_name, n=n)
    left, right = st.columns(2)
    with left:
        chart(charts.lines({name: val["per"], lbl_sector: val["sector_per"], t("market_median"): val["market_per"]},
                           t("per_hist"), height=380, buttons=True, hover_fmt=".1f"))
    with right:
        chart(charts.lines({name: val["net_yield"], lbl_sector: val["sector_net_yield"],
                            t("market_median"): val["market_net_yield"]},
                           t("yield_hist"), height=380, buttons=True, hover_fmt=".2f"))
    st.caption(t("val_note"))


def _events_tab(v: str, sym: str, name: str):
    st.subheader(t("splits"))
    sp = data.splits(v, sym)
    if len(sp):
        table(with_boc(sp), {"date": ("date", "date"), "boc": ("boc", "link"), "label": ("ratio", "text"),
                             "source": ("source", "text"), "evidence": ("evidence", "text")}, key="stock_splits")
    else:
        st.info(t("no_splits"))
    st.subheader(t("notices"))
    n = data.notices_for(v, sym, name)
    if len(n):
        n = n.assign(kind=n["kind"].map(lambda k: t(f"kind_{k}")))
        table(with_boc(n), {"date": ("date", "date"), "boc": ("boc", "link"), "kind": ("kind", "text"),
                            "reference": ("reference", "text"), "nature": ("nature", "text"),
                            "subject": ("subject", "text")}, height=360, key="stock_notices")
    else:
        st.info(t("no_data"))
    st.subheader(t("meetings"))
    m = data.meetings_for(v, sym, name)
    if len(m):
        table(m, {"meeting_date": ("date", "date"), "nature": ("nature", "text"), "time": ("time", "text"),
                  "place": ("place", "text")}, key="stock_meetings")
    else:
        st.info(t("no_data"))


# ---------------------------------------------------------------- page

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
    price = h["adj_ref_price"].dropna().iloc[-1] if h["adj_ref_price"].notna().any() else None
    divs = data.dividend_history(v, sym)

    st.caption(" · ".join(filter(None, [name_of(COUNTRIES, info["country"]), name_of(SECTOR_CODES, info["sector"]),
                                         str(info["compartment"] or ""),
                                         f"{t('session')} : {fmt_date(h.index[-1])}", boc_md(h.index[-1])])))
    perf = h[data.perf_column()]
    tr = data.basis() == "tr"
    k = st.columns(6)
    k[0].metric(t("last_price"), fmt_num(last["adj_ref_price"]), fmt_pct(last["change_pct"]), border=True)
    k[1].metric(t("ytd_tr" if tr else "ytd_pct"), fmt_pct(_ytd(perf) if tr else last["ytd_pct"]), border=True)
    k[2].metric(t("return_1y_tr" if tr else "return_1y"), fmt_pct(_return(perf, 365)), border=True)
    k[3].metric(t("per"), fmt_num(last["per"], 2), border=True)
    k[4].metric(t("yield"), fmt_pct(last["net_yield"], 2, signed=False), border=True)
    k[5].metric(t("last_div"), fmt_num(divs["div_amount"].iloc[-1], 2) if len(divs) else "—",
                fmt_date(divs["div_date"].iloc[-1]) if len(divs) else None, delta_color="off", border=True)

    prices = {t("tr_price"): h["tr_price"], t("adj_price"): h["adj_ref_price"]} if tr else h["adj_ref_price"]
    chart(charts.price_volume(prices, h["adj_volume"], t("adj_price"), t("volume_adj")))
    st.caption(t("basis_note_tr" if tr else "basis_note_price"))

    tabs = st.tabs([t("tab_dividends"), t("tab_liquidity"), t("tab_valuation"), t("tab_events")])
    with tabs[0]:
        _dividends_tab(v, sym, names[sym], price)
    with tabs[1]:
        _liquidity_tab(v, sym)
    with tabs[2]:
        _valuation_tab(v, sym, names[sym])
    with tabs[3]:
        _events_tab(v, sym, names[sym])
