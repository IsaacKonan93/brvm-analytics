"""Helpers shared by the pages: tables with translated headers, CSV download, chart display."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import data
from app_lib.i18n import t

# column kinds -> Streamlit number formats ("link": a URL shown as "📄 BOC")
_FORMATS = {"int": "localized", "num": "localized", "num2": "%.2f", "pct": "%.2f %%", "text": None, "date": None,
            "link": None}


def table(df: pd.DataFrame, spec: dict[str, tuple[str, str]], height: int | None = None, key: str | None = None):
    """Show df with columns in `spec` order: {column: (label_key, kind)}; kind in _FORMATS."""
    cols = [c for c in spec if c in df.columns]
    cfg = {}
    for c in cols:
        label_key, kind = spec[c]
        label = t(label_key)
        if kind == "date":
            cfg[c] = st.column_config.DateColumn(label, format="DD/MM/YYYY")
        elif kind == "link":
            cfg[c] = st.column_config.LinkColumn(label, display_text=t("boc_link"))
        elif kind == "text":
            cfg[c] = st.column_config.TextColumn(label)
        else:
            cfg[c] = st.column_config.NumberColumn(label, format=_FORMATS[kind])
    extra = {"height": height} if height else {}
    st.dataframe(df[cols], column_config=cfg, hide_index=True, width="stretch", key=key, **extra)


def boc_md(day) -> str:
    """Markdown link "📄 BOC" to the official bulletin of `day` on brvm.org, or "" if there is none."""
    url = data.boc_url(data.as_of(), day)
    return f"[{t('boc_link')}]({url})" if url else ""


def with_boc(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """df plus a `boc` column: the brvm.org address of the bulletin of each row's date (for kind "link")."""
    urls = data.boc_urls(data.as_of())
    return df.assign(boc=pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d").map(urls))


def csv_button(df: pd.DataFrame, filename: str, key: str):
    st.download_button(t("download_csv"), df.to_csv(index=False).encode("utf-8-sig"), file_name=filename,
                       mime="text/csv", key=key, icon=":material/download:")


def chart(fig):
    st.plotly_chart(fig, width="stretch", theme="streamlit", config={"displaylogo": False})
