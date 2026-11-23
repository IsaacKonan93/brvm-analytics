"""Plotly charts with the project's validated palette (see the dataviz rules in WEBAPP.md):
fixed categorical order, one y-axis per chart, unified hover, legends + end labels for <= 4 series,
diverging blue <-> red with a gray midpoint. Backgrounds follow the Streamlit theme (light/dark).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .i18n import plotly_separators, t

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
POS, NEG, MID = "#2a78d6", "#e34948", "#f0efec"
MUTED = "#898781"
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def _layout(fig: go.Figure, title: str | None = None, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=15)) if title else None,
        height=height, margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        font=dict(family=FONT), separators=plotly_separators(), hovermode="x unified",
        showlegend=legend, legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridwidth=0.5)
    return fig


def range_buttons() -> dict:
    """Range selector: 1M 3M 6M YTD 1Y 3Y 5Y All (translated)."""
    b = [dict(count=1, step="month", stepmode="backward", label=t("1M")),
         dict(count=3, step="month", stepmode="backward", label=t("3M")),
         dict(count=6, step="month", stepmode="backward", label=t("6M")),
         dict(count=1, step="year", stepmode="todate", label=t("YTD")),
         dict(count=1, step="year", stepmode="backward", label=t("1Y")),
         dict(count=3, step="year", stepmode="backward", label=t("3Y")),
         dict(count=5, step="year", stepmode="backward", label=t("5Y")),
         dict(step="all", label=t("ALL"))]
    return dict(buttons=b, x=0, y=1.02, yanchor="bottom", font=dict(size=11))


def lines(series: dict[str, pd.Series], title: str | None = None, height: int = 380, y_title: str | None = None,
          buttons: bool = False, end_labels: bool = True, hover_fmt: str = ",.2f", fill: bool = False) -> go.Figure:
    fig = go.Figure()
    for i, (name, s) in enumerate(series.items()):
        s = s.dropna()
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, mode="lines",
                                 line=dict(color=SERIES[i % len(SERIES)], width=2),
                                 fill="tozeroy" if fill and i == 0 else None,
                                 fillcolor="rgba(42,120,214,0.08)" if fill and i == 0 else None,
                                 hovertemplate=f"%{{y:{hover_fmt}}}<extra>{name}</extra>"))
        if end_labels and len(series) <= 4 and len(s):
            fig.add_annotation(x=s.index[-1], y=s.iloc[-1], text=f"{s.iloc[-1]:{hover_fmt}}" if len(series) == 1 else name,
                               showarrow=False, xanchor="left", xshift=6, font=dict(size=11, color=MUTED))
    _layout(fig, title, height, legend=len(series) > 1)
    fig.update_yaxes(title=y_title)
    if buttons:
        fig.update_xaxes(rangeselector=range_buttons())
        fig.update_layout(margin=dict(t=80 if title else 50))
    return fig


def price_volume(price: pd.Series, volume: pd.Series, price_name: str, volume_name: str,
                 height: int = 520) -> go.Figure:
    """Price on top, volume below: two panels sharing the time axis (never a dual axis)."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.74, 0.26], vertical_spacing=0.04)
    p = price.dropna()
    fig.add_trace(go.Scatter(x=p.index, y=p.values, name=price_name, mode="lines",
                             line=dict(color=SERIES[0], width=2), hovertemplate="%{y:,.0f}<extra></extra>"), 1, 1)
    fig.add_trace(go.Bar(x=volume.index, y=volume.values, name=volume_name, marker_color=SERIES[0],
                         opacity=0.55, hovertemplate="%{y:,.0f}<extra></extra>"), 2, 1)
    _layout(fig, None, height, legend=False)
    fig.update_xaxes(rangeselector=range_buttons(), row=1, col=1)
    fig.update_yaxes(title=price_name, row=1, col=1)
    fig.update_yaxes(title=volume_name, row=2, col=1)
    fig.update_layout(margin=dict(t=50))
    return fig


def hbars(labels, values, title: str | None = None, diverging: bool = False, text=None,
          height: int | None = None, color: str = SERIES[0]) -> go.Figure:
    colors = [POS if v >= 0 else NEG for v in values] if diverging else color
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color=colors, text=text,
                           textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x:,.2f}<extra></extra>"))
    _layout(fig, title, height or max(260, 34 * len(labels) + 70), legend=False)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=True, zeroline=True)
    return fig


def bars(df: pd.DataFrame, title: str | None = None, height: int = 360, names: dict | None = None,
         line: pd.Series | None = None, line_name: str | None = None) -> go.Figure:
    """Vertical bars, one trace per column (grouped), optional overlay line on the same axis."""
    fig = go.Figure()
    for i, c in enumerate(df.columns):
        fig.add_trace(go.Bar(x=df.index, y=df[c], name=(names or {}).get(c, c), marker_color=SERIES[i],
                             hovertemplate="%{y:,.0f}<extra>%{fullData.name}</extra>"))
    if line is not None:
        fig.add_trace(go.Scatter(x=line.index, y=line.values, name=line_name, mode="lines",
                                 line=dict(color=SERIES[1], width=2), hovertemplate="%{y:,.0f}<extra></extra>"))
    _layout(fig, title, height, legend=len(df.columns) > 1 or line is not None)
    fig.update_layout(barmode="group", bargap=0.2, bargroupgap=0.05)
    return fig


def heatmap_corr(corr: pd.DataFrame, title: str | None = None) -> go.Figure:
    scale = [[0.0, NEG], [0.5, MID], [1.0, POS]]
    fig = go.Figure(go.Heatmap(z=corr.values, x=corr.columns, y=corr.index, zmin=-1, zmax=1, zmid=0,
                               colorscale=scale, text=corr.round(2).values, texttemplate="%{text}",
                               hovertemplate="%{y} / %{x}: %{z:.2f}<extra></extra>", xgap=2, ygap=2))
    _layout(fig, title, max(320, 48 * len(corr) + 90), legend=False)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


def scatter_groups(groups: dict[str, pd.DataFrame], x: str, y: str, hover: str, title: str | None = None,
                   x_title: str | None = None, y_title: str | None = None, height: int = 420) -> go.Figure:
    fig = go.Figure()
    for i, (name, d) in enumerate(groups.items()):
        fig.add_trace(go.Scatter(x=d[x], y=d[y], mode="markers", name=name, text=d[hover],
                                 marker=dict(size=10, color=SERIES[i % len(SERIES)], line=dict(width=1.5, color="white")),
                                 hovertemplate="%{text}<br>%{x} · %{y:.2f}<extra></extra>"))
    _layout(fig, title, height, legend=len(groups) > 1)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title=x_title, showgrid=True)
    fig.update_yaxes(title=y_title)
    return fig
