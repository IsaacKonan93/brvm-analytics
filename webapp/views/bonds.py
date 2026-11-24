"""Bonds: market figures, listed bonds with terms and liquidity, coupon vs maturity, one bond's history,
value traded per year.

Reviewed in step 7 of WEBAPP_ROADMAP.md: issuers merged (one per state), short FR/EN categories, price in
% of nominal, liquidity (last trade, sessions traded in 3 months) and headline figures.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import charts, data
from app_lib.i18n import BOND_CATEGORIES, COUNTRIES, fmt_amount, fmt_date, fmt_num, name_of, t
from views.common import boc_md, chart, csv_button, table


def issuer_label(key: str, country: str | None) -> str:
    # country is NaN (not None) for non-state issuers once in a DataFrame: test for a real code
    return t("state_issuer", country=name_of(COUNTRIES, country)) if isinstance(country, str) and country else key


def render():
    v = data.as_of()
    st.title(t("page_bonds"))
    df = data.bonds_on(v, v).copy()
    df["issuer_name"] = [issuer_label(k, c) for k, c in zip(df["issuer_key"], df["issuer_country"])]
    df["category_name"] = df["category"].map(lambda c: name_of(BOND_CATEGORIES, c) or "—")
    st.caption(f"{t('bonds_listed', n=len(df))} · {t('session')} : {fmt_date(v)} · {boc_md(v)}")

    # ---- market figures of the session
    s = data.stats_on(v, v)
    traded = int((df["volume"].fillna(0) > 0).sum())
    k = st.columns(4)
    k[0].metric(t("bond_cap"), fmt_amount(s.get("bond_market_cap")), border=True)
    k[1].metric(t("bond_value_day"), f"{fmt_amount(s.get('bond_value') or df['value'].sum())} FCFA", border=True)
    k[2].metric(t("bonds_traded_day"), t("n_of_m", n=traded, m=len(df)), border=True)
    k[3].metric(t("bonds_traded_3m"), t("n_of_m", n=int((df["traded_3m"] > 0).sum()), m=len(df)), border=True)

    # ---- filters and table
    c = st.columns(3)
    issuers = c[0].multiselect(t("issuer"), sorted(df["issuer_name"].unique()), key="bd_issuer")
    cats = c[1].multiselect(t("category"), sorted(df["category_name"].unique()), key="bd_section")
    years = df["maturity_year"].dropna()
    lo, hi = (int(years.min()), int(years.max())) if len(years) else (2020, 2040)
    mat = c[2].slider(t("maturity"), lo, hi, (lo, hi), key="bd_maturity")
    m = pd.Series(True, index=df.index)
    if issuers:
        m &= df["issuer_name"].isin(issuers)
    if cats:
        m &= df["category_name"].isin(cats)
    if mat != (lo, hi):
        m &= df["maturity_year"].between(*mat)
    sel = df[m].sort_values(["issuer_name", "maturity_year"])

    spec = {"symbol": ("symbol", "text"), "name": ("name", "text"), "issuer_name": ("issuer", "text"),
            "category_name": ("category", "text"), "coupon_rate": ("coupon_rate", "num2"),
            "maturity_year": ("maturity", "text"), "price_pct": ("price_pct", "num2"), "ref_price": ("bond_price", "num"),
            "nominal": ("nominal", "num"), "accrued_coupon": ("accrued", "num2"), "next_coupon_date": ("next_coupon", "date"),
            "amort_type": ("amort", "text"), "last_trade": ("last_trade", "date"), "traded_3m": ("traded_3m", "int"),
            "volume": ("volume", "int")}
    table(sel.assign(maturity_year=sel["maturity_year"].astype("Int64").astype(str).replace("<NA>", "—")), spec,
          height=420, key="bd_table")
    st.caption(t("bonds_note"))
    csv_button(sel[list(spec)].rename(columns={k: t(l) for k, (l, _) in spec.items()}), f"brvm_bonds_{v}.csv", "bd_csv")

    # ---- coupon vs maturity: one color per issuer when <= 3 issuers are selected, otherwise one color
    pts = sel.dropna(subset=["coupon_rate", "maturity_year"])
    if len(pts):
        groups = {i: g for i, g in pts.groupby("issuer_name")} if 0 < len(issuers) <= 3 else {t("bonds"): pts}
        chart(charts.scatter_groups(groups, "maturity_year", "coupon_rate", "name", t("coupon_vs_maturity"),
                                    t("maturity"), t("coupon_rate")))

    # ---- one bond
    st.subheader(t("choose_bond"))
    options = sel["symbol"].tolist() or df["symbol"].tolist()
    names = dict(zip(df["symbol"], df["name"]))
    sym = st.selectbox(t("choose_bond"), options, format_func=lambda x: f"{names.get(x, x)} ({x})",
                       label_visibility="collapsed", key="bd_symbol")
    h = data.bond_history(v, sym)
    if len(h):
        left, right = st.columns(2)
        with left:
            chart(charts.lines({t("price_pct"): h["price_pct"]}, t("price_pct_hist"), height=320, hover_fmt=",.2f"))
        with right:
            chart(charts.lines({t("accrued"): h["accrued_coupon"]}, t("accrued"), height=320, hover_fmt=",.2f"))

    tv = data.traded_by_year(v).rename(columns={"equities": t("equities"), "bonds": t("bonds")})
    chart(charts.bars(tv[[t("equities"), t("bonds")]], t("traded_by_year")))
