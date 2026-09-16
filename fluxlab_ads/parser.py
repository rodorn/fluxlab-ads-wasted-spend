"""Parser eksportu CSV 'Wyszukiwane hasla' z Google Ads.

Obsluguje typowe formaty eksportu:
- polskie i angielskie naglowki kolumn,
- separatory: przecinek, srednik, tabulator,
- separatory dziesietne: kropka i przecinek,
- separatory tysiecy: spacja (rowniez NBSP), przecinek, apostrof,
- symbole waluty (zl, PLN, EUR, $, ...),
- naglowki poprzedzone wierszami metadanych (Google Ads dodaje 2-3 wiersze przed tabela),
- kodowanie UTF-8 (rowniez z BOM) oraz UTF-16 (natywny eksport z UI Google Ads).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass


# Synonimy naglowkow kolumn. Klucze porownujemy po normalizacji (lower, bez znakow
# specjalnych). Kolejnosc wariantow nie ma znaczenia, dopasowanie jest po zawieraniu.
COLUMN_ALIASES = {
    "term": [
        "wyszukiwane haslo",
        "wyszukiwane hasla",
        "haslo wyszukiwania",
        "search term",
        "search terms",
        "keyword",
        "query",
    ],
    "cost": [
        "koszt",
        "cost",
        "spend",
        "wydatki",
    ],
    "clicks": [
        "klikniecia",
        "clicks",
    ],
    "conversions": [
        "konwersje",
        "conversions",
        "conv",
        "conversion",
    ],
    "impressions": [
        "wyswietlenia",
        "impressions",
        "impr",
    ],
}


class ParseError(Exception):
    pass


@dataclass
class SearchTermRow:
    term: str
    cost: float
    clicks: float
    conversions: float
    impressions: float = 0.0


def _normalize_header(text: str) -> str:
    text = text.strip().lower()
    # usun tresc w nawiasach np. "Koszt (PLN)"
    text = re.sub(r"\(.*?\)", " ", text)
    # zamien polskie znaki na ascii dla stabilnego dopasowania
    text = (
        text.replace("ą", "a")
        .replace("ć", "c")
        .replace("ę", "e")
        .replace("ł", "l")
        .replace("ń", "n")
        .replace("ó", "o")
        .replace("ś", "s")
        .replace("ź", "z")
        .replace("ż", "z")
    )
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "utf-8", "cp1250", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _detect_delimiter(sample: str) -> str:
    candidates = [";", "\t", ",", "|"]
    lines = [ln for ln in sample.splitlines() if ln.strip()][:15]
    best, best_score = ",", -1
    for delim in candidates:
        counts = [ln.count(delim) for ln in lines]
        # dobry separator wystepuje spojnie i wiecej niz raz
        consistent = [c for c in counts if c > 0]
        if not consistent:
            continue
        score = min(consistent) * len(consistent)
        if score > best_score:
            best, best_score = delim, score
    return best


def parse_number(value: str) -> float:
    """Parsuje liczbe z roznych formatow Google Ads.

    Przyklady: '1 234,56', '1,234.56', '12 zl', '0', '--', '', "1'234.5".
    """
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s or s in {"--", "-", "n/a", "N/A"}:
        return 0.0
    # usun waluty, litery, spacje (rowniez NBSP i waskie NBSP), apostrofy
    s = s.replace(" ", " ").replace(" ", " ")
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s or s in {"-", ".", ","}:
        return 0.0

    has_comma = "," in s
    has_dot = "." in s
    if has_comma and has_dot:
        # ten z prawej to separator dziesietny
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        # przecinek: dziesietny jesli po nim 1-2 cyfry i wystepuje raz
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    # tylko kropka lub czyste cyfry -> zostaw
    try:
        return float(s)
    except ValueError:
        return 0.0


def _match_columns(header: list[str]) -> dict[str, int]:
    norm = [_normalize_header(h) for h in header]
    mapping: dict[str, int] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for idx, h in enumerate(norm):
            if idx in mapping.values():
                continue
            if any(_normalize_header(a) == h for a in aliases):
                mapping[field] = idx
                break
        if field in mapping:
            continue
        # dopasowanie po zawieraniu (np. "search term view")
        for idx, h in enumerate(norm):
            if idx in mapping.values():
                continue
            if any(
                _normalize_header(a) in h or h in _normalize_header(a) for a in aliases
            ):
                mapping[field] = idx
                break
    return mapping


def _find_header_row(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    """Znajdz wiersz naglowka. Google Ads wstawia metadane przed tabela."""
    for i, row in enumerate(rows[:10]):
        mapping = _match_columns(row)
        if "term" in mapping and "cost" in mapping:
            return i, mapping
    raise ParseError(
        "Nie znaleziono kolumn 'wyszukiwane haslo' i 'koszt'. "
        "Sprawdz, czy to eksport raportu 'Wyszukiwane hasla' z Google Ads."
    )


def parse_csv(raw: bytes | str) -> list[SearchTermRow]:
    text = _decode(raw) if isinstance(raw, bytes) else raw
    delim = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    all_rows = [r for r in reader if any(c.strip() for c in r)]
    if not all_rows:
        raise ParseError("Plik CSV jest pusty.")

    header_idx, cols = _find_header_row(all_rows)
    data_rows = all_rows[header_idx + 1 :]

    out: list[SearchTermRow] = []
    for row in data_rows:
        if len(row) <= cols["term"]:
            continue
        term = row[cols["term"]].strip()
        if not term:
            continue
        low = _normalize_header(term)
        # pomijaj wiersze podsumowan Google Ads
        if (
            low.startswith("suma")
            or low.startswith("total")
            or low.startswith("laczna")
        ):
            continue

        def cell(field: str) -> float:
            idx = cols.get(field)
            if idx is None or idx >= len(row):
                return 0.0
            return parse_number(row[idx])

        out.append(
            SearchTermRow(
                term=term,
                cost=cell("cost"),
                clicks=cell("clicks"),
                conversions=cell("conversions"),
                impressions=cell("impressions"),
            )
        )
    if not out:
        raise ParseError("Znaleziono naglowek, ale brak wierszy z danymi.")
    return out
