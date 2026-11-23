"""Corporate events: 'OPERATIONS EN COURS', 'AVIS', 'COMMUNIQUES' blocks and the shareholder
meetings table ('Société | Nature | Date | Heure | Lieu').

All these blocks are left-aligned text columns under their header words: a column starts at
the x of its header word. A new row starts on a line that has a reference number (N°) or, for
blocks without a N° column, a first-column value after a vertical gap; other lines are wrapped
text appended to the current row.
"""

from __future__ import annotations

import datetime as dt
import re

from ..pdfdoc import Document, Line, Page, norm
from ..values import parse_date

_BLOCKS = {
    "OPERATIONS EN COURS": "operation", "ONGOING OPERATIONS": "operation", "OPERATIONS IN PROGRESS": "operation",
    "AVIS": "avis", "NOTICES": "avis", "NOTICE": "avis",
    "COMMUNIQUES": "communique", "PRESS RELEASES": "communique", "RELEASES": "communique",
}
_HDR_WORDS = {
    "company": ("EMETTEUR", "ENTITE", "ISSUER", "ENTITY", "SOCIETE", "COMPANY"),
    "reference": ("N°", "NO", "N"),
    "nature": ("NATURE", "OPERATION", "TYPE"),
    "subject": ("OBJET", "SUBJECT", "PURPOSE"),
}
_STOP = re.compile(r"^(OPERATIONS EN COURS|AVIS|COMMUNIQUES|ASSEMBLEES|ANNEE\s*:|MARCHE DES|LEGENDE|OPCVM|"
                   r"ONGOING|NOTICES|PRESS RELEASES|GENERAL MEETINGS|YEAR\s*:)")


def _columns(hdr: Line) -> dict[str, float]:
    cols = {}
    for w in hdr.words:
        t = norm(w.text)
        for name, keys in _HDR_WORDS.items():
            if t in keys and name not in cols:
                cols[name] = w.x0
    return cols


def _assign(ln: Line, cols: dict[str, float]) -> dict[str, list[str]]:
    order = sorted(cols.items(), key=lambda kv: kv[1])
    out: dict[str, list[str]] = {}
    for w in ln.words:
        name = order[0][0]
        for n, x in order:
            if w.x0 >= x - 4:
                name = n
        out.setdefault(name, []).append(w.text)
    return out


def _blocks(doc: Document, date: str) -> list[dict]:
    out: list[dict] = []
    for page in doc.pages:
        lines = page.lines
        i = 0
        while i < len(lines):
            t = norm(lines[i].text)
            kind = _BLOCKS.get(t)
            if not kind or i + 1 >= len(lines):
                i += 1
                continue
            hdr = lines[i + 1]
            cols = _columns(hdr)
            if "company" not in cols or len(cols) < 2:
                i += 1
                continue
            seq, cur, last_y = 0, None, None
            j = i + 2
            while j < len(lines):
                ln = lines[j]
                tt = norm(ln.text)
                if _STOP.match(tt) or (ln.y > page.height - 30 and re.fullmatch(r"\d+", tt)):
                    break
                cells = _assign(ln, cols)
                has_ref = bool(cells.get("reference")) and any(re.search(r"\d", x) for x in cells["reference"])
                new_row = has_ref if "reference" in cols else (
                    bool(cells.get("company")) and (last_y is None or ln.yc - last_y > 10))
                if new_row or cur is None:
                    seq += 1
                    cur = {"date": date, "kind": kind, "seq": seq, "company": None, "reference": None,
                           "nature": None, "subject": None}
                    out.append(cur)
                for k, v in cells.items():
                    txt = " ".join(v)
                    cur[k] = f"{cur[k]} {txt}" if cur.get(k) else txt
                last_y = ln.yc
                j += 1
            i = j
    for r in out:
        for k in ("company", "reference", "nature", "subject"):
            if r[k]:
                r[k] = re.sub(r"\s+", " ", r[k]).replace("’", "'").strip()
    return out


# ---------------------------------------------------------------- shareholder meetings

_AGM_HDR = re.compile(r"^(SOCIETE|COMPANY)\s+NATURE\s+DATE\s+(HEURE|TIME|HOUR)\s+(LIEU|PLACE|VENUE)")
_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")


def _meetings(doc: Document, date: str) -> list[dict]:
    out: list[dict] = []
    cols = None
    for page in doc.pages:
        for ln in page.lines:
            t = norm(ln.text)
            if _AGM_HDR.match(t):
                xs = {norm(w.text): w.x0 for w in ln.words}
                cols = {"company": xs.get("SOCIETE", xs.get("COMPANY", 0)), "nature": xs["NATURE"],
                        "meeting_date": xs["DATE"], "time": xs.get("HEURE", xs.get("TIME", xs.get("HOUR"))),
                        "place": xs.get("LIEU", xs.get("PLACE", xs.get("VENUE")))}
                continue
            if cols is None:
                continue
            if _STOP.match(t) and not t.startswith(("ANNEE", "YEAR")) or "LIQUIDATIVE" in t or t.startswith("OPCVM"):
                cols = None
                continue
            if t.startswith(("ANNEE", "YEAR")) or (ln.y > page.height - 30 and re.fullmatch(r"\d+", t)):
                continue
            order = sorted(cols.items(), key=lambda kv: kv[1])
            cells: dict[str, list[str]] = {}
            for w in ln.words:
                name = order[0][0]
                for n, x in order:
                    if w.x0 >= x - 4:
                        name = n
                cells.setdefault(name, []).append(w.text)
            d = " ".join(cells.get("meeting_date", []))
            if _DATE.match(d):
                out.append({"_page": page.number, "_y": ln.yc, "date": date, "company": " ".join(cells.get("company", [])),
                             "nature": " ".join(cells.get("nature", [])),
                             "meeting_date": parse_date(d), "time": " ".join(cells.get("time", [])) or None,
                             "place": " ".join(cells.get("place", [])) or None})
            elif out and out[-1].get("_page") == page.number and 0 < ln.yc - out[-1]["_y"] < 20:
                r = out[-1]  # wrapped company name / place, right below its row
                if cells.get("company"):
                    r["company"] = f"{r['company']} {' '.join(cells['company'])}"
                if cells.get("place"):
                    r["place"] = f"{r['place'] or ''} {' '.join(cells['place'])}".strip()
                r["_y"] = ln.yc
            elif out and out[-1].get("_page") == page.number and ln.yc - out[-1]["_y"] > 60:
                cols = None  # a large gap: the table has ended (annex pages follow)
    for r in out:
        r.pop("_page", None)
        r.pop("_y", None)
        r["company"] = re.sub(r"\s+", " ", r["company"]).strip()
        if r["place"]:
            r["place"] = r["place"].replace("’", "'")
    return [r for r in out if r["company"] and r["meeting_date"] and len(r["company"]) <= 80]


# Some bulletins embed fonts without a usable character map: the text comes out shifted
# ('$)5,&$ */2%$/' for 'AFRICA GLOBAL'). Such tokens are detected and dropped.
_GARBLED = re.compile(r"[$%&*@#]|^[A-Za-z]\d|[A-Za-z]\)[A-Za-z]|\d[A-Za-z]{2}|[A-Za-z]{2}\d|^[^A-Za-z0-9(]")


def _garbled(token: str) -> bool:
    return bool(_GARBLED.search(token)) and token not in ("&",)


def parse_events(doc: Document, date: dt.date) -> dict:
    d = date.isoformat()
    warns: list[str] = []
    meetings = []
    for m in _meetings(doc, d):
        if any(_garbled(t) for t in m["company"].split()):
            warns.append(f"meeting skipped, unreadable company name (font without character map): {m['company']!r}")
            continue
        m["nature"] = " ".join(t for t in (m["nature"] or "").split() if not _garbled(t))
        meetings.append(m)
    return {"corporate_notices": _blocks(doc, d), "meeting_mentions": meetings, "warnings": warns}
