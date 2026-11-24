"""Official bulletins (BOC): the bulletin of any date, and the list of bulletins, linked to the PDFs on brvm.org.

The app links to BRVM's own files and does not re-host them. The addresses come from the table
`bulletins`, built from the download manifest (see EXTRACTION.md).
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from app_lib import data
from app_lib.i18n import fmt_date, month_name, t, weekday_name
from views.common import csv_button, table

PDF_ICON = ":material/picture_as_pdf:"


def _day_result(b: pd.DataFrame, day: dt.date):
    """What the date picker shows for `day`: the link, or why there is none plus the previous bulletin."""
    row = b[b["date"] == pd.Timestamp(day)]
    status = row["status"].iloc[0] if len(row) else None
    url = row["url"].iloc[0] if len(row) else None
    if status == "published" and url:
        st.link_button(t("open_boc", date=fmt_date(day)), url, type="primary", icon=PDF_ICON)
        return
    if day.weekday() >= 5:
        st.info(t("boc_weekend"))
    elif status == "unavailable":
        st.warning(t("boc_unavailable", date=fmt_date(day)))
    else:
        st.info(t("boc_none", date=fmt_date(day)))
    prev = b[(b["date"] < pd.Timestamp(day)) & (b["status"] == "published") & b["url"].notna()]
    if len(prev):
        p = prev.iloc[0]  # b is sorted newest first
        st.link_button(t("previous_boc", date=fmt_date(p["date"])), p["url"], icon=PDF_ICON)


def render():
    v = data.as_of()
    st.title(t("page_bulletins"))
    st.caption(t("bulletins_intro"))
    b = data.bulletins(v)
    if b.empty:
        st.info(t("no_data"))
        return
    first, last = b["date"].min().date(), b["date"].max().date()

    # ---- the bulletin of one date
    pick, result = st.columns([1, 3], vertical_alignment="bottom")
    with pick:
        day = st.date_input(t("date"), value=last, min_value=first, max_value=last, format="DD/MM/YYYY",
                            key="boc_day")
    with result:
        _day_result(b, day)

    # ---- list, filtered by year and month
    st.subheader(t("bulletin_list"))
    years = sorted(b["date"].dt.year.unique(), reverse=True)
    fy, fm, _ = st.columns([1, 1, 3])
    year = fy.selectbox(t("year"), years, key="boc_year")
    month = fm.selectbox(t("month"), [0] + list(range(1, 13)), key="boc_month",
                         format_func=lambda m: t("all_months") if m == 0 else month_name(m))
    sel = b[b["date"].dt.year == year]
    if month:
        sel = sel[sel["date"].dt.month == month]
    if sel.empty:
        st.info(t("no_data"))
        return
    sel = sel.assign(weekday=[weekday_name(d) for d in sel["date"]],
                     status_label=sel["status"].map(lambda s: t(f"bst_{s}")),
                     boc=sel["url"].where(sel["status"] == "published"))
    st.caption(t("bulletins_count", n=int((sel["status"] == "published").sum()),
                 m=int((sel["status"] != "published").sum())))
    table(sel, {"date": ("date", "date"), "weekday": ("weekday", "text"), "status_label": ("status", "text"),
                "boc": ("boc", "link")}, height=420, key="boc_table")
    csv_button(sel[["date", "status", "url"]], f"brvm_boc_{year}.csv", key="boc_csv")
