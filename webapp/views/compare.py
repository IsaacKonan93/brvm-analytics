"""Compare & screen: compare stocks, performance table, screener, investment simulator.

Performance and simulator added in step 5 of WEBAPP_ROADMAP.md. Returns follow the sidebar switch
(dividends reinvested by default, or price only), see data.basis().
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st

from app_lib import charts, data
from app_lib.i18n import COUNTRIES, SECTOR_CODES, fmt_amount, fmt_date, fmt_num, fmt_pct, name_of, t
from views.common import chart, csv_button, table

PERIODS = {"YTD": None, "1Y": 365, "3Y": 3 * 365, "5Y": 5 * 365, "ALL": None}


def _start(v: str, key: str) -> str | None:
    end = dt.date.fromisoformat(v)
    if key == "YTD":
        return dt.date(end.year, 1, 1).isoformat()
    if key == "ALL":
        return None
    return (end - dt.timedelta(days=PERIODS[key])).isoformat()


def _basis_note():
    st.caption(t("basis_note_tr" if data.basis() == "tr" else "basis_note_price"))


# ---------------------------------------------------------------- compare

def _compare(v: str):
    stocks = data.stocks(v)
    listed = stocks[stocks["last_date"] == pd.Timestamp(v)]
    names = dict(zip(stocks["symbol"], stocks["name"]))
    since = (dt.date.fromisoformat(v) - dt.timedelta(days=91)).isoformat()
    top = data.query("SELECT symbol, SUM(value) v FROM equity_quotes WHERE date > ? GROUP BY symbol ORDER BY v DESC LIMIT 4",
                     (since,), dates=())["symbol"].tolist()
    c1, c2 = st.columns([4, 1])
    with c1:
        syms = st.multiselect(t("choose_stocks"), listed["symbol"].tolist(), default=top, max_selections=8,
                              format_func=lambda s: f"{names[s]} ({s})", key="cmp_syms")
    with c2:
        per = st.selectbox(t("period"), list(PERIODS), index=1, format_func=t, key="cmp_period")
    if not syms:
        st.info(t("no_data"))
        return
    px = data.price_matrix(v, tuple(syms), _start(v, per), data.basis()).ffill()
    px = px.dropna(how="all")
    if px.empty:
        st.info(t("no_data"))
        return
    rebased = px / px.bfill().iloc[0] * 100
    chart(charts.lines({names[s]: rebased[s] for s in syms if s in rebased}, t("rebased"), height=440,
                       hover_fmt=",.1f"))
    _basis_note()

    rets = px.pct_change(fill_method=None)
    rows = []
    for s in syms:
        p = px[s].dropna()
        if len(p) < 2:
            continue
        r = rets[s].dropna()
        rows.append({"name": names[s], "total_return": (p.iloc[-1] / p.iloc[0] - 1) * 100,
                     "volatility": r.std() * np.sqrt(250) * 100, "max_dd": (p / p.cummax() - 1).min() * 100})
    stats = pd.DataFrame(rows)
    table(stats, {"name": ("name", "text"), "total_return": ("total_return", "pct"),
                  "volatility": ("volatility", "pct"), "max_dd": ("max_dd", "pct")})
    if len(syms) >= 2:
        corr = rets[syms].corr(min_periods=20).rename(index=names, columns=names)
        chart(charts.heatmap_corr(corr, t("correlation")))


# ---------------------------------------------------------------- performance table

def _filters(df: pd.DataFrame, prefix: str) -> pd.Series:
    """Sector and country filters shared by the performance table and the screener."""
    c = st.columns(2)
    sectors = c[0].multiselect(t("sector"), sorted(df["sector_name"].dropna().unique()), key=f"{prefix}_sector")
    countries = c[1].multiselect(t("country"), sorted(df["country_name"].dropna().unique()), key=f"{prefix}_country")
    m = pd.Series(True, index=df.index)
    if sectors:
        m &= df["sector_name"].isin(sectors)
    if countries:
        m &= df["country_name"].isin(countries)
    return m


def _performance(v: str):
    df = data.performance_table(v, data.basis()).copy()
    df["sector_name"] = df["sector_code"].map(lambda c: name_of(SECTOR_CODES, c))
    df["country_name"] = df["country"].map(lambda c: name_of(COUNTRIES, c))
    res = df[_filters(df, "perf")]
    h = st.radio(t("perf_chart_horizon"), list(data.HORIZONS), index=3, horizontal=True, format_func=t,
                 key="perf_horizon")
    ranked = res.dropna(subset=[h]).sort_values(h, ascending=False)
    if ranked.empty:
        st.info(t("no_data"))
        return
    chart(charts.hbars(ranked["name"], ranked[h], t("perf_chart", h=t(h)), diverging=True,
                       text=[fmt_pct(x, 1) for x in ranked[h]], height=max(320, 22 * len(ranked) + 90)))
    _basis_note()
    spec = {"symbol": ("symbol", "text"), "name": ("name", "text"), "sector_name": ("sector", "text"),
            "country_name": ("country", "text"), "ref_price": ("price", "num")}
    spec.update({hz: (f"perf_{hz}", "pct") for hz in data.HORIZONS})
    spec.update({"3Y_ann": ("perf_3Y_ann", "pct"), "5Y_ann": ("perf_5Y_ann", "pct")})
    out = res.sort_values(h, ascending=False)
    table(out, spec, height=560, key="perf_table")
    st.caption(t("perf_note"))
    csv_button(out[list(spec)].rename(columns={k: t(l) for k, (l, _) in spec.items()}),
               f"brvm_performance_{data.basis()}_{v}.csv", "perf_csv")


# ---------------------------------------------------------------- screener

def _screener(v: str):
    df = data.screener(v).copy()
    perf = data.performance_table(v, data.basis())[["symbol", "1Y"]]
    df = df.merge(perf, on="symbol", how="left")
    df["sector_name"] = df["sector_code"].map(lambda c: name_of(SECTOR_CODES, c))
    df["country_name"] = df["country"].map(lambda c: name_of(COUNTRIES, c))
    m = _filters(df, "scr")
    c = st.columns(4)
    comps = c[0].multiselect(t("compartment"), sorted(df["compartment"].dropna().unique()), key="scr_comp")
    per_lo, per_hi = c[1].slider(t("per_range"), 0.0, 60.0, (0.0, 60.0), step=0.5, key="scr_per")
    min_yield = c[2].number_input(t("min_yield"), 0.0, 30.0, 0.0, step=0.5, key="scr_yield")
    min_value = c[3].select_slider(t("min_value"), options=[0, 1e6, 5e6, 1e7, 5e7, 1e8],
                                   format_func=lambda x: f"{x:,.0f}", key="scr_value")
    if comps:
        m &= df["compartment"].isin(comps)
    if (per_lo, per_hi) != (0.0, 60.0):
        m &= df["per"].between(per_lo, per_hi)
    if min_yield:
        m &= df["net_yield"].fillna(0) >= min_yield
    if min_value:
        m &= df["avg_value_3m"].fillna(0) >= min_value
    res = df[m].sort_values("avg_value_3m", ascending=False)
    st.caption(t("results", n=len(res)))
    spec = {"symbol": ("symbol", "text"), "name": ("name", "text"), "sector_name": ("sector", "text"),
            "country_name": ("country", "text"), "compartment": ("compartment", "text"),
            "ref_price": ("price", "num"), "change_pct": ("change", "pct"), "ytd_pct": ("ytd_pct", "pct"),
            "1Y": ("return_1y_tr" if data.basis() == "tr" else "perf_1Y", "pct"),
            "per": ("per", "num2"), "net_yield": ("yield", "pct"), "avg_value_3m": ("avg_value_3m", "int")}
    table(res, spec, height=560)
    csv_button(res[list(spec)].rename(columns={k: t(l) for k, (l, _) in spec.items()}), f"brvm_screener_{v}.csv",
               "scr_csv")


# ---------------------------------------------------------------- investment simulator

def simulate(h: pd.DataFrame, divs: pd.DataFrame, index: pd.Series, amount: float, start: pd.Timestamp) -> pd.DataFrame:
    """Value over time of `amount` FCFA invested at the reference price of the first session >= start.

    Columns: reinvested (net dividends reinvested on the ex-date), cash (dividends kept in cash, not
    reinvested: shares x price + dividends received so far), price (price only), index (the same amount
    in the BRVM Composite, a price index). Fractional shares, no brokerage fees or taxes beyond the
    withholding already deducted from the net dividend."""
    h = h[h.index >= start]
    p = h["adj_ref_price"].ffill()
    tr = h["tr_price"].ffill()
    if p.dropna().empty:
        return pd.DataFrame()
    p0, tr0 = p.dropna().iloc[0], tr.dropna().iloc[0]
    shares = amount / p0
    d = divs[(divs["ex_date"] > p.index[0])].set_index("ex_date")["adj_div_amount"]
    cash = (d * shares).groupby(level=0).sum().reindex(p.index, fill_value=0.0).cumsum()
    out = pd.DataFrame({"reinvested": amount * tr / tr0, "price": amount * p / p0, "cash": shares * p + cash})
    idx = index[index.index >= p.index[0]].reindex(p.index).ffill()
    if idx.notna().any():
        out["index"] = amount * idx / idx.dropna().iloc[0]
    out["dividends"] = cash
    return out


def _simulator(v: str):
    stocks = data.stocks(v)
    listed = stocks[stocks["last_date"] == pd.Timestamp(v)]
    names = dict(zip(stocks["symbol"], stocks["name"]))
    symbols = listed["symbol"].tolist()
    c = st.columns([3, 2, 2])
    sym = c[0].selectbox(t("choose_stock"), symbols, index=symbols.index("SNTS") if "SNTS" in symbols else 0,
                         format_func=lambda s: f"{names[s]} ({s})", key="sim_symbol")
    amount = c[1].number_input(t("sim_amount"), min_value=10_000, max_value=10_000_000_000, value=1_000_000,
                               step=100_000, key="sim_amount")
    h = data.stock_history(v, sym)
    first = h["adj_ref_price"].first_valid_index()
    if first is None:
        st.info(t("no_data"))
        return
    last = h.index[-1]
    default = max(first, last - pd.DateOffset(years=5))
    start = c[2].date_input(t("sim_start"), value=default.date(), min_value=first.date(), max_value=last.date(),
                            format="DD/MM/YYYY", key="sim_start")
    sim = simulate(h, data.dividend_history(v, sym), data.index_history(v, "BRVM COMPOSITE"), float(amount),
                   pd.Timestamp(start))
    if len(sim) < 2:
        st.info(t("no_data"))
        return
    d0, d1 = sim.index[0], sim.index[-1]
    years = (d1 - d0).days / 365.25
    end = sim.iloc[-1]

    def _gain(x):
        return (x / amount - 1) * 100

    def _ann(x):
        return ((x / amount) ** (1 / years) - 1) * 100 if years >= 1 else None

    st.markdown(t("sim_sentence", amount=fmt_num(amount), name=names[sym], start=fmt_date(d0),
                  value=fmt_num(end["reinvested"]), gain=fmt_pct(_gain(end["reinvested"]), 1),
                  ann=fmt_pct(_ann(end["reinvested"]), 1) if years >= 1 else "—"))
    k = st.columns(4)
    k[0].metric(t("sim_reinvested"), f"{fmt_num(end['reinvested'])} FCFA", fmt_pct(_gain(end["reinvested"]), 1),
                border=True)
    k[1].metric(t("sim_cash"), f"{fmt_num(end['cash'])} FCFA", fmt_pct(_gain(end["cash"]), 1), border=True)
    k[2].metric(t("sim_price"), f"{fmt_num(end['price'])} FCFA", fmt_pct(_gain(end["price"]), 1), border=True)
    if "index" in sim:
        k[3].metric(t("sim_index"), f"{fmt_num(end['index'])} FCFA", fmt_pct(_gain(end["index"]), 1), border=True)
    rows = [{"scenario": t(f"sim_{c}"), "value": end[c], "gain": _gain(end[c]), "ann": _ann(end[c])}
            for c in ("reinvested", "cash", "price", "index") if c in sim]
    series = {t(f"sim_{c}"): sim[c] for c in ("reinvested", "cash", "price", "index") if c in sim}
    chart(charts.lines(series, t("sim_chart"), height=420, hover_fmt=",.0f"))
    table(pd.DataFrame(rows), {"scenario": ("sim_scenario", "text"), "value": ("sim_value", "int"),
                               "gain": ("sim_gain", "pct"), "ann": ("sim_ann", "pct")}, key="sim_table")
    st.caption(t("sim_note", dividends=fmt_amount(end["dividends"]), start=fmt_date(d0), end=fmt_date(d1)))


def render():
    v = data.as_of()
    st.title(t("page_compare"))
    tabs = st.tabs([t("compare"), t("tab_performance"), t("screener"), t("tab_simulator")])
    with tabs[0]:
        _compare(v)
    with tabs[1]:
        _performance(v)
    with tabs[2]:
        _screener(v)
    with tabs[3]:
        _simulator(v)
