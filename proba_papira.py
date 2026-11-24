#!/usr/bin/env python3
"""Proverava da li drajver prihvata MediaType / kvalitet nametnut iz koda."""
import win32con
import win32print

DM_IN_BUFFER = 8
DM_OUT_BUFFER = 2
DM_MEDIATYPE = 0x08000000
DM_PRINTQUALITY = 0x00000400
DM_YRESOLUTION = 0x00002000
DM_DEFAULTSOURCE = 0x00000200
DM_PAPERSIZE = 0x00000002

POLJA = ("PaperSize", "DefaultSource", "MediaType", "PrintQuality",
         "YResolution", "Color", "Orientation")


def snimak(dm):
    return {k: getattr(dm, k, None) for k in POLJA}


def nadji():
    for s in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 2):
        if "L18050" in s["pPrinterName"].upper():
            return s["pPrinterName"]
    return win32print.GetDefaultPrinter()


def proba(ime, medij=None, kvalitet=None, izvor=None):
    h = win32print.OpenPrinter(ime)
    try:
        dm = win32print.GetPrinter(h, 2)["pDevMode"]
        pre = snimak(dm)
        dm.PaperSize = 9
        dm.Fields |= DM_PAPERSIZE
        if medij is not None:
            dm.MediaType = medij
            dm.Fields |= DM_MEDIATYPE
        if izvor is not None:
            dm.DefaultSource = izvor
            dm.Fields |= DM_DEFAULTSOURCE
        if kvalitet is not None:
            dm.PrintQuality = kvalitet
            dm.YResolution = kvalitet
            dm.Fields |= (DM_PRINTQUALITY | DM_YRESOLUTION)
        win32print.DocumentProperties(0, h, ime, dm, dm, DM_IN_BUFFER | DM_OUT_BUFFER)
        posle = snimak(dm)
    finally:
        win32print.ClosePrinter(h)
    return pre, posle


ime = nadji()
print("STAMPAC:", ime, "\n")

sluchaji = [
    ("polazno (samo A4)", None, None, None),
    ("Epson Matte 326", 326, None, None),
    ("Epson Matte 326 + 1440", 326, 1440, None),
    ("Epson Matte 326 + 2880", 326, 2880, None),
    ("Epson Matte 326 + zadnji ulaz", 326, None, 261),
    ("Premium Glossy 325", 325, None, None),
    ("Photo Quality Ink Jet 318", 318, None, None),
    ("Plain 1 + 360", 1, 360, None),
]

for naziv, m, k, i in sluchaji:
    try:
        pre, posle = proba(ime, m, k, i)
    except Exception as e:
        print("%-32s GRESKA: %s" % (naziv, e))
        continue
    promene = []
    for kl in POLJA:
        if pre[kl] != posle[kl]:
            promene.append("%s %s->%s" % (kl, pre[kl], posle[kl]))
    print("%-32s %s" % (naziv, ", ".join(promene) if promene else "bez promene"))
    print("%-32s   rezultat: %s" % ("", posle))

print("\nNAPOMENA: ako 'MediaType' posle merge-a ima trazenu sifru, drajver je prihvatio.")
