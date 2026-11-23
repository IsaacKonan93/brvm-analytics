"""Parsing of BOC cell values: numbers, percentages and dates in French or English formats.

Every parser returns None for an empty / not-available cell. `cell_flag` extracts the status
markers the BOC prints instead of a value (NC = non coté, SP = suspendu, ND = non disponible...).
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata

# Markers printed instead of a value.
FLAGS = {
    "NC": "NC",        # non coté (no trade)
    "NT": "NC",        # not traded (English edition)
    "SP": "SP",        # suspendu
    "ND": "ND",        # non disponible
    "NA": "ND",
    "N/A": "ND",
    "EX-C": "EX-C",    # ex-coupon
    "EX-D": "EX-D",    # ex-droit / ex-dividende
    "VAL-T": "VAL-T",  # valeur théorique
    "(D)": "D",        # ex-dividende marker
    "(V)": "V",
}
_EMPTY = {"", "-", "--", "—", "–", "/", "ND", "NC", "NT", "SP", "NA", "N/A", "-%", "- %"}


def _clean(s: str | None) -> str:
    if s is None:
        return ""
    s = s.replace(" ", " ").replace(" ", " ").strip()
    return re.sub(r"\s+", " ", s)


def cell_flag(s: str | None) -> str | None:
    t = _clean(s).upper()
    for k, v in FLAGS.items():
        if t == k or t.startswith(k + " ") or t.endswith(" " + k):
            return v
    return None


def parse_number(s: str | None, locale: str = "fr", comma_thousands: bool = False) -> float | None:
    """'1 234,56' -> 1234.56 (fr), '1,234.56' -> 1234.56 (en). Returns None if not a number.

    comma_thousands: treat '12,345' as 12345 even in a French document (order-book prices).
    """
    t = _clean(s)
    if t.upper() in _EMPTY:
        return None
    t = t.replace("%", "").replace(" ", "").replace("'", "")
    t = t.rstrip(",.")  # '1 806,' (number split over two lines, first half)
    if not t or not re.fullmatch(r"[-+]?[\d.,]+", t):
        return None
    neg = t.startswith("-")
    t = t.lstrip("+-")
    if "," in t and "." in t:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        thou = "." if dec == "," else ","
        t = t.replace(thou, "").replace(dec, ".")
    elif "," in t:
        if (comma_thousands or locale == "en") and re.fullmatch(r"\d{1,3}(,\d{3})+", t):
            t = t.replace(",", "")
        elif t.count(",") > 1:
            t = t.replace(",", "")
        else:
            t = t.replace(",", ".")
    elif "." in t:
        if re.fullmatch(r"\d{1,3}(\.\d{3}){2,}", t):  # 1.234.567
            t = t.replace(".", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def parse_int(s: str | None, locale: str = "fr") -> int | None:
    v = parse_number(s, locale, comma_thousands=True)
    return None if v is None else int(round(v))


def parse_pct(s: str | None, locale: str = "fr") -> float | None:
    """'-7,45 %' -> -7.45 (percent units, not a fraction)."""
    return parse_number(s, locale)


# ---------------------------------------------------------------- dates

_MONTHS = {
    # French (accent-free, lower case, without trailing dot)
    "janv": 1, "janvier": 1, "jan": 1, "fev": 2, "fevr": 2, "fevrier": 2, "mars": 3, "mar": 3,
    "avr": 4, "avril": 4, "mai": 5, "juin": 6, "juil": 7, "juillet": 7, "aout": 8,
    "sept": 9, "sep": 9, "septembre": 9, "oct": 10, "octobre": 10, "nov": 11, "novembre": 11,
    "dec": 12, "decembre": 12,
    # English
    "feb": 2, "february": 2, "january": 1, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _year(y: str) -> int:
    n = int(y)
    return n + (2000 if n < 70 else 1900) if n < 100 else n


def parse_date(s: str | None, ref: dt.date | None = None) -> str | None:
    """Parse BOC date cells to ISO 'YYYY-MM-DD'.

    Handles '18-août-25', '10-sept.-25', '17 May 24', '29/10/2025', '11/03/19', '2025-10-30',
    and day-month without a year ('11-oct', '06-mars') using `ref` (the bulletin date) to pick
    the next occurrence. Returns None for anything else (e.g. coupon periods '28 mars/28 sep.').
    """
    t = _strip_accents(_clean(s)).lower()
    if not t or t in _EMPTY or "/" in t and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", t):
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return t
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", t)
    if m:
        d, mo, y = int(m[1]), int(m[2]), _year(m[3])
        return _iso(y, mo, d)
    m = re.fullmatch(r"(\d{1,2})[\s\-.]+([a-z]+)\.?(?:[\s\-.]+(\d{2,4}))?", t)
    if m and m[2].rstrip(".") in _MONTHS:
        d, mo = int(m[1]), _MONTHS[m[2].rstrip(".")]
        if m[3]:
            return _iso(_year(m[3]), mo, d)
        if ref:
            cand = _iso(ref.year, mo, d)
            if cand and cand < ref.isoformat():
                cand = _iso(ref.year + 1, mo, d)
            return cand
    return None


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return dt.date(y, m, d).isoformat()
    except ValueError:
        return None
