#!/usr/bin/env python3
"""Suvi hod: snimi DEVMODE, izracunaj geometriju tabaka, nista ne stampaj."""
import json, os, sys, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def red(t):
    print("\n" + "=" * 60); print(t); print("=" * 60)

try:
    import stampa_win, profili, tabak
    from obrada import Podesavanja, pripremi
except Exception:
    traceback.print_exc(); sys.exit(1)

red("STAMPACI")
for s in stampa_win.lista_stampaca():
    print("  %-40s %s" % (s["ime"], s["drajver"]))
podr = stampa_win.podrazumevani()
print("\npodrazumevani:", podr)

meta = [s["ime"] for s in stampa_win.lista_stampaca() if "L18050" in s["ime"].upper()]
cilj = meta[0] if meta else podr
print("ciljam:", cilj)

red("PODESAVANJA DRAJVERA (A4 nametnut, sistem se ne dira)")
try:
    print(json.dumps(stampa_win.procitaj_podesavanja(cilj), ensure_ascii=False, indent=2))
except Exception:
    traceback.print_exc()

red("GEOMETRIJA TABAKA - SUVI HOD")
try:
    d = profili.ucitaj(); ram = profili.ram_iz(d); t = d["tabak"]
    f = profili.faktor(d)
    rasp = tabak.raspored(ram, t, f, True)
    print("raspored:", rasp)
    from PIL import Image
    lazna = Image.new("RGB", (400, 290), (220, 210, 200))
    izv = stampa_win.odstampaj_tabake([lazna] * 4, ram, t, rasp, f,
                                      stampac=cilj, lenjir=True, probno=True)
    print(json.dumps(izv, ensure_ascii=False, indent=2))
except Exception:
    traceback.print_exc()

red("KRAJ")
