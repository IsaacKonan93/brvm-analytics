"""Compare stocks (rebased performance, risk, correlation) and screen the market."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st

from app_lib import charts, data
from app_lib.i18n import COUNTRIES, SECTOR_CODES, name_of, t
from views.common import chart, csv_button, table

PERIODS = {"YTD": None, "1Y": 365, "3Y": 3 * 365, "5Y": 5 * 365, "ALL": None}


def _start(v: str, key: str) -> str | None:
    end = dt.date.fromisoformat(v)
    if key == "YTD":
        return dt.date(end.year, 1, 1).isoformat()
    if key == "ALL":
        return None
    return (end - dt.timedelta(days=PERIODS[key])).isoformat()


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
    st.caption(t("basis_note_tr" if data.basis() == "tr" else "basis_note_price"))

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


def _screener(v: str):
    df = data.screener(v).copy()
    df["sector_name"] = df["sector_code"].map(lambda c: name_of(SECTOR_CODES, c))
    df["country_name"] = df["country"].map(lambda c: name_of(COUNTRIES, c))
    c = st.columns(3)
    sectors = c[0].multiselect(t("sector"), sorted(df["sector_name"].dropna().unique()), key="scr_sector")
    comps = c[1].multiselect(t("compartment"), sorted(df["compartment"].dropna().unique()), key="scr_comp")
    countries = c[2].multiselect(t("country"), sorted(df["country_name"].dropna().unique()), key="scr_country")
    c = st.columns(3)
    per_lo, per_hi = c[0].slider(t("per_range"), 0.0, 60.0, (0.0, 60.0), step=0.5, key="scr_per")
    min_yield = c[1].number_input(t("min_yield"), 0.0, 30.0, 0.0, step=0.5, key="scr_yield")
    min_value = c[2].select_slider(t("min_value"), options=[0, 1e6, 5e6, 1e7, 5e7, 1e8],
                                   format_func=lambda x: f"{x:,.0f}", key="scr_value")
    m = pd.Series(True, index=df.index)
    if sectors:
        m &= df["sector_name"].isin(sectors)
    if comps:
        m &= df["compartment"].isin(comps)
    if countries:
        m &= df["country_name"].isin(countries)
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
            "per": ("per", "num2"), "net_yield": ("yield", "pct"), "avg_value_3m": ("avg_value_3m", "int")}
    table(res, spec, height=560)
    csv_button(res[list(spec)].rename(columns={k: t(l) for k, (l, _) in spec.items()}), f"brvm_screener_{v}.csv",
               "scr_csv")


def render():
    v = data.as_of()
    st.title(t("page_compare"))
    tab1, tab2 = st.tabs([t("compare"), t("screener")])
    with tab1:
        _compare(v)
    with tab2:
        _screener(v)
