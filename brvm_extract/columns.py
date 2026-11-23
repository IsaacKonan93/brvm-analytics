"""Generic BOC table reader: header anchors -> column positions -> rows of raw cells.

How a table is read (see EXTRACTION.md, "How tables are read"):
1. The header block is the set of lines within +-14 pt of the line containing "Symbole"/"Symbol".
2. Each column of the table spec is anchored on a header word, searched left to right
   (each anchor must lie to the right of the previous one), e.g. close price -> "Clôt.".
3. Column centres are refined from the data itself (median x-centre of the values assigned to
   each column, two passes), so that right-aligned numbers far from their header still land in
   the right column, and empty cells never shift the other values.
4. A "row" starts on a line whose first word is a security symbol (in the symbol column) and
   that has values in the numeric columns. Lines without a symbol (wrapped names, the sector
   code of the 2023+ layouts, split numbers) are attached to the vertically nearest row.
5. Group headings (COMPARTIMENT..., OBLIGATIONS D'ETAT, SECTEUR - ..., FCTC D'ENTREPRISES...)
   set the `group` of the following rows; TOTAL lines are captured for checksums.
6. A table that reaches the bottom of the page without a stop line continues on the next page
   (the BOC does not repeat the header): the caller passes `continue_from` to read it with the
   same header geometry.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from .pdfdoc import Line, Page, Word, norm

NUMBER_RE = re.compile(r"^[-+]?\d{1,3}(?: ?\d{3})*(?:[.,]\d*)?(?: ?%)?$")


@dataclass
class Col:
    name: str
    header: str          # regex matched against one header word (accent-insensitive, upper case)
    kind: str = "num"    # num | pct | int | date | text
    min_gap: float = 8.0  # the anchor must be at least this far right of the previous anchor
    optional: bool = False  # absent in some layouts: no warning when its header is missing


@dataclass
class TableSpec:
    name: str
    cols: list[Col]
    symbol_re: str = r"^[A-Z][A-Z0-9]{1,9}(\.[A-Z0-9]{1,6})?$"
    group_re: str = (r"^(COMPARTIMENT|PREMIER COMPARTIMENT|SECOND COMPARTIMENT|DEUXIEME COMPARTIMENT|"
                     r"TROISIEME COMPARTIMENT|SECTEUR\b|OBLIGATIONS\b|\d\. |SUKUK\b|FONDS COMMUNS|FCTC\b|"
                     r"EMPRUNTS?\b|GOVERNMENT|REGIONAL|CORPORATE|PRIVATE)")
    stop_re: str = (r"^(LEGENDE|LEGEND|TOTAL ?- ?MARCHE|TOTAL ?- ?(EQUIT(Y|IES)|RIGHTS?|BONDS?) MARKET|SECTEURS D'ACTIVITES|"
                    r"SECTORS|MENTIONS|ECHE\.|DEFINITIONS|MARCHE DES|(EQUITIES|RIGHTS|BONDS?) MARKET|"
                    r"ASSEMBLEES?|GENERAL MEETINGS|SOCIETE NATURE|COMPANY|OPCVM|SOCIETES DE GESTION|"
                    r"COMMUNIQUES|OPERATIONS EN COURS|EMETTEUR|BULLETIN OFFICIEL|INDICES|ANNEE :|"
                    r"VALEUR LIQUIDATIVE|RESUME DE LA COTE|INFORMATIONS)")
    sector_codes: bool = False  # a sector-code column left of the symbol (2023+ layouts)
    max_attach_dist: float = 11.0


@dataclass
class Row:
    symbol: str
    title: str
    group: str | None
    sector: str | None
    cells: dict[str, str]
    page: int
    y: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class Header:
    words: list[Word]
    anchors: dict[str, float]
    sym_x0: float | None
    title_limit: float


@dataclass
class TableResult:
    rows: list[Row]
    totals: list[tuple[str | None, list[str]]]  # (group, numbers on the TOTAL line)
    anchors: dict[str, float]
    warnings: list[str]
    complete: bool = True        # False: reached the page bottom -> may continue on next page
    header: Header | None = None
    group: str | None = None     # group label in force at the end of the table
    grand_total: tuple[str, list[str]] | None = None  # 'TOTAL - Marché des ...' line, if reached


def is_header_line(ln: Line) -> bool:
    return bool(re.search(r"\bSYMBOLE?\b", norm(ln.text)))


def find_header(page: Page, start: int = 0) -> int | None:
    for i in range(start, len(page.lines)):
        if is_header_line(page.lines[i]):
            return i
    return None


_ROW_START = re.compile(r"^[A-Z][A-Z0-9]{1,9}(\.[A-Z0-9]{1,6})?$")


def header_words(page: Page, idx: int, span: float = 14.0, span_down: float = 20.0) -> tuple[list[Word], float]:
    """Words of the header block around line idx (14 pt above, up to 20 pt below, stopping at
    the first data row), and the y where the body starts."""
    lines = page.lines
    y0 = lines[idx].yc

    def below_excluded(ln: Line) -> bool:
        # below the "Symbole" line, stop at data rows and at group headings (they belong to the body)
        data = bool(_ROW_START.match(ln.words[0].text) and re.search(r"\d", ln.text) and len(ln.words) > 3)
        heading = bool(re.match(r"^(OBLIGATIONS|COMPARTIMENT|SECTEUR|MARCHE|GOVERNMENT|REGIONAL|CORPORATE|\d\. )",
                                norm(ln.text)))
        return data or heading

    block = [ln for ln in lines
             if -span <= ln.yc - y0 <= span_down and not (ln.yc > y0 + 1 and below_excluded(ln))]
    words = sorted((w for ln in block for w in ln.words), key=lambda w: w.xc)
    body_y = max(ln.yc for ln in block) + 0.5
    return words, body_y


def anchor_columns(words: list[Word], cols: list[Col]) -> dict[str, float]:
    """Sequential left-to-right matching of column header regexes -> {col: x-centre}."""
    anchors: dict[str, float] = {}
    last_x = -1e9
    for col in cols:
        rx = re.compile(col.header)
        for w in words:
            if w.xc > last_x + col.min_gap and rx.search(norm(w.text)):
                anchors[col.name] = w.xc
                last_x = w.xc
                break
    return anchors


def build_header(words: list[Word], spec: TableSpec) -> Header:
    anchors = anchor_columns(words, spec.cols)
    sym = next((w for w in words if norm(w.text) in ("SYMBOLE", "SYMBOL")), None)
    first = min(anchors.values()) if anchors else 1e9
    first_x0 = min((w.x0 for w in words if abs(w.xc - first) < 0.01), default=first)
    return Header(words, anchors, sym.x0 if sym else None, first_x0 - 2)


def _nearest(x: float, centres: dict[str, float]) -> str:
    return min(centres, key=lambda k: abs(centres[k] - x))


def read_table(page: Page, header_idx: int | None, spec: TableSpec, group: str | None = None,
               continue_from: Header | None = None) -> TableResult:
    lines = page.lines
    warnings: list[str] = []
    if continue_from is not None:
        hdr, body_y = continue_from, 0.0
    else:
        hwords, body_y = header_words(page, header_idx)
        hdr = build_header(hwords, spec)
        missing = [c.name for c in spec.cols if c.name not in hdr.anchors and not c.optional]
        if missing:
            warnings.append(f"p{page.number} {spec.name}: header anchors not found: {missing}")
    anchors = hdr.anchors
    if not anchors:
        return TableResult([], [], anchors, warnings, True, hdr, group, None)

    title_limit = hdr.title_limit
    sector_limit = (hdr.sym_x0 - 3) if (spec.sector_codes and hdr.sym_x0) else None
    sym_rx = re.compile(spec.symbol_re)
    group_rx = re.compile(spec.group_re)
    stop_rx = re.compile(spec.stop_re)

    # ---- pass 1: classify body lines
    body: list[tuple[str, Line]] = []  # (kind, line) kind in row|cont|group|total
    complete = False
    grand_total: tuple[str, list[str]] | None = None
    consumed: set[int] = set()

    def total_numbers(i: int) -> list[str]:
        """Numbers of the TOTAL line i, or of the next line if they are printed just below it."""
        nums = [w.text for w in lines[i].words if re.search(r"\d", w.text)]
        if not nums and i + 1 < len(lines) and lines[i + 1].yc - lines[i].yc <= 7 and \
                all(re.search(r"\d", w.text) for w in lines[i + 1].words):
            consumed.add(i + 1)
            nums = [w.text for w in lines[i + 1].words]
        return nums

    for i, ln in enumerate(lines):
        if ln.yc <= body_y or i in consumed:
            continue
        t = norm(ln.text)
        if is_header_line(ln) or stop_rx.search(t):
            complete = True
            if re.match(r"^TOTAL ?- ?(MARCHE|EQUIT(Y|IES)|RIGHTS?|BONDS?)", t):
                grand_total = (re.sub(r"[\d\s.,%]+$", "", t).strip(), total_numbers(i))
            break  # next table on the same page / end of table
        if t.startswith("TOTAL"):
            ln._nums = total_numbers(i)  # type: ignore[attr-defined]
            body.append(("total", ln))
            continue
        ws = [w for w in ln.words if sector_limit is None or w.x1 > sector_limit]
        first = ws[0] if ws else None
        right = [w for w in ws if w.x1 > title_limit]
        # a symbol sits in the symbol column: not right of the "Symbole" header's left edge
        # (wrapped title lines such as "MARKETING CI" start further right)
        sym_ok = first is not None and sym_rx.match(first.text) and (
            first.x0 <= hdr.sym_x0 + 6 if hdr.sym_x0 is not None else first.x0 < title_limit)
        looks_heading = group_rx.search(t) or " POINTS" in f" {t}" or (
            not right and len(ws) >= 2 and not re.search(r"\d", t))
        if sym_ok and right and not (group_rx.search(t) and not re.search(r"\.[A-Z]?\d", first.text)) \
                and " POINTS" not in f" {t}":
            body.append(("row", ln))
        elif looks_heading and ln.x0 < title_limit and (sym_ok or group_rx.search(t) or " POINTS" in f" {t}"):
            body.append(("group", ln))
        else:
            body.append(("cont", ln))

    # ---- pass 2: build rows
    rows: list[Row] = []
    totals: list[tuple[str | None, list[str]]] = []
    tokens: list[tuple[Row, Word]] = []
    for kind, ln in body:
        if kind == "group":
            group = norm(" ".join(w.text for w in ln.words
                                  if not re.search(r"\d", w.text) and w.text.upper() != "POINTS"))
            group = re.sub(r"^\d\.\s*", "", group).strip(" -") or group
            continue
        if kind == "total":
            label = norm(" ".join(w.text for w in ln.words if not re.search(r"\d", w.text)))
            # 'TOTAL' alone closes the current group; 'TOTAL - X' closes a category
            totals.append((group if label == "TOTAL" else label, ln._nums))  # type: ignore[attr-defined]
            continue
        if kind == "row":
            ws = ln.words
            sector = None
            if sector_limit is not None:
                sec = [w.text for w in ws if w.x1 <= sector_limit]
                sector = " ".join(sec) or None
                ws = [w for w in ws if w.x1 > sector_limit]
            row = Row(ws[0].text, "", group, sector, {}, page.number, ln.yc)
            row._title = [w for w in ws[1:] if w.x1 <= title_limit]  # type: ignore[attr-defined]
            rows.append(row)
            tokens += [(row, w) for w in ws[1:] if w.x1 > title_limit]
    # continuation lines -> nearest row
    for kind, ln in body:
        if kind != "cont" or not rows:
            continue
        row = min(rows, key=lambda r: (abs(r.y - ln.yc), r.y > ln.yc))
        if abs(row.y - ln.yc) > spec.max_attach_dist:
            continue
        for w in ln.words:
            if sector_limit is not None and w.x1 <= sector_limit:
                row.sector = f"{row.sector} {w.text}".strip() if row.sector else w.text
            elif w.x1 <= title_limit:
                row._title.append(w)  # type: ignore[attr-defined]
            else:
                tokens.append((row, w))

    # ---- pass 3: refine column centres from data, then assign
    centres = dict(anchors)
    for _ in range(2):
        assigned: dict[str, list[float]] = {k: [] for k in centres}
        for _row, w in tokens:
            assigned[_nearest(w.xc, centres)].append(w.xc)
        for k, xs in assigned.items():
            if len(xs) >= 2:
                centres[k] = statistics.median(xs)
    kinds = {c.name: c.kind for c in spec.cols}
    per_row: dict[int, dict[str, list[Word]]] = {}
    for row, w in tokens:
        per_row.setdefault(id(row), {}).setdefault(_nearest(w.xc, centres), []).append(w)
    # a numeric cell holding several tokens that do not form one number: keep the token nearest
    # the column centre and move the others to the nearest date/text column (e.g. the '17' of a
    # coupon period '17 janv./17 juil.' drifting into the coupon amount column)
    for cells in per_row.values():
        for k in list(cells):
            ws = cells[k]
            if len(ws) < 2 or kinds.get(k) not in ("num", "int", "pct"):
                continue
            joined = re.sub(r"([.,]) ", r"\1", " ".join(w.text for w in sorted(ws, key=lambda w: (round(w.yc), w.x0))))
            if NUMBER_RE.match(joined):
                continue
            keep = min(ws, key=lambda w: abs(w.xc - centres[k]))
            others = [w for w in ws if w is not keep]
            soft = {n: x for n, x in centres.items() if kinds.get(n) in ("date", "text") and n != k}
            if soft:
                cells[k] = [keep]
                for w in others:
                    cells.setdefault(_nearest(w.xc, soft), []).append(w)
    for row in rows:
        for k, ws in per_row.get(id(row), {}).items():
            ws.sort(key=lambda w: (round(w.yc), w.x0))
            joined = " ".join(w.text for w in ws)
            if len(ws) > 1 and kinds.get(k) in ("num", "int", "pct"):
                glued = re.sub(r"([.,]) ", r"\1", joined)  # '1 806, 93' -> '1 806,93'
                if NUMBER_RE.match(glued):
                    joined = glued
                else:
                    row.warnings.append(f"{row.symbol}: several values in column {k}: {joined!r}")
            row.cells[k] = joined
        tw = sorted(row._title, key=lambda w: (round(w.yc), w.x0))  # type: ignore[attr-defined]
        row.title = " ".join(w.text for w in tw)
        del row._title  # type: ignore[attr-defined]
    hdr = Header(hdr.words, centres, hdr.sym_x0, hdr.title_limit) if continue_from is None else hdr
    return TableResult(rows, totals, centres, warnings, complete, hdr, group, grand_total)
