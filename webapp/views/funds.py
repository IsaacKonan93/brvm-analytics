"""Mutual funds (OPCVM): ranking by 1-year / 3-year NAV performance and NAV charts."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import charts, data
from app_lib.i18n import FUND_CATEGORIES, name_of, t
from views.common import chart, csv_button, table


def render():
    v = data.as_of()
    st.title(t("page_funds"))
    rk = data.fund_ranking(v).copy()
    rk["category_name"] = rk["category"].map(lambda c: name_of(FUND_CATEGORIES, c))
    c = st.columns(2)
    cats = c[0].multiselect(t("category"), sorted(rk["category_name"].dropna().unique()), key="fd_cat")
    mgrs = c[1].multiselect(t("manager"), sorted(rk["manager"].dropna().unique()), key="fd_mgr")
    m = pd.Series(True, index=rk.index)
    if cats:
        m &= rk["category_name"].isin(cats)
    if mgrs:
        m &= rk["manager"].isin(mgrs)
    sel = rk[m].sort_values("perf_1y", ascending=False, na_position="last")
    st.caption(t("funds_count", n=len(sel)))
    spec = {"fund_name": ("name", "text"), "manager": ("manager", "text"), "category_name": ("category", "text"),
            "nav_last": ("nav", "num2"), "nav_date_last": ("nav_date", "date"), "perf_1y": ("perf_1y", "pct"),
            "perf_3y": ("perf_3y", "pct")}
    table(sel, spec, height=460)
    broken = sel[sel["nav_break"].notna() & sel["perf_1y"].isna()]["fund_name"].tolist()
    if broken:
        st.caption(t("nav_break_note", funds=", ".join(broken)))
    csv_button(sel[list(spec)], f"brvm_funds_{v}.csv", "fd_csv")

    default = sel.dropna(subset=["perf_1y"])["fund_name"].head(3).tolist()
    picks = st.multiselect(t("choose_funds"), sel["fund_name"].tolist(), default=default, max_selections=4,
                           key="fd_picks")
    if picks:
        nav = data.fund_navs(v)
        start = pd.Timestamp(v) - pd.Timedelta(days=3 * 365)
        series = {}
        for f in picks:
            s = nav[(nav["fund_name"] == f) & (nav["nav_date"] >= start)].set_index("nav_date")["nav"]
            s = data.drop_spikes(s)  # a few NAVs are misprinted in the bulletins
            if len(s):
                series[f] = s / s.iloc[0] * 100
        chart(charts.lines(series, t("nav_chart"), height=420, hover_fmt=",.1f"))
