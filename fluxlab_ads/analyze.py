"""Logika liczenia zmarnowanego budzetu i sugestii negatywow."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .parser import SearchTermRow

# Slowa nieznaczace (stopwords) pomijane przy analizie n-gramow.
STOPWORDS = {
    "i",
    "oraz",
    "w",
    "we",
    "na",
    "do",
    "z",
    "ze",
    "za",
    "o",
    "u",
    "a",
    "the",
    "of",
    "for",
    "to",
    "and",
    "or",
    "in",
    "on",
    "at",
    "by",
    "jak",
    "co",
    "czy",
    "dla",
    "pl",
    "com",
    "http",
    "https",
    "www",
}


@dataclass
class WastedTerm:
    term: str
    cost: float
    clicks: float
    conversions: float


@dataclass
class NegativeSuggestion:
    ngram: str
    wasted_cost: float
    term_count: int
    clicks: float


@dataclass
class AuditResult:
    total_cost: float
    total_clicks: float
    total_conversions: float
    wasted_cost: float
    wasted_share: float  # udzial zmarnowanego w calym koszcie (0..1)
    wasted_term_count: int
    monthly_recoverable: float
    yearly_recoverable: float
    top_wasted: list[WastedTerm]
    negatives: list[NegativeSuggestion]
    min_clicks: int
    period_days: int
    recovery_rate: float
    row_count: int = 0


def _tokenize(term: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9ąćęłńóśźż]+", term.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def analyze(
    rows: list[SearchTermRow],
    min_clicks: int = 3,
    period_days: int = 30,
    recovery_rate: float = 0.7,
    top_n: int = 20,
    max_negatives: int = 25,
) -> AuditResult:
    """Analizuje wiersze wyszukiwanych hasel.

    min_clicks: fraza jest 'marnotrawna' gdy ma 0 konwersji i > min_clicks klikniec.
    period_days: dlugosc okresu eksportu (do przeliczenia na miesiac).
    recovery_rate: jaka czesc marnotrawstwa realnie da sie odzyskac (ostrozne 70%).
    """
    total_cost = sum(r.cost for r in rows)
    total_clicks = sum(r.clicks for r in rows)
    total_conversions = sum(r.conversions for r in rows)

    wasted_rows = [
        r for r in rows if r.conversions == 0 and r.clicks > min_clicks and r.cost > 0
    ]
    wasted_cost = sum(r.cost for r in wasted_rows)
    wasted_share = (wasted_cost / total_cost) if total_cost > 0 else 0.0

    top_wasted = [
        WastedTerm(r.term, r.cost, r.clicks, r.conversions)
        for r in sorted(wasted_rows, key=lambda x: x.cost, reverse=True)[:top_n]
    ]

    # przeliczenie zmarnowanego kosztu na miesiac (30 dni)
    monthly_factor = 30.0 / period_days if period_days > 0 else 1.0
    monthly_wasted = wasted_cost * monthly_factor
    monthly_recoverable = monthly_wasted * recovery_rate
    yearly_recoverable = monthly_recoverable * 12

    negatives = _suggest_negatives(wasted_rows, max_negatives)

    return AuditResult(
        total_cost=total_cost,
        total_clicks=total_clicks,
        total_conversions=total_conversions,
        wasted_cost=wasted_cost,
        wasted_share=wasted_share,
        wasted_term_count=len(wasted_rows),
        monthly_recoverable=monthly_recoverable,
        yearly_recoverable=yearly_recoverable,
        top_wasted=top_wasted,
        negatives=negatives,
        min_clicks=min_clicks,
        period_days=period_days,
        recovery_rate=recovery_rate,
        row_count=len(rows),
    )


def _suggest_negatives(
    wasted_rows: list[SearchTermRow], max_negatives: int
) -> list[NegativeSuggestion]:
    """Analiza n-gramow (1 i 2 slowa) w frazach marnotrawnych.

    Zwraca slowa/pary slow, ktore powtarzaja sie w wielu marnotrawnych frazach
    i sumarycznie generuja najwiecej zmarnowanego kosztu = najlepsi kandydaci
    na wykluczenia (negative keywords).
    """
    cost_by_ngram: dict[str, float] = defaultdict(float)
    clicks_by_ngram: dict[str, float] = defaultdict(float)
    count_by_ngram: Counter = Counter()

    for r in wasted_rows:
        tokens = _tokenize(r.term)
        seen: set[str] = set()
        for n in (1, 2):
            for g in _ngrams(tokens, n):
                if g in seen:
                    continue
                seen.add(g)
                cost_by_ngram[g] += r.cost
                clicks_by_ngram[g] += r.clicks
                count_by_ngram[g] += 1

    suggestions = [
        NegativeSuggestion(
            ngram=g,
            wasted_cost=cost_by_ngram[g],
            term_count=count_by_ngram[g],
            clicks=clicks_by_ngram[g],
        )
        for g in cost_by_ngram
        # kandydat musi wystapic w min. 2 frazach (unikamy pojedynczych trafien)
        if count_by_ngram[g] >= 2
    ]
    suggestions.sort(key=lambda s: (s.wasted_cost, s.term_count), reverse=True)
    return suggestions[:max_negatives]
