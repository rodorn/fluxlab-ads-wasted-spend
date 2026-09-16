from fluxlab_ads.analyze import analyze
from fluxlab_ads.parser import SearchTermRow
import pytest


def rows():
    return [
        SearchTermRow(
            "naprawa telefonu za darmo", cost=120.0, clicks=15, conversions=0
        ),
        SearchTermRow("darmowa naprawa telefonu", cost=80.0, clicks=10, conversions=0),
        SearchTermRow("serwis iphone warszawa", cost=45.0, clicks=5, conversions=2),
        SearchTermRow("naprawa iphone cena", cost=30.0, clicks=4, conversions=1),
        SearchTermRow("praca naprawa telefonow", cost=25.0, clicks=6, conversions=0),
        SearchTermRow(
            "tania naprawa", cost=2.0, clicks=1, conversions=0
        ),  # <= min_clicks
    ]


class TestAnalyze:
    def test_wasted_cost_sum(self):
        r = analyze(rows(), min_clicks=3, period_days=30)
        # marnotrawne: 120 + 80 + 25 = 225 (0 konw. i >3 klikn.)
        assert r.wasted_cost == pytest.approx(225.0)
        assert r.wasted_term_count == 3

    def test_min_clicks_threshold_excludes_low_clicks(self):
        r = analyze(rows(), min_clicks=3, period_days=30)
        terms = [t.term for t in r.top_wasted]
        assert "tania naprawa" not in terms  # tylko 1 klikniecie

    def test_converting_terms_not_wasted(self):
        r = analyze(rows(), min_clicks=3, period_days=30)
        terms = [t.term for t in r.top_wasted]
        assert "serwis iphone warszawa" not in terms  # ma konwersje

    def test_top_wasted_sorted_by_cost_desc(self):
        r = analyze(rows(), min_clicks=3, period_days=30)
        costs = [t.cost for t in r.top_wasted]
        assert costs == sorted(costs, reverse=True)
        assert r.top_wasted[0].term == "naprawa telefonu za darmo"

    def test_monthly_recoverable(self):
        r = analyze(rows(), min_clicks=3, period_days=30, recovery_rate=0.7)
        # 225 * (30/30) * 0.7 = 157.5
        assert r.monthly_recoverable == pytest.approx(157.5)
        assert r.yearly_recoverable == pytest.approx(157.5 * 12)

    def test_period_scaling_to_month(self):
        # 15 dni danych -> podwojenie do miesiaca
        r = analyze(rows(), min_clicks=3, period_days=15, recovery_rate=1.0)
        assert r.monthly_recoverable == pytest.approx(225.0 * 2)

    def test_wasted_share(self):
        r = analyze(rows(), min_clicks=3, period_days=30)
        total = 120 + 80 + 45 + 30 + 25 + 2
        assert r.wasted_share == pytest.approx(225.0 / total)

    def test_negatives_ngram_detection(self):
        r = analyze(rows(), min_clicks=3, period_days=30)
        ngrams = [s.ngram for s in r.negatives]
        # 'darmo'/'darmowa' i 'naprawa' powtarzaja sie w frazach marnotrawnych
        assert any("naprawa" == n for n in ngrams)
        # kandydat musi wystapic w min. 2 frazach
        assert all(s.term_count >= 2 for s in r.negatives)

    def test_no_wasted_terms(self):
        good = [SearchTermRow("x", cost=10.0, clicks=5, conversions=3)]
        r = analyze(good, min_clicks=3, period_days=30)
        assert r.wasted_cost == 0
        assert r.monthly_recoverable == 0
        assert r.top_wasted == []
        assert r.negatives == []
