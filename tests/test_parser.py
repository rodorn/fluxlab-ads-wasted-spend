from fluxlab_ads.parser import ParseError, parse_csv, parse_number
import pytest


class TestParseNumber:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1 234,56", 1234.56),  # PL: spacja tysiace, przecinek dziesietny
            ("1,234.56", 1234.56),  # EN: przecinek tysiace, kropka dziesietna
            ("1234.56", 1234.56),
            ("12 zl", 12.0),
            ("0", 0.0),
            ("--", 0.0),
            ("", 0.0),
            ("1'234.5", 1234.5),  # apostrof jako separator
            ("45,00 zl", 45.0),
            ("3", 3.0),
            ("1 000", 1000.0),
            ("2 500,00 zl", 2500.0),
        ],
    )
    def test_parse_number(self, raw, expected):
        assert parse_number(raw) == pytest.approx(expected)

    def test_nbsp_thousands(self):
        assert parse_number("1 234,56") == pytest.approx(1234.56)


PL_SEMICOLON = """Raport wyszukiwanych hasel
Zakres dat: 2026-08-01 - 2026-08-30
Wyszukiwane haslo;Koszt (PLN);Klikniecia;Konwersje;Wyswietlenia
naprawa telefonu za darmo;120,50;15;0;800
serwis iphone warszawa;45,00;5;2;300
darmowa wycena telefonu;88,00;9;0;500
suma: konto;253,50;29;2;1600
"""

EN_COMMA = """Search term,Cost,Clicks,Conversions
free phone repair,120.50,15,0
iphone service warsaw,45.00,5,2
"""

TAB_SEP = "Wyszukiwane haslo\tKoszt\tKlikniecia\tKonwersje\nx darmo\t50,00\t10\t0\n"


class TestParseCsv:
    def test_polish_semicolon_with_metadata(self):
        rows = parse_csv(PL_SEMICOLON)
        assert len(rows) == 3  # wiersz 'suma' pominiety
        r0 = rows[0]
        assert r0.term == "naprawa telefonu za darmo"
        assert r0.cost == pytest.approx(120.50)
        assert r0.clicks == 15
        assert r0.conversions == 0

    def test_english_comma(self):
        rows = parse_csv(EN_COMMA)
        assert len(rows) == 2
        assert rows[0].term == "free phone repair"
        assert rows[0].cost == pytest.approx(120.50)

    def test_tab_separated(self):
        rows = parse_csv(TAB_SEP)
        assert len(rows) == 1
        assert rows[0].clicks == 10

    def test_utf8_bom(self):
        rows = parse_csv(("﻿" + EN_COMMA).encode("utf-8"))
        assert len(rows) == 2

    def test_utf16_bytes(self):
        rows = parse_csv(PL_SEMICOLON.encode("utf-16"))
        assert len(rows) == 3

    def test_missing_columns_raises(self):
        with pytest.raises(ParseError):
            parse_csv("foo,bar\n1,2\n")

    def test_empty_raises(self):
        with pytest.raises(ParseError):
            parse_csv("")
