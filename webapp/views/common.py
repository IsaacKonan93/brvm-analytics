"""Helpers shared by the pages: tables with translated headers, CSV download, chart display."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib.i18n import t

# column kinds -> Streamlit number formats
_FORMATS = {"int": "localized", "num": "localized", "num2": "%.2f", "pct": "%.2f %%", "text": None, "date": None}


def table(df: pd.DataFrame, spec: dict[str, tuple[str, str]], height: int | None = None, key: str | None = None):
    """Show df with columns in `spec` order: {column: (label_key, kind)}; kind in _FORMATS."""
    cols = [c for c in spec if c in df.columns]
    cfg = {}
    for c in cols:
        label_key, kind = spec[c]
        label = t(label_key)
        if kind == "date":
            cfg[c] = st.column_config.DateColumn(label, format="DD/MM/YYYY")
        elif kind == "text":
            cfg[c] = st.column_config.TextColumn(label)
        else:
            cfg[c] = st.column_config.NumberColumn(label, format=_FORMATS[kind])
    extra = {"height": height} if height else {}
    st.dataframe(df[cols], column_config=cfg, hide_index=True, width="stretch", key=key, **extra)


def csv_button(df: pd.DataFrame, filename: str, key: str):
    st.download_button(t("download_csv"), df.to_csv(index=False).encode("utf-8-sig"), file_name=filename,
                       mime="text/csv", key=key, icon=":material/download:")


def chart(fig):
    st.plotly_chart(fig, width="stretch", theme="streamlit", config={"displaylogo": False})
