#!/usr/bin/env python3
import json, os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stampa_win, profili
d = profili.ucitaj(); ram = profili.ram_iz(d); t = d["tabak"]
f = profili.faktor(d)
meta = [s["ime"] for s in stampa_win.lista_stampaca() if "L18050" in s["ime"].upper()]
cilj = meta[0] if meta else stampa_win.podrazumevani()
probno = "--probno" in sys.argv
print("stampac:", cilj, " faktor:", f, " probno:", probno)
try:
    print(json.dumps(stampa_win.odstampaj_kontrolni(ram, t, f, cilj, probno=probno),
                     ensure_ascii=False, indent=2))
    print("\nPOSLATO" if not probno else "\nSAMO PRORACUN")
except Exception:
    traceback.print_exc()
