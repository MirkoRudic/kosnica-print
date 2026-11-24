#!/usr/bin/env python3
"""
Biblioteka pripremljenih slika.

Priprema = izvorna slika + sva podesavanja + mera rama na kom je radjena.
Cuva se kao obicna fascikla, da se i bez aplikacije vidi sta je unutra:

    <biblioteka>/<naziv>/
        priprema.json     podesavanja, ram, datum
        izvor.<ext>       kopija izvorne slike, netaknuta
        pregled.jpg       slicica za listu

Fascikla biblioteke se bira u Podesavanjima. Podrazumevano ide u Dokumenta,
da korisnik moze da je kopira ili bekapuje bez aplikacije.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time

OVDE = os.path.dirname(os.path.abspath(__file__))
PODACI = os.path.join(OVDE, "podaci")


def podrazumevana_fascikla() -> str:
    dom = os.path.expanduser("~")
    for ime in ("Documents", "Dokumenti"):
        p = os.path.join(dom, ime)
        if os.path.isdir(p):
            return os.path.join(p, "Foto Ramići")
    return os.path.join(dom, "Foto Ramići")


def _bezbedno(ime: str) -> str:
    ime = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (ime or "").strip())
    ime = re.sub(r"\s+", " ", ime).strip(" .")
    return ime[:80] or "priprema"


def _jedinstveno(koren: str, ime: str) -> str:
    kandidat, n = ime, 2
    while os.path.exists(os.path.join(koren, kandidat)):
        kandidat = "%s (%d)" % (ime, n)
        n += 1
    return kandidat


def osiguraj(koren: str) -> str:
    os.makedirs(koren, exist_ok=True)
    return koren


# ------------------------------------------------------------------ pisanje

def sacuvaj(koren: str, naziv: str, izvor_putanja: str, pod: dict,
            ram: dict, pregled=None, prepisi: str | None = None) -> dict:
    """
    Snimi pripremu.

    Podrazumevano se NIKAD ne prepisuje postojeca: ako je naziv zauzet,
    dobija broj na kraju. Prepisivanje se trazi izricito, preko `prepisi`.
    """
    osiguraj(koren)
    fas = prepisi if prepisi else _jedinstveno(koren, _bezbedno(naziv))
    put = os.path.join(koren, fas)
    os.makedirs(put, exist_ok=True)

    nastavak = os.path.splitext(izvor_putanja)[1].lower() or ".jpg"
    cilj = os.path.join(put, "izvor" + nastavak)
    if os.path.abspath(izvor_putanja) != os.path.abspath(cilj):
        for stari in os.listdir(put):
            if stari.startswith("izvor."):
                os.remove(os.path.join(put, stari))
        shutil.copy2(izvor_putanja, cilj)

    if pregled is not None:
        p = pregled.copy()
        p.thumbnail((360, 360))
        p.convert("RGB").save(os.path.join(put, "pregled.jpg"), quality=86)

    zapis = {
        "naziv": naziv or fas,
        "fascikla": fas,
        "izvor": os.path.basename(cilj),
        "izvorno_ime": os.path.basename(izvor_putanja),
        "podesavanja": pod,
        "ram": ram,
        "izmenjeno": time.time(),
    }
    with open(os.path.join(put, "priprema.json"), "w", encoding="utf-8") as f:
        json.dump(zapis, f, ensure_ascii=False, indent=2)
    return zapis


def obrisi(koren: str, fascikla: str) -> bool:
    put = os.path.join(koren, _bezbedno(fascikla))
    if not os.path.isdir(put) or not os.path.exists(os.path.join(put, "priprema.json")):
        return False
    shutil.rmtree(put)
    return True


# ------------------------------------------------------------------ citanje

def spisak(koren: str) -> list[dict]:
    if not os.path.isdir(koren):
        return []
    out = []
    for ime in os.listdir(koren):
        put = os.path.join(koren, ime)
        fajl = os.path.join(put, "priprema.json")
        if not os.path.isfile(fajl):
            continue
        try:
            with open(fajl, "r", encoding="utf-8") as f:
                z = json.load(f)
        except Exception:
            continue
        z["fascikla"] = ime
        z["ima_pregled"] = os.path.isfile(os.path.join(put, "pregled.jpg"))
        out.append(z)
    out.sort(key=lambda z: z.get("izmenjeno", 0), reverse=True)
    return out


def ucitaj(koren: str, fascikla: str) -> dict | None:
    put = os.path.join(koren, _bezbedno(fascikla))
    fajl = os.path.join(put, "priprema.json")
    if not os.path.isfile(fajl):
        return None
    with open(fajl, "r", encoding="utf-8") as f:
        z = json.load(f)
    z["fascikla"] = fascikla
    z["putanja_izvora"] = os.path.join(put, z.get("izvor", ""))
    if not os.path.isfile(z["putanja_izvora"]):
        for ime in os.listdir(put):
            if ime.startswith("izvor."):
                z["putanja_izvora"] = os.path.join(put, ime)
                break
    return z


def putanja_pregleda(koren: str, fascikla: str) -> str | None:
    p = os.path.join(koren, _bezbedno(fascikla), "pregled.jpg")
    return p if os.path.isfile(p) else None
