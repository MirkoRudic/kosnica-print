#!/usr/bin/env python3
"""Proverava da li server ima sve nove rute i da li stranica nosi novo ime."""
import json, urllib.request, urllib.error
B = "http://127.0.0.1:8733"

def zovi(put, metod="GET"):
    try:
        with urllib.request.urlopen(urllib.request.Request(B+put, method=metod), timeout=10) as o:
            return o.status, o.read(200000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return 0, str(e).encode()

k, telo = zovi("/")
print("GET /            ->", k, " naslov sadrzi 'Foto Ramici':",
      b"Foto Rami" in telo, " tabova:", telo.count(b'data-tab='))
for p, m, oc in [("/api/podaci","GET",200), ("/api/biblioteka","GET",200),
                 ("/api/tabak_pregled","GET",200), ("/api/preset_slika/sepija","GET",200),
                 ("/api/tabak_maks","POST",200), ("/api/ram","POST",400),
                 ("/api/stl","POST",400), ("/api/app","POST",200),
                 ("/api/izaberi_ram/0","POST",200)]:
    k, t = zovi(p, m)
    print("%-6s %-26s -> %-4s %s" % (m, p, k, "OK" if k == oc else "<<< PROVERI"))
k, t = zovi("/api/podaci")
if k == 200:
    d = json.loads(t)
    print("popune:", [x["ime"] for x in d.get("popune", [])])
    print("app:", d.get("app"))
