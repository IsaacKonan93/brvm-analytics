"""PDF access: words with coordinates, grouped into lines, plus locale detection.

PyMuPDF (`pymupdf`) is used for speed (~0.1 s per BOC vs ~4.5 s with pdfplumber).
Coordinates are PDF points, origin top-left (y grows downward).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

# A fragment that continues a number split on its thousands separator: "14" + "455", "1" + "655,00".
_NUM_HEAD = re.compile(r"^[-+]?\d{1,3}$")
_NUM_TAIL = re.compile(r"^\d{3}([.,]\d+)?%?$")
MERGE_GAP = 3.6  # max horizontal gap (pt) between fragments of the same number


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Line:
    words: list[Word] = field(default_factory=list)

    @property
    def y(self) -> float:
        return min(w.y0 for w in self.words)

    @property
    def yc(self) -> float:
        return sum(w.yc for w in self.words) / len(self.words)

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Line(y={self.y:.0f}, {self.text!r})"


def norm(s: str) -> str:
    """Upper-case, accent-free, single-spaced version of s (for matching headings)."""
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().upper()


def merge_number_fragments(words: list[Word]) -> list[Word]:
    """Join number fragments split on thousands separators ('14','455' -> '14 455') and a
    trailing '%' ('5,50','%' -> '5,50 %'). Words must be on one line, sorted by x0."""
    out: list[Word] = []
    for w in words:
        if out:
            prev = out[-1]
            gap = w.x0 - prev.x1
            if gap <= MERGE_GAP:
                last_part = prev.text.split(" ")[-1]
                if (w.text == "%" and re.search(r"\d$", prev.text)) or (
                    _NUM_TAIL.match(w.text) and (_NUM_HEAD.match(last_part) or re.match(r"^\d{3}$", last_part))
                    and re.match(r"^[-+]?[\d ]+$", prev.text)
                ):
                    out[-1] = Word(f"{prev.text} {w.text}", prev.x0, min(prev.y0, w.y0), w.x1, max(prev.y1, w.y1))
                    continue
        out.append(Word(w.text, w.x0, w.y0, w.x1, w.y1))
    return out


def group_lines(words: list[Word], ytol: float = 2.5) -> list[Line]:
    """Group words whose vertical centres are within ytol into lines (sorted top->bottom, left->right)."""
    lines: list[Line] = []
    for w in sorted(words, key=lambda w: (w.yc, w.x0)):
        if lines and abs(lines[-1].yc - w.yc) <= ytol:
            lines[-1].words.append(w)
        else:
            lines.append(Line([w]))
    for ln in lines:
        ln.words.sort(key=lambda w: w.x0)
        ln.words = merge_number_fragments(ln.words)
    return lines


@dataclass
class Page:
    number: int  # 1-based
    width: float
    height: float
    words: list[Word]
    _lines: list[Line] | None = None

    @property
    def lines(self) -> list[Line]:
        if self._lines is None:
            self._lines = group_lines(self.words)
        return self._lines

    @property
    def text(self) -> str:
        return "\n".join(ln.text for ln in self.lines)


@dataclass
class Document:
    path: Path
    pages: list[Page]
    locale: str  # "fr" (1 234,56) or "en" (1,234.56)


_FR_NUM = re.compile(r"(?<![\d.,])\d{1,3}(?: \d{3})*,\d{2}(?![\d,])")
_EN_NUM = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,])|(?<![\d,])\d+\.\d{2}(?![\d.])")


def detect_locale(pages: list[Page]) -> str:
    """'fr' if numbers look like 1 234,56 / 0,15 %, 'en' if like 1,234.56 / 0.15 %."""
    sample = "\n".join(p.text for p in pages[:6])
    fr = len(_FR_NUM.findall(sample))
    en = len(_EN_NUM.findall(sample))
    return "en" if en > fr * 1.5 else "fr"


def _page(p: "pymupdf.Page", number: int) -> Page:
    """Words of a page in displayed coordinates, normalised to A4 size.

    * Rotated pages (/Rotate 90, e.g. the 2016-2018 fund pages): word boxes are mapped through
      the page rotation matrix so that text reads left to right.
    * Oversized pages (some 2020-2022 pages are drawn at 10x scale, 5950 x 8420 pt): coordinates
      are scaled back to A4 so that all distance thresholds keep their meaning.
    """
    raw = p.get_text("words")
    m = p.rotation_matrix if p.rotation else None
    width, height = p.rect.width, p.rect.height  # displayed size
    scale = 1.0
    if max(width, height) > 1200:
        scale = (842.0 if width > height else 595.44) / width
    words = []
    for x0, y0, x1, y1, t, *_ in raw:
        if m is not None:
            r = pymupdf.Rect(x0, y0, x1, y1) * m
            x0, y0, x1, y1 = r.x0, r.y0, r.x1, r.y1
        words.append(Word(t, x0 * scale, y0 * scale, x1 * scale, y1 * scale))
    return Page(number, width * scale, height * scale, words)


def is_front_page(text: str) -> bool:
    """The bulletin's front page: index summary + top movers (FR) or 'DAILY MARKET REPORT' (EN)."""
    t = norm(text)
    return "BRVM COMPOSITE" in t and ("PLUS FORTES HAUSSES" in t or "DAILY MARKET REPORT" in t
                                       or "RESUME DE LA COTE" in t or "TOP GAINERS" in t)


def load(path: str | Path) -> Document:
    """Load a BOC PDF. If the file holds a second bulletin after the first one (e.g. 2017-12-20
    also contains the English edition of 2017-12-19), only the first bulletin is kept."""
    path = Path(path)
    pages = []
    with pymupdf.open(path) as doc:
        fronts = [i for i, p in enumerate(doc) if is_front_page(p.get_text())]
        last = fronts[1] if len(fronts) > 1 else doc.page_count
        for i, p in enumerate(doc, start=1):
            if i > last:
                break
            pages.append(_page(p, i))
    d = Document(path, pages, detect_locale(pages))
    d.truncated_at = last + 1 if len(fronts) > 1 else None  # type: ignore[attr-defined]
    return d
