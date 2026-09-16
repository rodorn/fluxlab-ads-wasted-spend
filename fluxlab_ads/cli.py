"""CLI: audyt zmarnowanego budzetu Google Ads.

Uzycie:
    python -m fluxlab_ads.cli AUDYT input.csv --client "Nazwa" --pdf out/raport.pdf
    python -m fluxlab_ads.cli AUDYT input.csv --min-clicks 5 --days 30 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyze import analyze
from .parser import ParseError, parse_csv
from .report import html_to_pdf, render_html


def _zl(v: float) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",") + " zl"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="fluxlab-ads",
        description="Audyt zmarnowanego budzetu Google Ads (Wasted-Spend Audit).",
    )
    p.add_argument("csv", help="Sciezka do eksportu CSV 'Wyszukiwane hasla'.")
    p.add_argument("--client", default="PRZYKLAD", help="Nazwa klienta na raporcie.")
    p.add_argument(
        "--min-clicks",
        type=int,
        default=3,
        help="Minimalna liczba klikniec, by uznac fraze za marnotrawna (domyslnie 3).",
    )
    p.add_argument(
        "--days",
        type=int,
        default=30,
        help="Dlugosc okresu eksportu w dniach (do przeliczenia na miesiac).",
    )
    p.add_argument(
        "--recovery-rate",
        type=float,
        default=0.7,
        help="Ostrozny udzial mozliwy do odzyskania (domyslnie 0.7).",
    )
    p.add_argument(
        "--pdf", metavar="PLIK", help="Wygeneruj raport PDF pod wskazana sciezka."
    )
    p.add_argument(
        "--html", metavar="PLIK", help="Zapisz raport HTML pod wskazana sciezka."
    )
    p.add_argument(
        "--json", action="store_true", help="Wypisz wynik jako JSON zamiast tekstu."
    )
    args = p.parse_args(argv)

    try:
        raw = Path(args.csv).read_bytes()
    except OSError as e:
        print(f"Blad odczytu pliku: {e}", file=sys.stderr)
        return 2

    try:
        rows = parse_csv(raw)
    except ParseError as e:
        print(f"Blad parsowania CSV: {e}", file=sys.stderr)
        return 2

    result = analyze(
        rows,
        min_clicks=args.min_clicks,
        period_days=args.days,
        recovery_rate=args.recovery_rate,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "total_cost": round(result.total_cost, 2),
                    "wasted_cost": round(result.wasted_cost, 2),
                    "wasted_share": round(result.wasted_share, 4),
                    "wasted_term_count": result.wasted_term_count,
                    "monthly_recoverable": round(result.monthly_recoverable, 2),
                    "yearly_recoverable": round(result.yearly_recoverable, 2),
                    "top_wasted": [
                        {"term": t.term, "cost": round(t.cost, 2), "clicks": t.clicks}
                        for t in result.top_wasted
                    ],
                    "negatives": [
                        {
                            "ngram": s.ngram,
                            "wasted_cost": round(s.wasted_cost, 2),
                            "term_count": s.term_count,
                        }
                        for s in result.negatives
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Wierszy w eksporcie: {result.row_count}")
        print(f"Koszt calkowity ({result.period_days} dni): {_zl(result.total_cost)}")
        print(
            f"Zmarnowane (0 konw., >{result.min_clicks} klikn.): "
            f"{_zl(result.wasted_cost)} ({result.wasted_share * 100:.0f}%)"
        )
        print(f"Frazy marnotrawne: {result.wasted_term_count}")
        print(
            f">>> DO ODZYSKANIA: {_zl(result.monthly_recoverable)}/mc, "
            f"{_zl(result.yearly_recoverable)}/rok"
        )
        print("\nTop marnotrawne frazy:")
        for i, t in enumerate(result.top_wasted[:10], 1):
            print(f"  {i:2}. {_zl(t.cost):>14}  {int(t.clicks):>4} klikn.  {t.term}")
        print("\nSugerowane wykluczenia:")
        for s in result.negatives[:10]:
            print(
                f"  - {s.ngram:<28} {_zl(s.wasted_cost):>14}  (w {s.term_count} frazach)"
            )

    if args.html:
        Path(args.html).write_text(render_html(result, args.client), encoding="utf-8")
        print(f"\nZapisano HTML: {args.html}", file=sys.stderr)

    if args.pdf:
        out = html_to_pdf(render_html(result, args.client), args.pdf)
        print(f"Zapisano PDF: {out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
