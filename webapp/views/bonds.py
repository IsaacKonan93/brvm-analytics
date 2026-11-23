"""Bonds: listed bonds with terms, coupon vs maturity, one bond's history, value traded per year."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import charts, data
from app_lib.i18n import fmt_date, fmt_num, t
from views.common import chart, csv_button, table


def render():
    v = data.as_of()
    st.title(t("page_bonds"))
    df = data.bonds_on(v, v)
    st.caption(f"{t('bonds_listed', n=len(df))} · {t('session')} : {fmt_date(v)}")

    c = st.columns(3)
    issuers = c[0].multiselect(t("issuer"), sorted(df["issuer"].dropna().unique()), key="bd_issuer")
    sections = c[1].multiselect(t("category"), sorted(df["section"].dropna().unique()), key="bd_section")
    years = df["maturity_year"].dropna()
    lo, hi = (int(years.min()), int(years.max())) if len(years) else (2020, 2040)
    mat = c[2].slider(t("maturity"), lo, hi, (lo, hi), key="bd_maturity")
    m = pd.Series(True, index=df.index)
    if issuers:
        m &= df["issuer"].isin(issuers)
    if sections:
        m &= df["section"].isin(sections)
    if mat != (lo, hi):
        m &= df["maturity_year"].between(*mat)
    sel = df[m].sort_values(["issuer", "maturity_year"])

    spec = {"symbol": ("symbol", "text"), "name": ("name", "text"), "issuer": ("issuer", "text"),
            "coupon_rate": ("coupon_rate", "num2"), "maturity_year": ("maturity", "text"),
            "nominal": ("nominal", "num"), "ref_price": ("bond_price", "num"), "accrued_coupon": ("accrued", "num2"),
            "next_coupon_date": ("next_coupon", "date"), "amort_type": ("amort", "text"), "volume": ("volume", "int")}
    table(sel.assign(maturity_year=sel["maturity_year"].astype("Int64").astype(str)), spec, height=420)
    csv_button(sel[list(spec)], f"brvm_bonds_{v}.csv", "bd_csv")

    # coupon vs maturity: one color per issuer when <= 3 issuers are selected, otherwise one color
    pts = sel.dropna(subset=["coupon_rate", "maturity_year"])
    if len(pts):
        groups = {i: g for i, g in pts.groupby("issuer")} if 0 < len(issuers) <= 3 else {t("bonds"): pts}
        chart(charts.scatter_groups(groups, "maturity_year", "coupon_rate", "name", t("coupon_vs_maturity"),
                                    t("maturity"), t("coupon_rate")))

    st.subheader(t("choose_bond"))
    options = sel["symbol"].tolist() or df["symbol"].tolist()
    names = dict(zip(df["symbol"], df["name"]))
    sym = st.selectbox(t("choose_bond"), options, format_func=lambda s: f"{names.get(s, s)} ({s})",
                       label_visibility="collapsed", key="bd_symbol")
    h = data.bond_history(v, sym)
    if len(h):
        left, right = st.columns(2)
        with left:
            chart(charts.lines({t("bond_price"): h["ref_price"]}, t("bond_price"), height=320, hover_fmt=",.0f"))
        with right:
            chart(charts.lines({t("accrued"): h["accrued_coupon"]}, t("accrued"), height=320, hover_fmt=",.2f"))

    tv = data.traded_by_year(v).rename(columns={"equities": t("equities"), "bonds": t("bonds")})
    chart(charts.bars(tv[[t("equities"), t("bonds")]], t("traded_by_year")))
