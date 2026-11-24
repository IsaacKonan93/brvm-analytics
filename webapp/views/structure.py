"""Market structure: capitalisation by stock, sector and country, concentration, treemap of the day.

Step 6 of WEBAPP_ROADMAP.md. Each stock's capitalisation = number of shares (brvm.org, fetch_shares.py)
x split-adjusted reference price (data.market_structure). Rules in WEBAPP.md, "Market structure rules".
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import charts, data
from app_lib.i18n import COUNTRIES, SECTOR_CODES, fmt_amount, fmt_date, fmt_num, fmt_pct, name_of, t
from views.common import boc_md, chart, csv_button, table


def render():
    v = data.as_of()
    sess = data.sessions(v)
    head, pick = st.columns([4, 1])
    with pick:
        day = st.date_input(t("session"), value=sess[0], min_value=dt_min(v), max_value=sess[0],
                            format="DD/MM/YYYY", key="ms_day")
    day = data.session_on_or_before(v, day)
    d = day.isoformat()
    with head:
        st.title(t("page_structure"))
        st.caption(f"{t('session')} : {fmt_date(day)} · {boc_md(day)}")
    ms = data.market_structure(v, d)
    if ms.empty:
        st.info(t("no_shares"))
        return
    ms["sector_name"] = ms["sector"].map(lambda c: name_of(SECTOR_CODES, c) or "—")
    ms["country_name"] = ms["country"].map(lambda c: name_of(COUNTRIES, c) or "—")

    # ---- headline figures
    brvm_cap = data.stats_on(v, d).get("equity_market_cap")
    first = ms.iloc[0]
    k = st.columns(4)
    k[0].metric(t("equity_cap"), fmt_amount(brvm_cap or ms["cap"].sum()), border=True)
    k[1].metric(t("nb_companies"), str(len(ms)), border=True)
    k[2].metric(t("largest_company", name=first["name"]), fmt_pct(first["weight"], 1, signed=False), border=True)
    k[3].metric(t("top5_share"), fmt_pct(ms["weight"].head(5).sum(), 1, signed=False), border=True)

    # ---- treemap of the session
    by = st.radio(t("group_by"), ["sector_name", "country_name"], horizontal=True, key="ms_group",
                  format_func=lambda c: t("sector") if c == "sector_name" else t("country"))
    hover = [f"<b>{r['name']}</b> ({r['symbol']})<br>{t('cap')} : {fmt_amount(r['cap'])} FCFA · "
             f"{fmt_pct(r['weight'], 1, signed=False)}<br>{t('change')} : {fmt_pct(r['change_pct'])}"
             for r in ms.to_dict("records")]
    chart(charts.treemap(ms, by, "name", "cap", "change_pct", hover, t("treemap_title"), height=600))
    st.caption(t("treemap_note"))

    # ---- by sector and by country
    left, right = st.columns(2)
    for col, key, title in ((left, "sector_name", "cap_by_sector"), (right, "country_name", "cap_by_country")):
        g = ms.groupby(key)["weight"].sum().sort_values(ascending=False)
        with col:
            chart(charts.hbars(g.index, g.values, t(title), text=[fmt_pct(x, 1, signed=False) for x in g.values]))

    # ---- concentration since 2019
    ch = data.concentration_history(v)
    if len(ch):  # indexed by the last session of each month
        chart(charts.lines({t("top5_share"): ch["top5"], t("top1_share"): ch["top1"]}, t("concentration_title"),
                           height=360, hover_fmt=".1f"))
        st.caption(t("concentration_note", lo=fmt_pct(ch["gap_pct"].min(), 1), hi=fmt_pct(ch["gap_pct"].max(), 1)))

    # ---- table
    st.subheader(t("structure_table"))
    out = ms.assign(rank=range(1, len(ms) + 1))
    spec = {"rank": ("rank", "int"), "symbol": ("symbol", "text"), "name": ("name", "text"),
            "sector_name": ("sector", "text"), "country_name": ("country", "text"), "cap": ("cap_fcfa", "int"),
            "weight": ("weight", "pct"), "shares": ("shares", "int"), "adj_ref_price": ("price", "num"),
            "change_pct": ("change", "pct")}
    table(out, spec, height=520, key="ms_table")
    st.caption(t("structure_note", date=fmt_date(ms["date"].max()) if "date" in ms else "—"))
    csv_button(out[list(spec)].rename(columns={k: t(l) for k, (l, _) in spec.items()}), f"brvm_structure_{d}.csv",
               "ms_csv")


def dt_min(v: str):
    """First session of the structure history (today's share counts rebuild the total well since 2019)."""
    s = [x for x in data.sessions(v) if x.isoformat() >= data.STRUCTURE_SINCE]
    return s[-1] if s else data.sessions(v)[-1]
