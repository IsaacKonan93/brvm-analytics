"""Indices and market statistics (front pages of the BOC).

* index_values: headline indices (BRVM 10 / COMPOSITE / 30 / PRESTIGE / PRINCIPAL...), the
  compartment and sector index tables, and - for the 2016-2017 layout - the sector indices
  printed in the group headings of the quote table ("SECTEUR - INDUSTRIE 155,94 points -0,62%").
* market_stats: key/value figures (capitalisation, volumes, number of rising/falling stocks,
  market PER and yield, liquidity ratios...). Keys are documented in EXTRACTION.md.
"""

from __future__ import annotations

import datetime as dt
import re

from ..pdfdoc import Document, Line, Page, Word, norm
from ..values import parse_int, parse_number

_NUM = re.compile(r"^[-+]?\d[\d .,]*%?$")
_PCT = re.compile(r"%$")


def _is_num(w: Word) -> bool:
    return bool(_NUM.match(w.text.strip())) or w.text.strip() == "-"


def index_name(raw: str) -> str:
    """'BRVM-PRESTIGE' / 'BRVM - SERVICES PUBLICS (**)' / 'BRVM Composite' -> 'BRVM PRESTIGE' ..."""
    t = re.sub(r"\([^)]*\)?", "", norm(raw))  # footnote markers '(**)', '( **)', a dangling '('
    t = t.replace("*", "")
    t = re.sub(r"^BRVM\s*-?\s*", "BRVM ", t)
    t = re.sub(r"\s*-\s*", " - ", t).replace("BRVM - ", "BRVM ")
    t = re.sub(r"\s+", " ", t).strip()
    if t.startswith("BRVM "):  # English edition sector names -> French names
        from .quotes import SECTOR_EN_FR
        rest = t[5:]
        t = "BRVM " + SECTOR_EN_FR.get(rest, rest)
    return t


# ---------------------------------------------------------------- headline indices

_HEADLINE = re.compile(r"^BRVM ?(10|30|COMPOSITE|PRESTIGE|PRINCIPAL|C)$")


def _headline(pages: list[Page], loc: str, date: str) -> list[dict]:
    """Headline indices: 'BRVM COMPOSITE 344,36' with the day and year-to-date changes printed
    in the lines below, in the same column (each % is given to the nearest headline value)."""
    out, seen = [], set()
    for page in pages[:2]:
        lines = page.lines
        found: list[tuple[str, Word, int, Word]] = []  # (name, value word, line index, name word)
        for i, ln in enumerate(lines):
            ws = ln.words
            for j, w in enumerate(ws[:-1]):
                if norm(w.text) != "BRVM":
                    continue
                nxt = norm(ws[j + 1].text)
                if not _HEADLINE.match(f"BRVM {nxt}") or nxt == "C":
                    continue
                # value: first number to the right, within 140 pt, on the same line
                val_w = next((x for x in ws[j + 2:] if _is_num(x) and not _PCT.search(x.text)
                              and x.x0 - ws[j + 1].x1 < 140), None)
                name = index_name(f"BRVM {nxt}")
                if val_w is None or name in seen:
                    continue
                seen.add(name)
                found.append((name, val_w, i, w))
        for name, val_w, i, name_w in found:
            y0 = lines[i].yc
            pcts = []
            for ln2 in lines[i + 1:]:
                if ln2.yc - y0 > 75:
                    break
                for x in ln2.words:
                    if not _PCT.search(x.text):
                        continue
                    # headlines at the same height compete for this %: keep it if we are the nearest
                    rivals = [f for f in found if abs(lines[f[2]].yc - y0) < 3]
                    best = min(rivals, key=lambda f: abs(f[1].x1 - x.x1))
                    if best[0] == name and abs(x.x1 - val_w.x1) < 60:
                        pcts.append(parse_number(x.text, loc))
            out.append({"date": date, "index_name": name, "family": "headline",
                        "value": parse_number(val_w.text, loc),
                        "change_pct": pcts[0] if pcts else None, "ytd_pct": pcts[1] if len(pcts) > 1 else None,
                        "nb_companies": None, "volume": None, "value_traded": None, "avg_per": None, "base": None})
    return out


# ---------------------------------------------------------------- index tables

def _index_tables(pages: list[Page], loc: str, date: str) -> list[dict]:
    out = []
    for page in pages[:3]:
        family, base = None, None
        for ln in page.lines:
            t = norm(ln.text)
            if t.startswith("INDICES PAR COMPARTIMENT") or "COMPARTMENT INDICES" in t:
                family = "compartment"
            elif t.startswith("INDICES SECTORIELS NOUVEAUX") or "NEW SECTOR" in t:
                family = "sector_new"
            elif t.startswith("INDICES SECTORIELS") or "SECTOR INDICES" in t or "SECTORAL INDICES" in t:
                family = "sector"
            m = re.match(r"^BASE\s*=\s*100\s*(AU|ON|AS OF)?\s*(.+?)\s+(NOMBRE|NUMBER|NB)\b", t)
            if m:
                base = m[2].title()
                continue
            ws = ln.words
            if not ws or norm(ws[0].text) not in ("BRVM", "BRVM-PRESTIGE", "BRVM-PRINCIPAL") and not norm(ws[0].text).startswith("BRVM-"):
                continue
            first_digit = next((w.x0 for w in ws if re.search(r"\d", w.text)), None)
            if first_digit is None:
                continue
            nums = [w for w in ws if _is_num(w) and w.x0 >= first_digit]  # a '-' inside the name is not a value
            if len(nums) < 5 or family is None:
                continue
            name = index_name(" ".join(w.text for w in ws if w.x0 < first_digit))
            if re.search(r"SOCIETE|CAPITAL DE|ANONYME|SIEGE", name) or len(name.split()) > 6:
                continue  # BRVM's own address line, not an index
            pct = [w for w in nums if _PCT.search(w.text)]
            plain = [w for w in nums if not _PCT.search(w.text)]
            rec = {"date": date, "index_name": name, "family": family, "base": base,
                   "nb_companies": parse_int(plain[0].text, loc) if plain else None,
                   "value": parse_number(plain[1].text, loc) if len(plain) > 1 else None,
                   "change_pct": parse_number(pct[0].text, loc) if pct else None,
                   "ytd_pct": parse_number(pct[1].text, loc) if len(pct) > 1 else None,
                   "volume": parse_int(plain[2].text, loc) if len(plain) > 2 else None,
                   "value_traded": parse_int(plain[3].text, loc) if len(plain) > 3 else None,
                   "avg_per": parse_number(plain[4].text, loc) if len(plain) > 4 else None}
            if family == "sector" and base and "2025" in base:
                rec["family"] = "sector_new"  # 2026+: the new sector indices under a plain heading
            out.append(rec)
    return out


_GROUP_INDEX = re.compile(
    r"^(SECTEUR\s*-\s*(?P<s>.+?)|(?P<a>AUTRES SECTEURS)|COMPARTIMENT\s+(?P<c>[A-Z]+)|(?P<e>.+?) - SECTOR)\s+"
    r"(?P<v>[\d .,]+?)\s*POINTS\s+(?P<p>[-+]?[\d.,]+ ?%)")


def _group_heading_indices(pages: list[Page], loc: str, date: str) -> list[dict]:
    """Sector/compartment index printed in the quote-table group headings (all layouts)."""
    out = []
    for page in pages:
        for ln in page.lines:
            m = _GROUP_INDEX.match(norm(ln.text))
            if not m:
                continue
            if m["c"]:
                name, family = f"BRVM {m['c']}", "compartment"
            else:
                from .quotes import SECTOR_EN_FR
                sec = (m["s"] or m["a"] or m["e"]).strip()
                name, family = f"BRVM {SECTOR_EN_FR.get(sec, sec)}", "sector"
            out.append({"date": date, "index_name": index_name(name), "family": family,
                        "value": parse_number(m["v"], loc), "change_pct": parse_number(m["p"], loc),
                        "ytd_pct": None, "nb_companies": None, "volume": None, "value_traded": None,
                        "avg_per": None, "base": None})
    return out


# ---------------------------------------------------------------- market statistics

STAT_KEYS = [
    # (regex on the label (upper case, accents and parentheses removed), key, side-dependent)
    (r"^CAPITALI[SZ]ATION", "market_cap", True),
    (r"^VOLUME (ECHANGE|TRADED)|^VOLUME$", "volume", True),
    (r"^VALEUR TRANSIGEE|^VALUE TRADED|^TRADED VALUE|^VALUE$", "value", True),
    (r"^NOMBRE DE TITRES TRANSIGES|^NUMBER OF (SECURITIES|STOCKS|SHARES)( TRADED)?$", "nb_traded", True),
    (r"EN HAUSSE|RISING|GAINERS|^GAINS$", "nb_up", True),
    (r"EN BAISSE|FALLING|DECLINERS|^LOSSES$", "nb_down", True),
    (r"INCHANGES|UNCHANGED|^FLAT$", "nb_unchanged", True),
    (r"^PER MOYEN DU MARCHE|^MARKET (AVERAGE )?PER|^AVERAGE PER|^PER$", "market_per", False),
    (r"^TAUX DE RENDEMENT MOYEN|AVERAGE YIELD|MARKET YIELD|^RATE OF YIE?L?D", "market_yield", False),
    (r"^TAUX DE RENTABILITE MOYEN|AVERAGE RETURN|PROFITABILITY", "market_return", False),
    (r"^NOMBRE DE SOCIETES COTEES|LISTED COMPANIES|^SECURITIES LISTED", "nb_listed_companies", False),
    (r"^NOMBRE DE LIGNES OBLIGATAIRES|BOND LINES|LISTED BONDS|^BONDS LISTED", "nb_bond_lines", False),
    (r"^VOLUME MOYEN ANNUEL PAR SEANCE|AVERAGE (ANNUAL )?VOLUME PER|^YEARLY VOLUME", "avg_volume_per_session_ytd", False),
    (r"^VALEUR MOYENNE ANNUELLE PAR SEANCE|AVERAGE (ANNUAL )?VALUE PER|^YEARLY VALUE", "avg_value_per_session_ytd", False),
    (r"^RATIO MOYEN DE LIQUIDITE|LIQUIDITY RATIO", "liquidity_ratio", False),
    (r"^RATIO MOYEN DE SATISFACTION|SATISFACTION RATIO", "satisfaction_ratio", False),
    (r"^RATIO MOYEN DE TENDANCE|TREND RATIO|TENDENCY RATIO", "trend_ratio", False),
    (r"^RATIO MOYEN DE COUVERTURE|COVERAGE RATIO", "coverage_ratio", False),
    (r"^TAUX DE ROTATION|TURNOVER", "turnover_rate", False),
    (r"^PRIME DE RISQUE|RISK PREMIUM|PREMIUM RISK", "risk_premium", False),
    (r"^NOMBRE DE SGI|BROKER|SGI", "nb_brokers", False),
]


def _stat_key(label: str) -> tuple[str, bool] | None:
    t = norm(label)
    t = re.sub(r"\(.*?\)", "", t).replace("(**)", "").strip()
    for rx, key, sided in STAT_KEYS:
        if re.search(rx, t):
            return key, sided
    return None


def _segments(words: list[Word]) -> list[tuple[list[Word], list[Word]]]:
    """Split a line into (label words, number words) segments: 'Label 12 3,4 % Label2 5'."""
    segs: list[tuple[list[Word], list[Word]]] = []
    for w in words:
        if _is_num(w) and not re.fullmatch(r"\(?\*+\)?", w.text):
            if segs:
                segs[-1][1].append(w)
        elif w.text in ("(**)", "(*)", "&", ":"):
            continue
        else:
            if not segs or segs[-1][1]:
                segs.append(([w], []))
            else:
                segs[-1][0].append(w)
    return [s for s in segs if s[1]]


def _market_stats(pages: list[Page], loc: str, date: str) -> list[dict]:
    out: dict[str, dict] = {}
    for page in pages[:2]:
        split_x = None  # x of the 'Obligations' column header -> left = equities, right = bonds
        for ln in page.lines:
            t = norm(ln.text)
            if re.match(r"^(ACTIONS|EQUITIES)\b.*\b(OBLIGATIONS|BONDS)\b", t):
                split_x = next(w.x0 for w in ln.words if norm(w.text) in ("OBLIGATIONS", "BONDS"))
                continue
            if t.startswith(("PLUS FORTES", "TOP ", "INDICES", "BASE", "TITRES")):
                split_x = None if t.startswith(("PLUS FORTES", "INDICES")) else split_x
            for labels, nums in _segments(ln.words):
                label = " ".join(w.text for w in labels)
                found = _stat_key(label)
                if not found:
                    continue
                key, sided = found
                if sided:
                    if split_x is None:
                        continue
                    key = ("bond_" if labels[0].x0 >= split_x - 5 else "equity_") + key
                if key in out:
                    continue
                vals = [w for w in nums if not _PCT.search(w.text)]
                pcts = [w for w in nums if _PCT.search(w.text)]
                if not vals:
                    continue
                out[key] = {"date": date, "key": key, "value": parse_number(vals[0].text, loc), "unit": None,
                            "raw": " ".join(w.text for w in nums)}
                if pcts:
                    out[key + "_change_pct"] = {"date": date, "key": key + "_change_pct",
                                                "value": parse_number(pcts[0].text, loc), "unit": "%",
                                                "raw": pcts[0].text}
    # 2016-2017 layout: capitalisations in billions on the front page
    if pages:
        txt = norm(pages[0].text)
        for side, key in (("ACTIONS", "equity_market_cap"), ("OBLIGATIONS", "bond_market_cap")):
            m = re.search(side + r"\s*:\s*([\d ]+[.,]\d+)", txt)
            if m and key not in out:
                v = parse_number(m[1], loc)
                out[key] = {"date": date, "key": key, "value": v * 1e9 if v is not None else None,
                            "unit": "FCFA", "raw": f"{m[1]} milliards"}
    for r in out.values():
        if r["unit"] is None:
            r["unit"] = "%" if r["key"].endswith(("_pct", "_yield", "_return", "_rate", "_premium")) else None
    return list(out.values())


def parse_market(doc: Document, date: dt.date) -> dict:
    d = date.isoformat()
    loc = doc.locale
    idx: dict[tuple[str, str], dict] = {}
    for rec in _index_tables(doc.pages, loc, d) + _headline(doc.pages, loc, d) + _group_heading_indices(doc.pages, loc, d):
        idx.setdefault((rec["family"], rec["index_name"]), rec)  # first source wins
    warns = []
    if not any(r["family"] == "headline" for r in idx.values()):
        warns.append("no headline index found on the front page")
    return {"index_values": list(idx.values()), "market_stats": _market_stats(doc.pages, loc, d), "warnings": warns}
