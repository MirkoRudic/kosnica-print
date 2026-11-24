#!/usr/bin/env python3
"""
Profili ramova i kalibracija stampaca.

Sve se cuva kao obican JSON pored programa, da moze rukom da se pogleda
i prepravi. Mere ramova su IZMERENE na odstampanom komadu, ne projektovane -
PLA se skuplja oko 0.7% i to se ne racuna unapred nego meri.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from obrada import Ram

MAPA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "podaci")
FAJL = os.path.join(MAPA, "profili.json")

PODRAZUMEVANO = {
    "ramovi": [
        {
            "naziv": "Barokni 95 x 74 (v9)",
            "prozor_s": 69.10, "prozor_v": 47.70,
            "rez_s": 73.10, "rez_v": 51.70,
            "napust": 3.0, "ostro": 1.5,
            "beleska": "Prozor izmeren sublerom na odstampanom ramu: 69.10 x 47.70 "
                       "naspram projektovanih 69.60 x 48.00 (skupljanje 0.72% / 0.62%). "
                       "Rez = procenjeni prorez 73.48 x 52.09 minus 0.4 mm zazora.",
        }
    ],
    "izabrani_ram": 0,
    "stampaci": [
        {
            "naziv": "Epson L18050 - magneti",
            "kalibracija": 100.0,       # procenat; 150/izmereno*100
            "sistemsko_ime": None,      # ime stampaca u Windowsu
            "medij": None,              # Epsonova sifra tipa papira (326 = Matte)
            "ulaz": None,               # sifra ulaza (261 = zadnji ulaz)
            "papir": "po drajveru",     # samo opis za prikaz
        }
    ],
    "izabrani_stampac": 0,
    "tabak": {"sirina": 210.0, "visina": 297.0, "ivica": 10.0, "razmak": 12.0,
              "lenjir": True, "lenjir_duzina": 150.0},
    "app": {
        "tema": "svetla",            # svetla | tamna | sepija
        "biblioteka": None,          # fascikla sa sacuvanim pripremama
        "svi_papiri": False,         # prikazi ceo spisak iz drajvera
        "obrezi_rub": False,         # skidanje belog ruba skenera
        "skupljanje": 0.7,           # procenat, za predlog mere iz STL-a
    },
}

# Papiri koji se nude po imenu; ostali samo ako se ukljuci "svi_papiri".
KRATKI_PAPIRI = {
    1: "Običan papir",
    326: "Mat foto papir",
    325: "Sjajni foto papir",
}


def _osiguraj():
    os.makedirs(MAPA, exist_ok=True)
    if not os.path.exists(FAJL):
        sacuvaj(PODRAZUMEVANO)


def ucitaj() -> dict:
    _osiguraj()
    with open(FAJL, "r", encoding="utf-8") as f:
        d = json.load(f)
    for k, v in PODRAZUMEVANO.items():      # dopuni ako je fajl stariji
        d.setdefault(k, v)
    return d


def sacuvaj(d: dict) -> None:
    os.makedirs(MAPA, exist_ok=True)
    with open(FAJL, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def app_iz(d: dict) -> dict:
    a = d.setdefault("app", {})
    for k, v in PODRAZUMEVANO["app"].items():
        a.setdefault(k, v)
    if not a.get("biblioteka"):
        import biblioteka
        a["biblioteka"] = biblioteka.podrazumevana_fascikla()
    return a


def ram_iz(d: dict, i: int | None = None) -> Ram:
    i = d["izabrani_ram"] if i is None else i
    r = d["ramovi"][max(0, min(i, len(d["ramovi"]) - 1))]
    return Ram(naziv=r["naziv"], prozor_s=r["prozor_s"], prozor_v=r["prozor_v"],
               rez_s=r["rez_s"], rez_v=r["rez_v"],
               napust=r.get("napust", 3.0), ostro=r.get("ostro", 1.5))


def stampac_iz(d: dict, i: int | None = None) -> dict:
    i = d["izabrani_stampac"] if i is None else i
    return d["stampaci"][max(0, min(i, len(d["stampaci"]) - 1))]


def faktor(d: dict) -> float:
    """Mnozitelj koji se primenjuje pri renderovanju, ne u dijalogu za stampu."""
    return stampac_iz(d).get("kalibracija", 100.0) / 100.0


def iz_merenja(izmereno_mm: float, nominalno_mm: float = 150.0) -> float:
    """Faktor iz izmerene duzine kalibracionog lenjira, u procentima."""
    if izmereno_mm <= 0:
        return 100.0
    return round(nominalno_mm / izmereno_mm * 100.0, 2)


def dodaj_ram(d: dict, r: Ram, beleska: str = "") -> dict:
    z = asdict(r)
    z["beleska"] = beleska
    d["ramovi"].append(z)
    d["izabrani_ram"] = len(d["ramovi"]) - 1
    sacuvaj(d)
    return d


if __name__ == "__main__":
    d = ucitaj()
    r = ram_iz(d)
    print("ram        %s" % r.naziv)
    print("  prozor   %.2f x %.2f mm" % (r.prozor_s, r.prozor_v))
    print("  rez      %.2f x %.2f mm" % (r.rez_s, r.rez_v))
    print("  preklop  %.2f / %.2f mm po strani" % (r.preklop_s, r.preklop_v))
    print("  puna     %.2f x %.2f mm (sa napustom %.1f)" % (r.puna_s, r.puna_v, r.napust))
    print("  odnos    %.4f" % r.odnos)
    print("stampac    %s, kalibracija %.2f %%" % (stampac_iz(d)["naziv"],
                                                  stampac_iz(d)["kalibracija"]))
    for izm in (150.0, 151.0, 149.0):
        print("  izmereno %.1f -> faktor %.2f %%" % (izm, iz_merenja(izm)))
