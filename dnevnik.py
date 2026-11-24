#!/usr/bin/env python3
"""
Dnevnik rada aplikacije - tanak sloj nad applog.py (PRAVILA.md L1-L6).

Jedan fajl po danu: podaci/logs/kosnica-print_YYYY-MM-DD.log

    2026-11-19 13:40:02  INFO   app.uvoz       sken.pdf  piksela=3308x4678
    2026-11-19 13:41:55  INFO   app.stampa     6 otisaka na 1 tabaku, L18050
    2026-11-19 13:42:10  ERROR  app.stampa     3 slike na L18050
    Traceback (most recent call last): ...

Zasto sloj, a ne applog direktno: upisuje se sa dvadesetak mesta kao
dnevnik.upisi("stampa", ...). Radnja ide u ime podlogera, pa se u fajlu
cita kao kolona, a pozivi u server.py ostaju nepromenjeni.
"""
from __future__ import annotations

import os

import applog

OVDE = os.path.dirname(os.path.abspath(__file__))
MAPA = os.path.join(OVDE, "podaci", "logs")
IME = "kosnica-print"

applog.setup(MAPA, IME)
applog.auto_trim(500)          # L1: automatsko brisanje samo iznad 500 MB


def _spoji(poruka: str, dodatno: dict) -> str:
    if dodatno:
        delovi = " ".join("%s=%s" % (k, v) for k, v in dodatno.items())
        poruka = (poruka + "  " + delovi).strip()
    return poruka or "-"


def upisi(radnja: str, poruka: str = "", **dodatno) -> None:
    """Jedan red u dnevnik. Nikad ne ruši aplikaciju ako pisanje ne uspe (L3)."""
    applog.get(radnja).info("%s", _spoji(poruka, dodatno))


def greska(radnja: str, izuzetak: BaseException, poruka: str = "") -> None:
    """Greška sa punim tracebackom ispod reda (L4)."""
    applog.get(radnja).error(
        "%s", poruka or "greška",
        exc_info=(type(izuzetak), izuzetak, izuzetak.__traceback__))


def procitaj(dana: int = 2, samo_greske: bool = False,
             trazi: str | None = None, koliko: int = 800) -> list[str]:
    """Poslednji redovi, najnoviji na kraju."""
    return applog.read(days=dana, problems_only=samo_greske,
                       query=trazi, limit=koliko)


def velicina_mb() -> float:
    return applog.size_mb()


def broj_fajlova() -> int:
    return len(applog.files())


def obrisi_starije(dana: int) -> int:
    n = applog.delete_older_than(dana)
    upisi("dnevnik", "obrisano starije od %d dana" % dana, fajlova=n)
    return n
