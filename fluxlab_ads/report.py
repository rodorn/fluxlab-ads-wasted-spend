"""Generowanie raportu HTML i konwersja do PDF przez google-chrome-stable."""

from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from .analyze import AuditResult


def _zl(value: float) -> str:
    s = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} zl"


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%".replace(".", ",")


def _num(value: float) -> str:
    if value == int(value):
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.1f}".replace(",", " ").replace(".", ",")


def render_html(result: AuditResult, client_name: str = "PRZYKLAD") -> str:
    today = date.today().strftime("%d.%m.%Y")
    r = result

    rows_html = ""
    for i, t in enumerate(r.top_wasted, 1):
        rows_html += (
            f"<tr><td class='n'>{i}</td>"
            f"<td class='term'>{html.escape(t.term)}</td>"
            f"<td class='num'>{_num(t.clicks)}</td>"
            f"<td class='num'>{_num(t.conversions)}</td>"
            f"<td class='num cost'>{_zl(t.cost)}</td></tr>"
        )
    if not rows_html:
        rows_html = "<tr><td colspan='5'>Brak fraz spelniajacych kryteria marnotrawstwa.</td></tr>"

    neg_html = ""
    for s in r.negatives:
        neg_html += (
            f"<tr><td class='term'>{html.escape(s.ngram)}</td>"
            f"<td class='num'>{s.term_count}</td>"
            f"<td class='num cost'>{_zl(s.wasted_cost)}</td></tr>"
        )
    if not neg_html:
        neg_html = (
            "<tr><td colspan='3'>Brak wyraznych wzorcow do wykluczenia.</td></tr>"
        )

    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Audyt zmarnowanego budzetu Google Ads</title>
<style>
  @page {{ size: A4; margin: 14mm 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Arial, sans-serif; color: #1a1a1a;
         font-size: 11px; line-height: 1.45; margin: 0; }}
  h1 {{ font-size: 20px; margin: 0 0 2px; }}
  h2 {{ font-size: 13px; margin: 16px 0 6px; color: #0b5; border-bottom: 2px solid #0b5;
        padding-bottom: 3px; }}
  .brand {{ color: #0b5; font-weight: 700; }}
  .meta {{ color: #666; font-size: 10px; margin-bottom: 14px; }}
  .hero {{ background: #0b5; color: #fff; border-radius: 10px; padding: 16px 20px;
           margin: 10px 0 4px; }}
  .hero .big {{ font-size: 30px; font-weight: 800; line-height: 1.1; }}
  .hero .sub {{ font-size: 11px; opacity: .92; }}
  .cards {{ display: flex; gap: 10px; margin: 12px 0; }}
  .card {{ flex: 1; border: 1px solid #e2e2e2; border-radius: 8px; padding: 10px 12px; }}
  .card .v {{ font-size: 17px; font-weight: 700; }}
  .card .l {{ font-size: 9.5px; color: #666; text-transform: uppercase; letter-spacing: .3px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
  th, td {{ text-align: left; padding: 4px 6px; border-bottom: 1px solid #eee; }}
  th {{ background: #f4f7f5; font-size: 9.5px; text-transform: uppercase; color: #555; }}
  td.num, th.num {{ text-align: right; }}
  td.cost {{ font-weight: 700; color: #c0392b; }}
  td.n {{ color: #999; width: 18px; }}
  td.term {{ font-family: "SFMono-Regular", Consolas, monospace; font-size: 10px; }}
  .note {{ font-size: 9px; color: #888; margin-top: 6px; }}
  .footer {{ margin-top: 16px; padding-top: 8px; border-top: 1px solid #ddd;
             font-size: 9px; color: #777; display: flex; justify-content: space-between; }}
  .sample {{ background: #fff3cd; border: 1px solid #ffe08a; color: #7a5b00;
             padding: 4px 8px; border-radius: 5px; font-size: 9.5px; display: inline-block;
             margin-bottom: 8px; }}
</style>
</head>
<body>
  <div class="sample">DOKUMENT PRZYKLADOWY, dane wygenerowane na potrzeby demonstracji. To nie jest raport realnego klienta.</div>
  <h1>Audyt zmarnowanego budzetu <span class="brand">Google Ads</span></h1>
  <div class="meta">Klient: {html.escape(client_name)} &nbsp;|&nbsp; Data: {today} &nbsp;|&nbsp;
     Okres danych: {r.period_days} dni &nbsp;|&nbsp; FluxLab, fluxlab.pl</div>

  <div class="hero">
    <div class="big">{_zl(r.monthly_recoverable)} / miesiac do odzyskania</div>
    <div class="sub">To ostrozny szacunek ({_pct(r.recovery_rate)} zmarnowanego budzetu),
       rocznie okolo {_zl(r.yearly_recoverable)}. Pieniadze wydane na klikniecia, ktore nie dowiozly ani jednej konwersji.</div>
  </div>

  <div class="cards">
    <div class="card"><div class="v">{_zl(r.total_cost)}</div><div class="l">Koszt calkowity ({r.period_days} dni)</div></div>
    <div class="card"><div class="v">{_zl(r.wasted_cost)}</div><div class="l">Wydane bez konwersji</div></div>
    <div class="card"><div class="v">{_pct(r.wasted_share)}</div><div class="l">Udzial marnotrawstwa</div></div>
    <div class="card"><div class="v">{r.wasted_term_count}</div><div class="l">Frazy bez konwersji</div></div>
  </div>

  <h2>Top {len(r.top_wasted)} najbardziej marnotrawnych fraz</h2>
  <table>
    <thead><tr><th class="n"></th><th>Wyszukiwane haslo</th><th class="num">Klikn.</th>
      <th class="num">Konw.</th><th class="num">Koszt</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="note">Kryterium: 0 konwersji oraz wiecej niz {r.min_clicks} klikniec w analizowanym okresie.</div>

  <h2>Sugerowane wykluczenia (negative keywords)</h2>
  <table>
    <thead><tr><th>Slowo / fraza do wykluczenia</th><th class="num">W ilu frazach</th>
      <th class="num">Zmarnowany koszt</th></tr></thead>
    <tbody>{neg_html}</tbody>
  </table>
  <div class="note">Analiza n-gramow: slowa powtarzajace sie w wielu marnotrawnych frazach.
     Przed dodaniem jako wykluczenie zawsze zweryfikuj, czy slowo nie wystepuje tez w frazach konwertujacych.</div>

  <div class="footer">
    <span>FluxLab, automatyzacja i optymalizacja Google Ads, fluxlab.pl</span>
    <span>Wygenerowano automatycznie z eksportu raportu Wyszukiwane hasla</span>
  </div>
</body>
</html>"""


def html_to_pdf(html_content: str, output_pdf: str | Path) -> Path:
    """Konwertuje HTML do PDF przez google-chrome-stable --headless --print-to-pdf."""
    chrome = (
        shutil.which("google-chrome-stable")
        or shutil.which("google-chrome")
        or shutil.which("chromium")
    )
    if not chrome:
        raise RuntimeError("Nie znaleziono google-chrome-stable/chromium w PATH.")

    output_pdf = Path(output_pdf).resolve()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html_content)
        tmp_html = f.name

    try:
        with tempfile.TemporaryDirectory() as profile:
            cmd = [
                chrome,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                f"--user-data-dir={profile}",
                "--no-pdf-header-footer",
                f"--print-to-pdf={output_pdf}",
                f"file://{tmp_html}",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if not output_pdf.exists():
            raise RuntimeError(
                f"Chrome nie wygenerowal PDF. stderr: {proc.stderr[:500]}"
            )
    finally:
        Path(tmp_html).unlink(missing_ok=True)
    return output_pdf
