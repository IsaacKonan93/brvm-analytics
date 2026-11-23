"""Mutual funds (OPCVM: FCP / SICAV) net asset values, from the "VALEUR LIQUIDATIVE" pages.

Layout (2017-03-29 onwards):
  Société de gestion | Dépositaire | OPCVM | Catégorie | Valeur d'origine |
  VL précédente (valeur, date) | VL actuelle (valeur, date) | Date d'origine |
  Variation depuis l'origine % | Variation depuis la VL précédente %
grouped by publication frequency (QUOTIDIENNES / HEBDOMADAIRES / MENSUELLES ...). The manager
and depositary are printed on the first row of their group only and carried forward.
The older 2016-10..2017-03 layout (one column per fund) is not supported (logged).
"""

from __future__ import annotations

import datetime as dt
import re
import statistics
from collections import Counter

from ..pdfdoc import Document, Page, Word, norm
from ..values import parse_date, parse_number

_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
_NUMLIKE = re.compile(r"^[-+]?[\d][\d .,]*%?$|^ND$|^-$|^NC$")
_FREQ = re.compile(r"^(QUOTIDIENNES|HEBDOMADAIRES|MENSUELLES|TRIMESTRIELLES|BIMENSUELLES|DAILY|WEEKLY|MONTHLY|QUARTERLY)$")

# words that continue a manager / depositary name wrapped onto the next line
_CONT_WORDS = {"MANAGEMENT", "ASSET", "D'ACTIFS", "SA", "S.A.", "GESTION", "CAPITAL", "FINANCE", "FINANCES",
               "BOURSE", "SECURITIES", "INVESTMENT", "PARTNERS", "AFRICA", "CORPORATION", "CI", "SN", "SGI",
               "WEST", "&", "DE", "DES", "DU", "MANAGERS", "ADVISORY", "INVEST", "GROUP", "BANK", "AM"}

# words that normally end a manager / depositary name
_TERMINAL = {"MANAGEMENT", "SA", "S.A.", "GESTION", "FINANCES", "FINANCE", "AM", "SECURITIES", "CORPORATION",
             "BOURSE", "D'ACTIFS", "SGI", "INVEST", "CAPITAL", "PARTNERS"}

# numeric columns, left to right, anchored on header words
_NUM_COLS = [("origin_value", r"^ORIGINE$"), ("nav_prev", r"^VALEUR$"), ("nav_prev_date", r"^DATE$"),
             ("nav", r"^VALEUR$"), ("nav_date", r"^DATE$"), ("inception_date", r"^DATE$"),
             ("perf_origin_pct", r"^%$"), ("perf_period_pct", r"^%$")]


def _header(page: Page):
    """Header words of the fund table on this page, or None."""
    lines = page.lines
    for i, ln in enumerate(lines):
        t = norm(ln.text)
        if "OPCVM" in t.split() and ("DEPOSITAIRE" in t or "CATEGORIE" in t):
            # header lines around the 'OPCVM' line; data rows (they carry dates) are not header
            block = [l for l in lines if -14 <= l.yc - ln.yc <= 14
                     and not any(_DATE.match(w.text) for w in l.words)]
            return sorted((w for l in block for w in l.words), key=lambda w: w.xc), max(l.yc for l in block)
    return None


def _anchors(words: list[Word]) -> dict[str, float]:
    out, last = {}, -1e9
    for name, rx in _NUM_COLS:
        for w in words:
            if w.xc > last + 6 and re.match(rx, norm(w.text)):
                out[name] = w.xc
                last = w.xc
                break
    return out


def _parse_page(page: Page, loc: str, ref: dt.date, state: dict) -> list[dict]:
    h = _header(page)
    if not h:
        return []
    hwords, body_y = h
    anchors = _anchors(hwords)
    for w in hwords:  # the first frequency group heading can sit inside the header block
        if _FREQ.match(norm(w.text)):
            state["frequency"] = norm(w.text).title()
    cat_w = next((w for w in hwords if norm(w.text) in ("CATEGORIE", "CATEGORY")), None)
    if cat_w is None or len(anchors) < 6:
        state["warnings"].append(f"p{page.number} funds: header not recognised ({len(anchors)} anchors)")
        return []
    num_left = min(anchors.values()) - 22
    cat_left, cat_right = cat_w.x0 - 6, cat_w.x1 + 8

    body = [ln for ln in page.lines if ln.yc > body_y]
    # rows = lines carrying at least one date or ND in the numeric zone
    rows = [ln for ln in body if any((_DATE.match(w.text) or w.text == "ND") and w.x0 > num_left for w in ln.words)]
    if not rows:
        return []
    # left edge of the fund-name column = most common x0 of the first text word of a row
    firsts = [next((w.x0 for w in ln.words if w.x1 < cat_left and not _NUMLIKE.match(w.text)), None) for ln in rows]
    firsts = [round(x) for x in firsts if x is not None]
    fund_left = Counter(firsts).most_common(1)[0][0] if firsts else cat_left - 100
    # left edge of the depositary column: most common x0 of a word that starts a new field between
    # the manager column and the fund column
    dep_cands = []
    for ln in body:
        ws = [w for w in ln.words if w.x1 < fund_left - 2]
        for a, b in zip(ws, ws[1:]):
            if b.x0 - a.x1 > 2.5:
                dep_cands.append(round(b.x0))
    dep_left = Counter(dep_cands).most_common(1)[0][0] if dep_cands else None

    out = []
    for ln in body:
        t = norm(ln.text)
        if _FREQ.match(t):
            state["frequency"] = t.title()
            continue
        if t.startswith(("TOTAL", "CATEGORIES", "LEGENDE", "ND:", "A:", "OCT:", "OMLT:", "C:", "D:")):
            continue
        mgr = [w for w in ln.words if w.x1 < fund_left - 2 and (dep_left is None or w.x0 < dep_left - 2)]
        dep = [w for w in ln.words if w.x1 < fund_left - 2 and dep_left is not None and w.x0 >= dep_left - 2]
        is_row = ln in rows
        for key, ws in (("manager", mgr), ("depositary", dep)):
            if not ws:
                continue
            txt = " ".join(w.text for w in ws)
            prev_y = state.get(key + "_y")
            # a name wrapped on the next line: continuation word, or a line with no fund row
            prev_last = norm(state.get(key) or "").split(" ")[-1]
            starts_cont = norm(ws[0].text) in _CONT_WORDS
            wrapped = prev_y is not None and 0 < ln.yc - prev_y < 11 and (
                starts_cont or (not is_row and prev_last not in _TERMINAL))
            if wrapped and state.get(key):
                state[key] = f"{state[key]} {txt}"
                for r in state.get(key + "_rows", []):  # rows already given the truncated name
                    r[key] = state[key]
            else:
                state[key] = txt
                state[key + "_rows"] = []
            state[key + "_y"] = ln.yc
        if not is_row:
            continue
        fund = [w for w in ln.words if fund_left - 2 <= w.x0 and w.x1 <= cat_left]
        cat = [w for w in ln.words if cat_left <= w.x0 and w.x1 <= cat_right + 4 and not _NUMLIKE.match(w.text)]
        cells: dict[str, list[str]] = {}
        for w in ln.words:
            if w.x0 > num_left and (_NUMLIKE.match(w.text) or _DATE.match(w.text) or re.match(r"^[A-Za-z]{3,4}\.?$", w.text)):
                k = min(anchors, key=lambda a: abs(anchors[a] - w.xc))
                cells.setdefault(k, []).append(w.text)
        c = {k: " ".join(v) for k, v in cells.items()}
        name = " ".join(w.text for w in fund).strip().strip('"')
        if not name:
            continue
        out.append({
            "fund_name": re.sub(r"\s+", " ", name.replace('"', "")), "manager": state.get("manager"),
            "depositary": state.get("depositary"), "category": " ".join(w.text for w in cat) or None,
            "origin_value": parse_number(c.get("origin_value"), loc), "nav_prev": parse_number(c.get("nav_prev"), loc),
            "nav_prev_date": parse_date(c.get("nav_prev_date"), ref), "nav": parse_number(c.get("nav"), loc),
            "nav_date": parse_date(c.get("nav_date"), ref), "inception_date": parse_date(c.get("inception_date"), ref),
            "inception_raw": c.get("inception_date"), "perf_origin_pct": parse_number(c.get("perf_origin_pct"), loc),
            "perf_period_pct": parse_number(c.get("perf_period_pct"), loc), "frequency": state.get("frequency"),
        })
        state.setdefault("manager_rows", []).append(out[-1])
        state.setdefault("depositary_rows", []).append(out[-1])
    return out


def parse_funds(doc: Document, date: dt.date) -> dict:
    state: dict = {"warnings": []}
    funds: dict[str, dict] = {}
    pages = [p for p in doc.pages if "LIQUIDATIVE" in norm(p.text)]
    for page in pages:
        for r in _parse_page(page, doc.locale, date, state):
            r["date"] = date.isoformat()
            if r["fund_name"] in funds:
                # same name under two managers: keep both, qualified by manager
                r["fund_name"] = f"{r['fund_name']} [{r['manager']}]"
            funds.setdefault(r["fund_name"], r)
    if pages and not funds:
        state["warnings"].append("funds pages found but no fund row read (old layout?)")
    return {"fund_navs": list(funds.values()), "warnings": state["warnings"]}
