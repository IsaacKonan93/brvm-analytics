"""Daily briefing: written summary of a session, notable events, upcoming events (WEBAPP_ROADMAP.md, step 2).

Everything is computed from the database for one session `day` (any past session works the same way):

* notable events of the session:
    - new 52-week high / low: split-adjusted reference price above the highest (below the lowest) of the
      previous 365 days, for stocks listed for at least a year;
    - close to the daily limit: |change| >= 7 % (the BRVM limit is ±7.5 %; with price ticks a stock at the
      limit often shows e.g. -7.33 %);
    - unusual trading: value traded >= 5 x its average of the previous 63 sessions (about 3 months);
    - splits taking effect; new notices (not in the previous bulletin);
* upcoming events, as known on `day`: general meetings, and the corporate operations announced in the
  bulletins with a future date (dividend payments, first listings...);
* the written summary, built from text templates in French and English (no AI).
The thresholds were measured on 2026: about 1 unusual-volume and 1 limit move per session.
"""

from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import streamlit as st

from app_lib import data
from app_lib.i18n import fmt_amount, fmt_num, fmt_pct, lang, t

LIMIT_MOVE = 7.0          # % : "close to the ±7.5 % daily limit"
VOLUME_MULTIPLE = 5       # x the 3-month average value traded
AVG_SESSIONS = 63         # ~3 months of sessions
NOTICE_LOOKBACK = 15      # sessions of operation notices scanned for upcoming events

_MONTHS = {m: i for i, names in enumerate([
    ("janvier", "january"), ("février", "fevrier", "february"), ("mars", "march"), ("avril", "april"), ("mai", "may"),
    ("juin", "june"), ("juillet", "july"), ("août", "aout", "august"), ("septembre", "september"),
    ("octobre", "october"), ("novembre", "november"), ("décembre", "decembre", "december")], 1) for m in names}
_DATE_NUM = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_DATE_TXT = re.compile(r"(\d{1,2})(?:er)?\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})", re.I)
_DIVIDEND = re.compile(r"dividendes?\s+de\s+([\d\s.,]+)\s*F\s*CFA\s*(net|brut)?", re.I)
_LISTING = re.compile(r"Premi[èe]re cotation\s*-\s*(.+?)(?:\s*-\s*Premi[èe]re cotation|\s*,?\s*le\s+\d|$)", re.I)
_SPLIT = re.compile(r"\((\d+)\)\s*actions?\s+nouvelles?\s+pour\s+\w+\s*\((\d+)\)\s*actions?\s+anciennes?", re.I)
_GARBLED = re.compile(r"[$%&*@#+]")  # company names mis-decoded from the PDF fonts, e.g. "$),1+$%"
_MEETING_EN = {"ordinaire": "Ordinary", "extraordinaire": "Extraordinary", "mixte": "Combined"}


def event_date(text: str) -> dt.date | None:
    """Last date written in a notice ('le 27/10/2026', 'le 1er décembre 2026'), or None."""
    found = []
    for m in _DATE_NUM.finditer(text or ""):
        found.append((m.start(), (int(m[3]), int(m[2]), int(m[1]))))
    for m in _DATE_TXT.finditer(text or ""):
        found.append((m.start(), (int(m[3]), _MONTHS[m[2].lower()], int(m[1]))))
    for _, (y, mo, d) in sorted(found, reverse=True):
        try:
            return dt.date(y, mo, d)
        except ValueError:
            continue
    return None


def describe_operation(text: str) -> tuple[str, str]:
    """(kind, label in the current language) of an operation notice: dividend | split | listing | other."""
    m = _SPLIT.search(text or "")
    if m:
        return "split", t("ev_split", new=m[1], old=m[2])
    m = _DIVIDEND.search(text or "")
    if m:
        amount = m[1].strip().rstrip(",.")
        net = {"net": t("div_net"), "brut": t("div_gross")}.get((m[2] or "").lower(), "")
        return "dividend", t("ev_dividend", amount=amount, net=net).replace("  ", " ").strip()
    m = _LISTING.search(text or "")
    if m:
        return "listing", t("ev_listing", what=m[1].strip())
    return "other", (text or "").strip()


def meeting_label(nature: str) -> str:
    nature = (nature or "").strip()
    if lang() == "en":
        base = nature.split("(")[0].strip().lower()
        nature = _MEETING_EN.get(base, nature)
    return t("ev_meeting", nature=nature.lower() if lang() == "fr" else nature).strip()


# ---------------------------------------------------------------- notable events

@st.cache_data(show_spinner=False)
def _window(v: str, day: str) -> pd.DataFrame:
    """Adjusted quotes of the 400 days up to `day`, with the 52-week range and 3-month average value."""
    start = (pd.Timestamp(day) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    q = data.query("""SELECT date, symbol, name, adj_ref_price AS price, change_pct, value
                      FROM equity_quotes_adjusted WHERE date BETWEEN ? AND ? ORDER BY symbol, date""", (start, day))
    out = []
    for _, g in q.groupby("symbol", sort=False):
        g = g.set_index("date")
        g["hi"] = g["price"].rolling("365D", closed="left").max()
        g["lo"] = g["price"].rolling("365D", closed="left").min()
        g["since"] = g.index.min()
        g["avg_value"] = g["value"].shift(1).rolling(AVG_SESSIONS, min_periods=40).mean()
        out.append(g.reset_index())
    return pd.concat(out) if out else q


@st.cache_data(show_spinner=False)
def notable(v: str, day: str) -> dict[str, pd.DataFrame]:
    """Notable events of the session `day`: highs, lows, limit, volume, splits, notices (DataFrames)."""
    w = _window(v, day)
    d = w[w["date"] == pd.Timestamp(day)].copy()
    year_old = d["since"] <= pd.Timestamp(day) - pd.Timedelta(days=365)
    ok = d["price"].notna()  # misprinted sessions have no adjusted price
    highs = d[ok & year_old & (d["price"] > d["hi"])].sort_values("change_pct", ascending=False)
    lows = d[ok & year_old & (d["price"] < d["lo"])].sort_values("change_pct")
    limit = d[d["change_pct"].abs() >= LIMIT_MOVE].sort_values("change_pct", ascending=False)
    vol = d[(d["avg_value"] > 0) & (d["value"] >= VOLUME_MULTIPLE * d["avg_value"])]
    vol = vol.assign(multiple=vol["value"] / vol["avg_value"]).sort_values("multiple", ascending=False)

    splits = data.query("""SELECT a.symbol, s.name, a.label FROM corporate_actions a
                           LEFT JOIN securities s USING (symbol) WHERE a.date = ?""", (day,))
    prev = data.query("SELECT MAX(date) AS d FROM corporate_notices WHERE date < ?", (day,), dates=())["d"].iloc[0]
    notices = data.query("SELECT date, kind, company, reference, nature, subject FROM corporate_notices "
                         "WHERE date IN (?, ?)", (day, prev or day))
    key = ["kind", "company", "reference", "nature", "subject"]
    notices[key] = notices[key].fillna("")
    notices = notices[(notices["nature"] != "") | (notices["subject"] != "")]
    today = notices[notices["date"] == pd.Timestamp(day)]
    before = set(map(tuple, notices.loc[notices["date"] != pd.Timestamp(day), key].values))
    new = today[[tuple(r) not in before for r in today[key].values]].drop_duplicates(key)
    return {"highs": highs, "lows": lows, "limit": limit, "volume": vol, "splits": splits, "notices": new}


# ---------------------------------------------------------------- upcoming events

@st.cache_data(show_spinner=False)
def _upcoming_raw(v: str, day: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    meetings = data.query("""SELECT company, meeting_date, nature, time, place, last_seen FROM general_meetings
                             WHERE meeting_date >= ? AND first_seen <= ?""", (day, day), dates=("meeting_date",))
    ops = data.query("""SELECT date, company, nature FROM corporate_notices WHERE kind = 'operation'
                        AND date IN (SELECT DISTINCT date FROM corporate_notices WHERE date <= ?
                                     ORDER BY date DESC LIMIT ?)""", (day, NOTICE_LOOKBACK))
    return meetings, ops


def upcoming(v: str, day: str) -> pd.DataFrame:
    """Events after `day` as known on that day: date, company, label, kind, boc (bulletin announcing it)."""
    meetings, ops = _upcoming_raw(v, day)
    rows = []
    m = meetings.assign(cancelled=(meetings["nature"].fillna("") + meetings["place"].fillna(""))
                        .str.contains("annul", case=False))
    m = m.sort_values("cancelled", ascending=False).drop_duplicates(["company", "meeting_date"])
    for r in m.itertuples():
        label = meeting_label(r.nature.split("(")[0] if r.nature else "")
        rows.append({"date": r.meeting_date, "company": r.company, "kind": "meeting",
                     "label": label + (f" — {t('cancelled')}" if r.cancelled else ""), "seen": r.last_seen})
    # one row per announcement: the same text is repeated in every bulletin until the event, sometimes with a
    # garbled company name; keep the latest mention with a readable company
    ops = ops.dropna(subset=["nature"]).assign(
        clean=lambda o: o["company"].fillna("").str.len().gt(0) & ~o["company"].fillna("").str.contains(_GARBLED))
    ops = ops.sort_values(["clean", "date"]).drop_duplicates("nature", keep="last")
    ops.loc[~ops["clean"], "company"] = ""
    for r in ops.itertuples():
        when = event_date(r.nature)
        if when is None or when < dt.date.fromisoformat(day):
            continue
        kind, label = describe_operation(r.nature)
        rows.append({"date": pd.Timestamp(when), "company": r.company, "kind": kind, "label": label,
                     "seen": r.date})
    if not rows:
        return pd.DataFrame(columns=["date", "company", "kind", "label", "seen"])
    out = pd.DataFrame(rows)
    out["seen"] = pd.to_datetime(out["seen"]).clip(upper=pd.Timestamp(day))
    return out.sort_values(["date", "company"]).reset_index(drop=True)


# ---------------------------------------------------------------- written summary

def _plural(n: int, key: str) -> str:
    return t(f"{key}_{'one' if n == 1 else 'many'}", n=n)


def summary(v: str, day: str) -> str:
    """A few sentences describing the session, in the current language (markdown)."""
    hl = data.headline(v, day).set_index("index_name")
    eq = data.equities_on(v, day)
    parts = []
    if "BRVM COMPOSITE" in hl.index:
        c = hl.loc["BRVM COMPOSITE"]
        ch = c["change_pct"]
        verb = "sum_flat" if ch is None or abs(ch) < 0.005 else ("sum_up" if ch > 0 else "sum_down")
        text = t(verb, pct=fmt_pct(abs(ch) if ch is not None else 0, signed=False), value=fmt_num(c["value"], 2))
        if "BRVM 30" in hl.index:
            text += t("sum_b30", pct=fmt_pct(hl.loc["BRVM 30", "change_pct"]))
        parts.append(text + ". " + t("sum_ytd", pct=fmt_pct(c["ytd_pct"])))
    up, down, flat = data.breadth(v, day)
    parts.append(t("sum_breadth", up=_plural(up, "n_up"), down=_plural(down, "n_down"), flat=_plural(flat, "n_flat")))
    value = data.equity_value(v, day)
    if value:
        hist = data.equity_value_history(v)
        past = hist[hist.index < pd.Timestamp(day)].tail(AVG_SESSIONS)
        text = t("sum_value", amount=fmt_amount(value))
        if len(past) >= 20 and past.mean() > 0:
            diff = (value / past.mean() - 1) * 100
            text += ", " + t("sum_value_above" if diff >= 0 else "sum_value_below",
                             pct=fmt_pct(abs(diff), 0, signed=False))
        text += "."
        traded = eq[eq["value"] > 0]
        if len(traded) and traded["value"].sum() > 0:
            top = traded.loc[traded["value"].idxmax()]
            share = top["value"] / traded["value"].sum() * 100
            if share >= 25:
                text += " " + t("sum_top_share", pct=fmt_pct(share, 0, signed=False), name=top["name"])
        parts.append(text)
    movers = eq.dropna(subset=["change_pct"])
    best = movers[movers["change_pct"] > 0].nlargest(1, "change_pct")
    worst = movers[movers["change_pct"] < 0].nsmallest(1, "change_pct")
    if len(best) or len(worst):
        bits = []
        if len(best):
            bits.append(t("sum_best", name=best["name"].iloc[0], pct=fmt_pct(best["change_pct"].iloc[0])))
        if len(worst):
            bits.append(t("sum_worst", name=worst["name"].iloc[0], pct=fmt_pct(worst["change_pct"].iloc[0])))
        joined = (" ; " if lang() == "fr" else "; ").join(bits)
        parts.append(joined[0].upper() + joined[1:] + ".")
    return " ".join(parts)
