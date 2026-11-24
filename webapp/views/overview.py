"""Market overview: headline indices, market figures, top movers, sectors, history."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import briefing, charts, data
from app_lib.i18n import fmt_amount, fmt_date, fmt_num, fmt_pct, t
from views.common import boc_md, chart, table, with_boc

MAX_ITEMS = 8  # per highlight group; the rest is counted


def _highlights(v: str, d: str):
    """Notable events of the session (app_lib/briefing.py)."""
    st.subheader(t("events_title"))
    ev = briefing.notable(v, d)
    groups = [
        ("highs", "ev_high", lambda r: f"**{r['name']}** {fmt_num(r['price'])} ({fmt_pct(r['change_pct'])})"),
        ("lows", "ev_low", lambda r: f"**{r['name']}** {fmt_num(r['price'])} ({fmt_pct(r['change_pct'])})"),
        ("limit", "ev_limit", lambda r: f"**{r['name']}** {fmt_pct(r['change_pct'])}"),
        ("volume", "ev_volume", lambda r: f"**{r['name']}** {fmt_amount(r['value'])} FCFA (× {fmt_num(r['multiple'], 1)})"),
        ("splits", "ev_splits", lambda r: f"**{r['name'] or r['symbol']}** {r['label']}"),
    ]
    shown = False
    for key, title, line in groups:
        df = ev[key]
        if df.empty:
            continue
        shown = True
        items = [f"- {line(r)}" for r in df.head(MAX_ITEMS).to_dict("records")]
        if len(df) > MAX_ITEMS:
            items.append(f"- … +{len(df) - MAX_ITEMS}")
        st.markdown(f"**{t(title)}**\n" + "\n".join(items))
    notices = ev["notices"]
    if len(notices):
        shown = True
        with st.expander(t("ev_notices", n=len(notices))):
            n = notices.assign(kind=notices["kind"].map(lambda k: t(f"kind_{k}")),
                               text=(notices["nature"] + " " + notices["subject"]).str.strip())
            table(with_boc(n), {"kind": ("kind", "text"), "company": ("company", "text"), "text": ("ev_text", "text"),
                                "boc": ("boc", "link")}, key="ov_notices")
    if not shown:
        st.info(t("no_events"))


def _upcoming(v: str, d: str):
    """Meetings and announced operations after the session, as known on that day."""
    st.subheader(t("upcoming_title"))
    up = briefing.upcoming(v, d)
    if up.empty:
        st.info(t("no_upcoming"))
        return
    table(with_boc(up, "seen"), {"date": ("date", "date"), "company": ("company", "text"), "label": ("event", "text"),
                                 "boc": ("boc", "link")}, height=min(420, 38 + 35 * len(up)), key="ov_upcoming")
    st.caption(t("upcoming_note"))


MOVERS = {"name": ("name", "text"), "ref_price": ("price", "num"), "change_pct": ("change", "pct"),
          "value": ("value", "int")}


def render():
    v = data.as_of()
    sess = data.sessions(v)
    head, pick = st.columns([4, 1])
    with pick:
        day = st.date_input(t("session"), value=sess[0], min_value=sess[-1], max_value=sess[0],
                            format="DD/MM/YYYY", key="ov_day")
    day = data.session_on_or_before(v, day)
    d = day.isoformat()
    with head:
        st.title(t("page_overview"))
        st.caption(f"{t('session')} : {fmt_date(day)} · {boc_md(day)}")

    # ---- written summary (daily briefing)
    with st.container(border=True):
        st.markdown(f"**{t('briefing_title')}** — {briefing.summary(v, d)}")

    # ---- headline indices
    hl = data.headline(v, d)
    order = ["BRVM COMPOSITE", "BRVM 30", "BRVM PRESTIGE", "BRVM 10"]
    hl = hl.set_index("index_name").reindex([n for n in order if n in set(hl["index_name"])])
    cols = st.columns(max(len(hl), 1) + 1)
    for col, (name, r) in zip(cols, hl.iterrows()):
        with col:
            st.metric(name, fmt_num(r["value"], 2), f"{fmt_pct(r['change_pct'])} ({t('day')})", border=True)
            st.caption(f"{t('ytd')} : {fmt_pct(r['ytd_pct'])}")

    # ---- market figures
    s = data.stats_on(v, d)
    up, down, flat = data.breadth(v, d)
    c = st.columns(4)
    c[0].metric(t("equity_cap"), fmt_amount(s.get("equity_market_cap")),
                fmt_pct(s.get("equity_market_cap_change_pct")) if s.get("equity_market_cap_change_pct") is not None else None,
                border=True)
    c[1].metric(t("bond_cap"), fmt_amount(s.get("bond_market_cap")),
                fmt_pct(s.get("bond_market_cap_change_pct")) if s.get("bond_market_cap_change_pct") is not None else None,
                border=True)
    c[2].metric(t("value_traded"), fmt_amount(data.equity_value(v, d)), None, border=True)
    c[3].metric(t("breadth"), f"{up:.0f} / {down:.0f} / {flat:.0f}", None, border=True)

    # ---- highlights and upcoming events (daily briefing)
    ev_col, up_col = st.columns(2)
    with ev_col:
        _highlights(v, d)
    with up_col:
        _upcoming(v, d)

    # ---- Composite history
    comp = data.index_history(v, "BRVM COMPOSITE")
    chart(charts.lines({"BRVM Composite": comp}, t("composite_history"), height=420, buttons=True, fill=True))

    # ---- movers
    eq = data.equities_on(v, d)
    g, l = st.columns(2)
    with g:
        st.subheader(t("top_gainers"))
        up_df = eq[eq["change_pct"] > 0].nlargest(5, "change_pct")
        table(up_df, MOVERS) if len(up_df) else st.info(t("none_rose"))
    with l:
        st.subheader(t("top_losers"))
        dn_df = eq[eq["change_pct"] < 0].nsmallest(5, "change_pct")
        table(dn_df, MOVERS) if len(dn_df) else st.info(t("none_fell"))

    left, right = st.columns(2)
    with left:
        most = eq.nlargest(10, "value")
        if len(most):
            chart(charts.hbars(most["name"], most["value"], t("most_traded"),
                               text=[fmt_amount(x) for x in most["value"]]))
    with right:
        sec = data.sector_indices(v, d)
        if len(sec):
            sec = sec.assign(label=sec["index_name"].str.replace("BRVM ", "").str.title()).sort_values("ytd_pct", ascending=False)
            chart(charts.hbars(sec["label"], sec["ytd_pct"], t("sector_ytd"), diverging=True,
                               text=[fmt_pct(x, 1) for x in sec["ytd_pct"]]))

    # ---- history
    hist = data.stats_history(v, ("equity_market_cap", "bond_market_cap"))
    caps = {t("equities"): data.drop_spikes(hist["equity_market_cap"].dropna()),
            t("bonds"): data.drop_spikes(hist["bond_market_cap"].dropna())}
    chart(charts.lines(caps, t("market_cap_history"), height=380, buttons=True, hover_fmt=",.3s"))
    mv = data.monthly_value(v)
    chart(charts.bars(pd.DataFrame({t("value"): mv}), t("monthly_value"), line=mv.rolling(12).mean(),
                      line_name=t("avg12")))
