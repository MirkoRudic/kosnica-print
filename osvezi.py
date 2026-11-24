#!/usr/bin/env python3
"""Proverava da li podignuti server ima nove rute za stampu."""
import json
import urllib.request
import urllib.error

BAZA = "http://127.0.0.1:8733"


def stanje(putanja, metod="GET"):
    z = urllib.request.Request(BAZA + putanja, method=metod)
    try:
        with urllib.request.urlopen(z, timeout=6) as o:
            return o.status, o.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, "%s: %s" % (type(e).__name__, e)


k, telo = stanje("/api/podaci")
print("GET /api/podaci ->", k)
if k == 200:
    try:
        d = json.loads(telo)
        s = d["podesavanja"]["stampaci"][0] if d["podesavanja"].get("stampaci") else {}
        print("  ram:", d["ram"]["naziv"], d["ram"]["rez"])
        print("  raspored:", d["raspored"])
        print("  kalibracija:", s.get("kalibracija"))
    except Exception as e:
        print("  (ne mogu da raspakujem:", e, ")")

for put in ("/api/kontrolni_stampa", "/api/stampaj", "/api/stampac"):
    k, _ = stanje(put)
    print("GET %-24s -> %s  %s" % (put, k, "RUTA POSTOJI" if k == 405 else
                                   ("NEMA RUTE - stari server" if k == 404 else "?")))

k, telo = stanje("/api/stampaci")
print("GET /api/stampaci ->", k)
if k == 200:
    try:
        d = json.loads(telo)
        print("  izabrani:", d.get("izabrani"), " medij:", d.get("medij"), " ulaz:", d.get("ulaz"))
        for p in d.get("papiri", []):
            print("    papir %6s  %s" % (p["sifra"], p["ime"]))
        for p in d.get("ulazi", []):
            print("    ulaz  %6s  %s" % (p["sifra"], p["ime"]))
    except Exception as e:
        print("  (ne mogu da raspakujem:", e, ")")
