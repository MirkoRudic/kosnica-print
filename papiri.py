#!/usr/bin/env python3
"""Ispituje drajver: koje tipove papira, kvalitete, izvore i formate nudi."""
import json
import sys

import win32print

DC_PAPERS = 2
DC_PAPERSIZE = 3
DC_BINS = 6
DC_BINNAMES = 12
DC_ENUMRESOLUTIONS = 13
DC_PAPERNAMES = 16
DC_COLORDEVICE = 32
DC_MEDIATYPENAMES = 34
DC_MEDIATYPES = 35


def sposobnost(ime, port, sta):
    try:
        return win32print.DeviceCapabilities(ime, port, sta)
    except Exception as e:
        return "GRESKA: %s" % e


def ispitaj(ime):
    h = win32print.OpenPrinter(ime)
    try:
        inf = win32print.GetPrinter(h, 2)
    finally:
        win32print.ClosePrinter(h)
    port = inf["pPortName"]

    imena = sposobnost(ime, port, DC_MEDIATYPENAMES)
    sifre = sposobnost(ime, port, DC_MEDIATYPES)
    mediji = []
    if isinstance(imena, (list, tuple)) and isinstance(sifre, (list, tuple)):
        for n, s in zip(imena, sifre):
            mediji.append({"sifra": s, "ime": n})

    kante_i = sposobnost(ime, port, DC_BINNAMES)
    kante_s = sposobnost(ime, port, DC_BINS)
    kante = []
    if isinstance(kante_i, (list, tuple)) and isinstance(kante_s, (list, tuple)):
        for n, s in zip(kante_i, kante_s):
            kante.append({"sifra": s, "ime": n})

    pap_i = sposobnost(ime, port, DC_PAPERNAMES)
    pap_s = sposobnost(ime, port, DC_PAPERS)
    papiri = []
    if isinstance(pap_i, (list, tuple)) and isinstance(pap_s, (list, tuple)):
        for n, s in zip(pap_i, pap_s):
            papiri.append({"sifra": s, "ime": n})

    return {
        "stampac": ime,
        "port": port,
        "u_boji": sposobnost(ime, port, DC_COLORDEVICE),
        "rezolucije": sposobnost(ime, port, DC_ENUMRESOLUTIONS),
        "tipovi_papira": mediji,
        "izvori": kante,
        "formati": papiri,
    }


if __name__ == "__main__":
    cilj = sys.argv[1] if len(sys.argv) > 1 else None
    if not cilj:
        for s in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 2):
            if "L18050" in s["pPrinterName"].upper():
                cilj = s["pPrinterName"]
                break
    if not cilj:
        cilj = win32print.GetDefaultPrinter()

    d = ispitaj(cilj)
    print("STAMPAC:", d["stampac"], " port:", d["port"])
    print("u boji:", d["u_boji"])
    print("\nREZOLUCIJE:")
    print(" ", d["rezolucije"])
    print("\nTIPOVI PAPIRA (%s):" % (len(d["tipovi_papira"]) if isinstance(d["tipovi_papira"], list) else "?"))
    for m in d["tipovi_papira"]:
        print("  %6s  %s" % (m["sifra"], m["ime"]))
    print("\nIZVORI:")
    for m in d["izvori"]:
        print("  %6s  %s" % (m["sifra"], m["ime"]))
    print("\nFORMATI (prvih 20):")
    for m in d["formati"][:20]:
        print("  %6s  %s" % (m["sifra"], m["ime"]))

    with open("papiri.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("\nsnimljeno u papiri.json")
