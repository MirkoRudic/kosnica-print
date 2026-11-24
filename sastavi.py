#!/usr/bin/env python3
"""
Sastavlja static/index.html iz delova.

Interfejs se pise u tri fajla da bi se nalazilo sta se menja:
    static/deo_glava.html    <head> i CSS
    static/deo_telo.html     markup, sa oznakom __SPRAJT__ na mestu ikonica
    static/deo_skripta.html  <script> i zatvaranje strane
    static/ikone.svg         Tabler sprajt, ulepljuje se umesto __SPRAJT__

CSS i JS se ulepljuju u index.html, pa nema spoljnih fajlova koje bi
pregledac mogao da drzi u kesu (zato UI11 ovde nema sta da resava).

Pokretanje posle svake izmene dela:   python sastavi.py
"""
import os
import sys

OVDE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(OVDE, "static")


def procitaj(ime):
    with open(os.path.join(S, ime), "r", encoding="utf-8") as f:
        return f.read()


def main():
    telo = procitaj("deo_telo.html")
    if "__SPRAJT__" not in telo:
        print("deo_telo.html nema oznaku __SPRAJT__", file=sys.stderr)
        return 1
    strana = (procitaj("deo_glava.html")
              + telo.replace("__SPRAJT__", procitaj("ikone.svg").strip())
              + procitaj("deo_skripta.html"))
    put = os.path.join(S, "index.html")
    with open(put, "w", encoding="utf-8", newline="\n") as f:
        f.write(strana)
    print("index.html: %d KB" % (len(strana.encode("utf-8")) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
