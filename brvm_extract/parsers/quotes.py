"""Quote tables: equities, rights, bonds and the order book (best limits at the close).

Every table is located by its header (a line containing "Symbole") and classified by the
header words; the column layout (old 2016-2017 layout vs. 2017-12-19+ layout) is chosen from
the header too, not from the date. See EXTRACTION.md for the column meanings.
"""

from __future__ import annotations

import datetime as dt
import re

from ..columns import Col, Header, TableResult, TableSpec, find_header, header_words, read_table
from ..pdfdoc import Document, Page, norm
from ..values import cell_flag, parse_date, parse_int, parse_number

# ---------------------------------------------------------------- column specs
# Header regexes are matched against single header words (upper case, accents removed),
# searched left to right.

EQ_NEW = [
    Col("prev_close", r"^(PRECEDENT|PREVIOUS)$"), Col("open", r"^(OUV|OPEN)"), Col("close", r"^(CLOT|CLOS)"),
    Col("change_pct", r"^(JOUR|VARIATION|DAILY)$", "pct", min_gap=12), Col("volume", r"^VOLUME$", "int"),
    Col("value", r"^(VALEUR|VALUE)$", "int"), Col("ref_price", r"^REFERENCE$"),
    Col("ytd_pct", r"^(PRECEDENTE|L'ANNEE|VARIATION|ANNUAL|YEAR)$", "pct"), Col("div_amount", r"^(MONTANT|INCOME)$"),
    Col("div_date", r"^DATE$", "date"), Col("net_yield", r"^(RDT|YIELD)", "pct"), Col("per", r"^PER$"),
]
EQ_OLD = [
    Col("volume", r"^VOLUME$", "int"), Col("value", r"^(VALEUR|VALUE)$", "int"), Col("prev_close", r"^(PRECEDENT|PREVIOUS)$"),
    Col("open", r"^(OUV|OPEN)"), Col("close", r"^(CLOT|CLOS)"), Col("avg_price", r"^(MOY|AVG|AVERAGE)"),
    Col("change_pct", r"^(VARIATION|DAILY|CHANGE)$", "pct"), Col("ytd_pct", r"^(VARIATION|L'ANNEE|\(31/12|ANNUAL|YEAR)", "pct"),
    Col("ref_price", r"^REFERENCE$"), Col("limit_low", r"^(BAS|LOW)$"), Col("limit_high", r"^(HAUT|HIGH)$"),
    Col("div_amount", r"^(MONTANT|INCOME|AMOUNT)$"), Col("div_date", r"^DATE$", "date"), Col("compartment", r"^(COMP|BOARD)", "text"),
    Col("net_yield", r"^(RDT|YIELD)", "pct"), Col("per", r"^PER$"),
]
RIGHTS_NEW = [
    Col("prev_close", r"^(PRECEDENT|PREVIOUS)$"), Col("open", r"^(OUV|OPEN)"), Col("close", r"^(CLOT|CLOS)"),
    Col("change_pct", r"^(JOUR|VARIATION|DAILY)$", "pct", min_gap=12), Col("volume", r"^VOLUME$", "int"),
    Col("value", r"^(VALEUR|VALUE)$", "int"), Col("ref_price", r"^REFERENCE$"),
    Col("change_origin_pct", r"^(L'ORIGINE|DEPUIS|ANNUAL|YEAR)$", "pct"), Col("parity", r"^(PARITE|RATIO)$", "text"),
    Col("start_date", r"^(DEBUT|START)$", "date"), Col("end_date", r"^(FIN|END)$", "date"),
]
RIGHTS_OLD = [
    Col("volume", r"^VOLUME$", "int"), Col("value", r"^(VALEUR|VALUE)$", "int"), Col("prev_close", r"^(PRECEDENT|PREVIOUS)$"),
    Col("open", r"^(OUV|OPEN)"), Col("close", r"^(CLOT|CLOS)"), Col("avg_price", r"^(MOY|AVG)"),
    Col("change_origin_pct", r"^(VARIATION|L'ORIGINE|DEPUIS)$", "pct"), Col("ref_price", r"^REFERENCE$"),
    Col("limit_low", r"^(BAS|LOW)$"), Col("limit_high", r"^(HAUT|HIGH)$"), Col("parity", r"^(PARITE|RATIO)$", "text"),
    Col("start_date", r"^(DEBUT|START)$", "date"), Col("end_date", r"^(FIN|END)$", "date"),
]
BOND_NEW = [
    Col("nominal", r"^(NOMINALE|NOMINAL|FACE)$"), Col("prev_price", r"^(PRECEDENT|PREVIOUS)$"), Col("price", r"^(JOUR|DAILY)$"),
    Col("ref_price", r"^REFERENCE$"), Col("volume", r"^VOLUME$", "int"), Col("value", r"^(VALEUR|VALUE)$", "int"),
    Col("accrued_coupon", r"^(COURU|ACCRUED)$"), Col("periodicity", r"^(PERIODE|PERIOD)$", "text"),
    Col("coupon_amount", r"^(MONTANT|AMOUNT)$"), Col("next_coupon_date", r"^(ECHE|PAY)", "date"),
    Col("amort_type", r"^(TYPE|AMORT)", "text"),
]
BOND_OLD = [
    Col("volume", r"^VOLUME$", "int"), Col("value", r"^(VALEUR|VALUE)$", "int"), Col("prev_price", r"^(PRECEDENT|PREVIOUS)$"),
    Col("open", r"^(OUV|OPEN)"), Col("price", r"^(CLOT|CLOS)"), Col("avg_price", r"^(MOY|AVG)"),
    Col("change_pct", r"^(VARIATION|CHANGE)$", "pct"), Col("ref_price", r"^REFERENCE$"),
    Col("limit_low", r"^(BAS|LOW)$"), Col("limit_high", r"^(HAUT|HIGH)$"), Col("nominal", r"^(NOMINALE|NOMINAL)$"),
    Col("accrued_coupon", r"^(COURU|ACCRUED)$", optional=True), Col("amort_type", r"^(TYPE|AMORT)", "text"),
    Col("periodicity", r"^(PERIODE|PERIOD)$", "text"), Col("coupon_amount", r"^(MONTANT|AMOUNT)$"),
    Col("next_coupon_date", r"^(ECHE|PAY)", "date"),
]
BOOK = [
    Col("bid_qty", r"^(L'ACHAT|BUY|RESIDUELLE)$", "int"), Col("bid_price", r"^(ACHAT|BUY/?)$"),
    Col("ask_price", r"^(VENTE|SELL)$"), Col("ask_qty", r"^(VENTE|SELL|RESIDUELLE)$", "int"),
    Col("ref_price", r"^REFERENCE$"),
]

SECTOR_SPLIT_RE = r"\bSECT\.|\bACT\.$"


def classify_header(words: list[str]) -> str | None:
    """Table type from the header words (French or English edition)."""
    s = set(words)
    if s & {"RESIDUELLE", "RESIDUELLES", "REMAINING", "QUANTITY"}:
        return "order_book"
    if s & {"PARITE", "RATIO", "RIGHTS"}:
        return "rights"
    if s & {"COUPON", "NOMINALE", "COURU", "ACCRUED", "BOND"}:
        return "bonds"
    if s & {"PER", "DIVIDENDE", "RDT.", "RDT", "DIVIDEND"}:
        return "equities"
    return None


def _market_before(page: Page, idx: int, default: str | None) -> str | None:
    for ln in reversed(page.lines[:idx]):
        t = norm(ln.text)
        m = re.search(r"MARCHE DES (ACTIONS|DROITS|OBLIGATIONS)|(EQUITIES|RIGHTS|BONDS?) MARKET", t)
        if m:
            key = m[1] or m[2]
            return {"ACTIONS": "equities", "EQUITIES": "equities", "DROITS": "rights", "RIGHTS": "rights",
                    "OBLIGATIONS": "bonds", "BONDS": "bonds", "BOND": "bonds"}[key]
    return default


def _spec(kind: str, hw: list[str]) -> TableSpec:
    old = bool({"MOY.", "MOY", "AVERAGE"} & set(hw)) or ("BAS" in hw and "HAUT" in hw) or ("LOW" in hw and "HIGH" in hw)
    cols = {
        "equities": EQ_OLD if old else EQ_NEW, "rights": RIGHTS_OLD if old else RIGHTS_NEW,
        "bonds": BOND_OLD if old else BOND_NEW, "order_book": BOOK,
    }[kind]
    has_sector = kind == "equities" and any(w in ("SECT.", "ACT.", "SECT") for w in hw)
    return TableSpec(kind, cols, sector_codes=has_sector)


def read_all(doc: Document) -> list[tuple[str, str | None, TableResult]]:
    """Read every quote-type table of the document, page by page, following tables that
    continue on the next page without a header. Returns [(kind, market, result)]; cached."""
    cached = getattr(doc, "_quote_tables", None)
    if cached is not None:
        return cached
    out: list[tuple[str, str | None, TableResult]] = []
    pending: tuple[str, str | None, TableSpec, Header, str | None] | None = None
    market = None
    for page in doc.pages:
        if pending:  # table running over from the previous page
            kind, mk, spec, hdr, group = pending
            res = read_table(page, None, spec, group=group, continue_from=hdr)
            pending = None
            if res.rows:
                out.append((kind, mk, res))
                if not res.complete:
                    pending = (kind, mk, spec, hdr, res.group)
        i = find_header(page)
        while i is not None:
            words, _ = header_words(page, i)
            hw = [norm(w.text) for w in words]
            kind = classify_header(hw)
            if kind:
                if kind == "order_book":
                    market = _market_before(page, i, market)
                spec = _spec(kind, hw)
                group = None
                if out and out[-1][0] == kind and kind != "order_book":
                    group = out[-1][2].group  # header repeated on a new page: keep the group
                res = read_table(page, i, spec, group=group)
                mk = market if kind == "order_book" else kind
                out.append((kind, mk, res))
                pending = None if res.complete else (kind, mk, spec, res.header, res.group)
            i = find_header(page, i + 1)
    doc._quote_tables = out  # type: ignore[attr-defined]
    return out


# ---------------------------------------------------------------- helpers

def _num(cells, k, loc, comma_thousands=False):
    """Number of a cell; tolerates a trailing annotation ('1250 Amort' -> 1250)."""
    raw = cells.get(k)
    v = parse_number(raw, loc, comma_thousands)
    if v is None and raw:
        m = re.match(r"^([-+]?[\d][\d .,]*%?)\s+[A-Za-z(].*$", raw)
        if m:
            v = parse_number(m[1], loc, comma_thousands)
    return v


def _int(cells, k, loc):
    return parse_int(cells.get(k), loc)


def _flags(cells: dict, keys) -> str | None:
    fl = sorted({f for k in keys if (f := cell_flag(cells.get(k)))})
    return ",".join(fl) or None


_COMP = {"1ER": "1", "1": "1", "1ST": "1", "2EME": "2", "2E": "2", "2": "2", "2ND": "2", "3EME": "3", "3": "3", "3RD": "3"}


def _compartment(group: str | None, comp_cell: str | None) -> str | None:
    if comp_cell:
        c = norm(comp_cell).replace(" ", "")
        if c in _COMP:
            return {"1": "PREMIER", "2": "SECOND", "3": "TROISIEME"}[_COMP[c]]
    if group:
        m = re.search(r"COMPARTIMENT\s+([A-Z]+)|^(PREMIER|SECOND|DEUXIEME|TROISIEME)\s+COMPARTIMENT", group)
        if m:
            v = m[1] or m[2]
            return "SECOND" if v == "DEUXIEME" else v
    return None


# English edition sector names -> the French names used by the French bulletins
SECTOR_EN_FR = {"INDUSTRY": "INDUSTRIE", "PUBLIC UTILITIES": "SERVICES PUBLICS", "FINANCIAL SERVICES": "FINANCES",
                "TRANSPORTATION": "TRANSPORT", "TRANSPORT": "TRANSPORT", "AGRICULTURE": "AGRICULTURE",
                "DISTRIBUTION": "DISTRIBUTION", "OTHER SECTORS": "AUTRES SECTEURS", "OTHERS": "AUTRES SECTEURS",
                "MISC.": "AUTRES SECTEURS", "TELECOMMUNICATIONS": "TELECOMMUNICATIONS",
                "CONSUMER STAPLES": "CONSOMMATION DE BASE", "CONSUMER DISCRETIONARY": "CONSOMMATION DISCRETIONNAIRE",
                "INDUSTRIALS": "INDUSTRIELS", "ENERGY": "ENERGIE", "UTILITIES": "SERVICES PUBLICS"}


def _sector_group(group: str | None) -> str | None:
    """'SECTEUR - FINANCES' / 'AUTRES SECTEURS' / 'FINANCIAL SERVICES - SECTOR' -> sector name."""
    if not group:
        return None
    if group.startswith("SECTEUR"):
        return re.sub(r"\s*POINTS?$", "", group.split("-", 1)[-1]).strip() or None
    if group == "AUTRES SECTEURS":
        return "AUTRES SECTEURS"
    m = re.match(r"^(.+?) - SECTORS?$", group)
    return SECTOR_EN_FR.get(m[1], m[1]) if m else None


# bulletin markers printed next to names: (d) ex-dividend, (V) variation vs reference price,
# (*) (**) (***) footnotes, (#), (-), (ex- div)
_MARKER = re.compile(r"\s*\((?:d|v|#|-|\*+|ex-?\s*div\.?)\)?(?=\s|$)", re.IGNORECASE)
_EX_DIV = re.compile(r"\((?:d|ex-?\s*div\.?)\)", re.IGNORECASE)


def _clean_title(t: str) -> str:
    t = t.replace("’", "'").replace("–", "-").replace("''", "'")
    return re.sub(r"\s+", " ", _MARKER.sub(" ", t)).strip()


def _title_flags(t: str) -> str | None:
    """Flags carried by markers in the name: ex-dividend '(d)'."""
    return "EX-DIV" if _EX_DIV.search(t) else None


def _yield(cells: dict, loc: str) -> float | None:
    """Net yield in percent. The English edition prints it as a fraction (0.08 = 8 %)."""
    raw = cells.get("net_yield")
    v = parse_number(raw, loc)
    if v is not None and raw and "%" not in raw and abs(v) < 1:
        v = round(v * 100, 4)
    return v


# ---------------------------------------------------------------- parsers

def _read(doc: Document, kind: str) -> list[TableResult]:
    return [res for k, _mk, res in read_all(doc) if k == kind]


def _totals(res: TableResult, date: dt.date, table: str, loc: str) -> list[dict]:
    """TOTAL lines of a table: per group ('group'), per category ('category') and the market
    grand total ('grand'), as printed in the BOC (used by the QC checksums)."""
    out = []
    items = [("category" if (g or "").startswith("TOTAL") else "group", g, n) for g, n in res.totals]
    if res.grand_total:
        items.append(("grand", res.grand_total[0], res.grand_total[1]))
    for level, label, nums in items:
        if nums:
            out.append({"date": date.isoformat(), "table": table, "level": level, "label": label,
                        "volume": parse_int(nums[0], loc), "value": parse_int(nums[1], loc) if len(nums) > 1 else None})
    return out


_GROUPED_INT = re.compile(r"^\d{1,3}([ ,.]\d{3})*$")


def _fix_value(rec: dict, raw: str | None, price_keys: tuple[str, ...], warns: list[str]) -> None:
    """The BOC sometimes clips a traded value that is too wide for its column ('15 000 000 0'
    for 15 000 000 000). When the cell is malformed, or value/volume is far from the price,
    replace it by volume x price and flag the row VALUE-EST."""
    vol = rec.get("volume")
    price = next((rec[k] for k in price_keys if rec.get(k)), None)
    if not vol or not price:
        return
    val = rec.get("value")
    malformed = bool(raw) and not _GROUPED_INT.match(raw.strip())
    implausible = val is not None and not (0.2 * price <= val / vol <= 5 * price)
    if malformed or implausible or (val is None and raw):
        est = int(round(vol * price))
        warns.append(f"{rec['symbol']}: traded value {raw!r} unreadable/clipped in the PDF; "
                     f"estimated as volume x price = {est}")
        rec["value"] = est
        rec["status_flag"] = ",".join(filter(None, [rec.get("status_flag"), "VALUE-EST"]))


def _dedupe(rows: list[dict], warns: list[str], what: str) -> list[dict]:
    """Keep the first row of each symbol (a symbol listed twice is a layout artefact)."""
    seen, out = set(), []
    for r in rows:
        if r["symbol"] in seen:
            warns.append(f"{what}: duplicate row for {r['symbol']} (page {r.get('page')}) ignored")
            continue
        seen.add(r["symbol"])
        out.append(r)
    return out


def parse_equities(doc: Document, date: dt.date) -> tuple[list[dict], list[dict], list[str]]:
    """Returns (quotes, totals, warnings)."""
    loc = doc.locale
    quotes, totals, warns = [], [], []
    for res in _read(doc, "equities"):
        warns += res.warnings
        for r in res.rows:
            c = r.cells
            warns += r.warnings
            quotes.append({
                "date": date.isoformat(), "symbol": r.symbol, "name": _clean_title(r.title),
                "group_label": r.group, "sector_code": r.sector,
                "sector": _sector_group(r.group), "compartment": _compartment(r.group, c.get("compartment")),
                "prev_close": _num(c, "prev_close", loc), "open": _num(c, "open", loc),
                "close": _num(c, "close", loc), "avg_price": _num(c, "avg_price", loc),
                "change_pct": _num(c, "change_pct", loc), "volume": _int(c, "volume", loc),
                "value": _int(c, "value", loc), "ref_price": _num(c, "ref_price", loc),
                "ytd_pct": _num(c, "ytd_pct", loc), "limit_low": _num(c, "limit_low", loc),
                "limit_high": _num(c, "limit_high", loc), "div_amount": _num(c, "div_amount", loc),
                "div_date": parse_date(c.get("div_date"), date), "net_yield": _yield(c, loc),
                "per": _num(c, "per", loc),
                "status_flag": ",".join(filter(None, [_flags(c, ("open", "close", "prev_close", "ref_price")),
                                                      _title_flags(r.title)])) or None,
                "page": r.page,
            })
            _fix_value(quotes[-1], c.get("value"), ("close", "avg_price", "ref_price", "prev_close"), warns)
        totals += _totals(res, date, "equities", loc)
    return _dedupe(quotes, warns, "equities"), totals, warns


def parse_rights(doc: Document, date: dt.date) -> tuple[list[dict], list[str]]:
    loc = doc.locale
    out, warns = [], []
    for res in _read(doc, "rights"):
        warns += res.warnings
        for r in res.rows:
            c = r.cells
            warns += r.warnings
            out.append({
                "date": date.isoformat(), "symbol": r.symbol, "name": _clean_title(r.title),
                "prev_close": _num(c, "prev_close", loc), "open": _num(c, "open", loc), "close": _num(c, "close", loc),
                "avg_price": _num(c, "avg_price", loc), "change_pct": _num(c, "change_pct", loc),
                "volume": _int(c, "volume", loc), "value": _int(c, "value", loc), "ref_price": _num(c, "ref_price", loc),
                "change_origin_pct": _num(c, "change_origin_pct", loc), "parity": c.get("parity"),
                "start_date": parse_date(c.get("start_date"), date), "end_date": parse_date(c.get("end_date"), date),
                "status_flag": _flags(c, ("open", "close")), "page": r.page,
            })
    return _dedupe(out, warns, "rights"), warns


_BOND_TITLE = re.compile(
    r"^(?P<issuer>.*?)\s*(?P<rate>\d+(?:[.,]\d+)?)\s*%\s*(?P<y1>(?:19|20)\d{2})\s*-\s*(?P<y2>(?:19|20)\d{2})?")


def bond_terms(title: str) -> dict:
    """'ETAT DU MALI 6,20 % 2022-2029' -> issuer, coupon_rate 6.2, issue_year 2022, maturity_year 2029."""
    m = _BOND_TITLE.search(title)
    if not m:
        y = re.search(r"((?:19|20)\d{2})\s*-\s*((?:19|20)\d{2})", title)
        return {"issuer": re.split(r"\s\d", title)[0].strip() or None, "coupon_rate": None,
                "issue_year": int(y[1]) if y else None, "maturity_year": int(y[2]) if y else None}
    return {"issuer": m["issuer"].strip(" -") or None, "coupon_rate": float(m["rate"].replace(",", ".")),
            "issue_year": int(m["y1"]), "maturity_year": int(m["y2"]) if m["y2"] else None}


def parse_bonds(doc: Document, date: dt.date) -> tuple[list[dict], list[dict], list[str]]:
    loc = doc.locale
    out, totals, warns = [], [], []
    for res in _read(doc, "bonds"):
        warns += res.warnings
        for r in res.rows:
            c = r.cells
            warns += r.warnings
            title = _clean_title(r.title)
            out.append({
                "date": date.isoformat(), "symbol": r.symbol, "name": title, "section": r.group,
                "nominal": _num(c, "nominal", loc), "prev_price": _num(c, "prev_price", loc),
                "open": _num(c, "open", loc), "price": _num(c, "price", loc), "avg_price": _num(c, "avg_price", loc),
                "change_pct": _num(c, "change_pct", loc), "ref_price": _num(c, "ref_price", loc),
                "limit_low": _num(c, "limit_low", loc), "limit_high": _num(c, "limit_high", loc),
                "volume": _int(c, "volume", loc), "value": _int(c, "value", loc),
                "accrued_coupon": _num(c, "accrued_coupon", loc), "periodicity": c.get("periodicity"),
                "coupon_amount": _num(c, "coupon_amount", loc),
                "next_coupon_date": parse_date(c.get("next_coupon_date"), date),
                "next_coupon_raw": c.get("next_coupon_date"), "amort_type": c.get("amort_type"),
                "status_flag": _flags(c, ("price", "open")), "page": r.page, **bond_terms(title),
            })
            _fix_value(out[-1], c.get("value"), ("price", "avg_price", "ref_price", "prev_price"), warns)
        totals += _totals(res, date, "bonds", loc)
    return _dedupe(out, warns, "bonds"), totals, warns


def _split_book_prices(c: dict) -> None:
    """'9,995 / 10,000' may land in one column: split around '/' into bid and ask."""
    for k in ("bid_price", "ask_price"):
        v = c.get(k)
        if v and "/" in v:
            left, _, right = v.partition("/")
            c["bid_price"], c["ask_price"] = left.strip() or c.get("bid_price"), right.strip() or None
            if k == "bid_price" and not right.strip():
                c["ask_price"] = c.get("ask_price") if c.get("ask_price") and "/" not in c.get("ask_price") else None


def parse_order_book(doc: Document, date: dt.date) -> tuple[list[dict], list[str]]:
    loc = doc.locale
    out, warns = [], []
    seen = set()
    for kind, market, res in read_all(doc):
        if kind != "order_book":
            continue
        warns += res.warnings
        for r in res.rows:
            c = {k: v.replace(" /", "").replace("/ ", "").strip() if v != "/" else "" for k, v in r.cells.items()}
            _split_book_prices(c)
            mk = market or ("bonds" if re.search(r"\.[A-Z]\d", r.symbol) else "equities")
            key = (mk, r.symbol)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "date": date.isoformat(), "market": mk, "symbol": r.symbol, "name": _clean_title(r.title),
                "bid_qty": parse_int(c.get("bid_qty"), loc), "bid_price": _num(c, "bid_price", loc, True),
                "ask_price": _num(c, "ask_price", loc, True), "ask_qty": parse_int(c.get("ask_qty"), loc),
                "ref_price": _num(c, "ref_price", loc, True), "page": r.page,
            })
    return out, warns


# ---------------------------------------------------------------- section entry points (pipeline)

def equities_section(doc: Document, date: dt.date) -> dict:
    q, t, w = parse_equities(doc, date)
    return {"equity_quotes": q, "table_totals": t, "warnings": w}


def rights_section(doc: Document, date: dt.date) -> dict:
    r, w = parse_rights(doc, date)
    return {"right_quotes": r, "warnings": w}


def bonds_section(doc: Document, date: dt.date) -> dict:
    b, t, w = parse_bonds(doc, date)
    return {"bond_quotes": b, "table_totals": t, "warnings": w}


def order_book_section(doc: Document, date: dt.date) -> dict:
    o, w = parse_order_book(doc, date)
    return {"order_book": o, "warnings": w}
