# FluxLab, Audyt zmarnowanego budzetu Google Ads

Narzedzie do wykrywania budzetu Google Ads przepalanego na frazy, ktore nie dowoza
konwersji, plus gotowy skrypt-straznik, ktory utrzymuje konto czyste automatycznie.

Typowo 20 do 40 procent budzetu malego konta idzie na wyszukiwane hasla z zerem
konwersji. To narzedzie liczy dokladna kwote i daje liste wykluczen do wklejenia.

## Co robi

1. **Analizator (Python, CLI)** wczytuje eksport CSV raportu _Wyszukiwane hasla_
   z Google Ads i liczy:
   - sume kosztu fraz z 0 konwersji i wiecej niz N klikniec (zmarnowany budzet),
   - top 20 najbardziej marnotrawnych fraz,
   - sugerowana liste wykluczen (negative keywords) na podstawie analizy n-gramow,
   - oszczednosc miesieczna i roczna (ostrozny szacunek).
   - Odporny na rozne formaty eksportu: polskie i angielskie naglowki, separatory
     `;` `,` `\t`, przecinek lub kropka jako separator dziesietny, spacje w tysiacach,
     symbol waluty, wiersze metadanych przed tabela, kodowanie UTF-8 i UTF-16.
2. **Raport HTML do PDF** (1 do 2 stron, po polsku) z twarda liczba
   "X zl/mc do odzyskania", generowany przez `google-chrome-stable --headless --print-to-pdf`.
3. **Google Ads Script** (`google-ads-script/guardian.js`), ktory dziala w koncie klienta:
   co noc dodaje jako wykluczenia frazy z kosztem powyzej progu i 0 konwersji w 30 dni
   oraz wysyla alert mailem.

## Wymagania

- Python 3.10+ (tylko biblioteka standardowa, bez zaleznosci runtime).
- `google-chrome-stable` lub `chromium` w PATH (tylko do generowania PDF).
- `pytest` do testow (opcjonalnie).

## Instalacja

```bash
git clone https://github.com/rodorn/fluxlab-ads-wasted-spend.git
cd fluxlab-ads-wasted-spend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"    # lub: pip install pytest  (runtime nie wymaga niczego)
```

## Uzycie

```bash
# Raport tekstowy w terminalu
python -m fluxlab_ads.cli examples/PRZYKLAD_wyszukiwane_hasla.csv

# Pelny raport PDF dla klienta
python -m fluxlab_ads.cli sciezka/do/wyszukiwane_hasla.csv \
    --client "Nazwa klienta" --days 30 --pdf out/raport.pdf

# Wynik jako JSON (do dalszej automatyzacji)
python -m fluxlab_ads.cli plik.csv --json
```

Parametry:

| Flaga             | Domyslnie | Znaczenie                                                |
| ----------------- | --------- | -------------------------------------------------------- |
| `--min-clicks`    | 3         | Ile klikniec musi miec fraza, by uznac ja za marnotrawna |
| `--days`          | 30        | Dlugosc okresu eksportu (do przeliczenia na miesiac)     |
| `--recovery-rate` | 0.7       | Ostrozny udzial realnie mozliwy do odzyskania            |
| `--pdf PLIK`      | brak      | Wygeneruj PDF                                            |
| `--html PLIK`     | brak      | Zapisz sam HTML                                          |
| `--json`          | wyl.      | Wypisz wynik jako JSON                                   |

## Skad wziac plik CSV (dane klienta, read-only)

Klient nie musi dawac zadnych hasel ani platnosci. Wystarczy dostep **tylko do odczytu**
albo sam eksport CSV:

**Wariant A, dostep read-only (zalecany dla retainera):**

1. Klient w Google Ads: _Narzedzia i ustawienia > Dostep i bezpieczenstwo_.
2. Dodaje moj adres e-mail z poziomem uprawnien **Tylko do odczytu**.
3. Klika zapisz. Cofniecie dostepu zajmuje 10 sekund w tym samym miejscu.

**Wariant B, sam eksport CSV (dla jednorazowego mini-audytu):**

1. Google Ads > _Statystyki i raporty > Wyszukiwane hasla_ (albo zakladka
   _Wyszukiwane hasla_ w kampanii).
2. Zakres dat: ostatnie 30 dni.
3. Przycisk pobierania > CSV.
4. Klient przesyla plik mailem. Zadne haslo ani dostep nie sa potrzebne.

## Google Ads Script, skrypt-straznik (w koncie klienta)

Plik: `google-ads-script/guardian.js`

1. W koncie klienta: _Narzedzia i ustawienia > Zbiorcze dzialania > Skrypty_.
2. Kliknij `+`, wklej cala zawartosc `guardian.js`.
3. Na gorze pliku ustaw w obiekcie `CONFIG`:
   - `EMAIL` na adres, ktory ma dostawac alerty,
   - `COST_THRESHOLD` i `MIN_CLICKS` wedlug progu z audytu,
   - `DRY_RUN` zostaw `true` na pierwszy przebieg (skrypt tylko przysle raport mailem,
     nic nie zmieni).
4. _Podglad_ i autoryzacja konta, potem _Uruchom_. Sprawdz maila z podsumowaniem.
5. Gdy raport wyglada dobrze, zmien `DRY_RUN` na `false` i ustaw harmonogram
   (_Uruchamiaj co dzien_, np. 03:00). Od teraz skrypt sam dodaje wykluczenia
   i codziennie raportuje mailem, ile budzetu ochronil.

Skrypt tworzy wspoldzielona liste wykluczen `FluxLab - Auto Wasted-Spend` i podpina ja
pod aktywne kampanie. Dodaje wykluczenia w dopasowaniu dokladnym (mozna zmienic
`MATCH_TYPE`). Nic nie usuwa i nie zmienia stawek.

## Przykladowy raport

- Przykladowy eksport: `examples/PRZYKLAD_wyszukiwane_hasla.csv`
  (dane demonstracyjne, wyraznie oznaczone, to nie jest konto realnego klienta).
- Wygenerowany raport: `out/sample_audyt.pdf`.

Na tym przykladzie narzedzie wykrywa okolo 51 procent budzetu wydawanego bez konwersji
i okolo 1400 zl miesiecznie do odzyskania.

## Cennik

- **Mini-audyt: 690 zl** (jednorazowo). Dostajesz raport PDF z konkretna kwota
  do odzyskania i gotowa lista wykluczen. **Gwarancja: jesli nie znajde min. 500 zl/mc
  do odzyskania, zwracam cala kwote.**
- **Retainer: 400 do 600 zl/mc.** Skrypt-straznik pilnuje konta codziennie plus
  comiesieczny przeglad marnotrawstwa i optymalizacja wykluczen.

## Bezpieczenstwo i prywatnosc

- Zero sekretow w kodzie. Skrypt-straznik dziala w koncie klienta, nie tu.
- Analizator dziala lokalnie na pliku CSV. Nic nie wysyla do sieci.
- Raporty realnych klientow sa ignorowane przez `.gitignore` i nie trafiaja do repo.

## Testy

```bash
python -m pytest -q
```

## Licencja

Kod wewnetrzny FluxLab. Wszelkie prawa zastrzezone.

---

Zbudowane przez FluxLab, https://fluxlab.pl. Automatyzacja procesow i wdrozenia AI dla malych firm.
