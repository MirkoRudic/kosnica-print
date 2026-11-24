#!/usr/bin/env python3
"""Cita ceo DEVMODE (javni + Epsonov privatni blok) preko ctypes.

Cilj: utvrditi da li privatni blok prati promenu MediaType-a.
"""
import ctypes
import ctypes.wintypes as w
import hashlib

import win32print

DM_OUT_BUFFER = 2
DM_IN_BUFFER = 8
DM_MEDIATYPE = 0x08000000
DM_PAPERSIZE = 0x00000002

CCHDEVICENAME = 32
CCHFORMNAME = 32


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", w.WCHAR * CCHDEVICENAME),
        ("dmSpecVersion", w.WORD),
        ("dmDriverVersion", w.WORD),
        ("dmSize", w.WORD),
        ("dmDriverExtra", w.WORD),
        ("dmFields", w.DWORD),
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", w.WCHAR * CCHFORMNAME),
        ("dmLogPixels", w.WORD),
        ("dmBitsPerPel", w.DWORD),
        ("dmPelsWidth", w.DWORD),
        ("dmPelsHeight", w.DWORD),
        ("dmDisplayFlags", w.DWORD),
        ("dmDisplayFrequency", w.DWORD),
        ("dmICMMethod", w.DWORD),
        ("dmICMIntent", w.DWORD),
        ("dmMediaType", w.DWORD),
        ("dmDitherType", w.DWORD),
        ("dmReserved1", w.DWORD),
        ("dmReserved2", w.DWORD),
        ("dmPanningWidth", w.DWORD),
        ("dmPanningHeight", w.DWORD),
    ]


winspool = ctypes.WinDLL("winspool.drv")
DocumentPropertiesW = winspool.DocumentPropertiesW
DocumentPropertiesW.argtypes = [w.HWND, w.HANDLE, w.LPWSTR,
                                ctypes.c_void_p, ctypes.c_void_p, w.DWORD]
DocumentPropertiesW.restype = ctypes.c_long


def uzmi(ime):
    """Vraca (bafer, velicina) sa tekucim podesavanjima drajvera."""
    h = win32print.OpenPrinter(ime)
    try:
        hp = h.handle if hasattr(h, "handle") else int(h)
        n = DocumentPropertiesW(0, hp, ime, None, None, 0)
        if n <= 0:
            raise OSError("DocumentProperties velicina = %d" % n)
        buf = ctypes.create_string_buffer(n)
        r = DocumentPropertiesW(0, hp, ime, buf, None, DM_OUT_BUFFER)
        if r < 0:
            raise OSError("DocumentProperties citanje = %d" % r)
        return buf, n
    finally:
        win32print.ClosePrinter(h)


def spoji(ime, buf, n):
    """Propusta izmenjeni bafer kroz drajver (ulaz i izlaz isti bafer)."""
    h = win32print.OpenPrinter(ime)
    try:
        hp = h.handle if hasattr(h, "handle") else int(h)
        izlaz = ctypes.create_string_buffer(n)
        r = DocumentPropertiesW(0, hp, ime, izlaz, buf, DM_IN_BUFFER | DM_OUT_BUFFER)
        if r < 0:
            raise OSError("DocumentProperties merge = %d" % r)
        return izlaz
    finally:
        win32print.ClosePrinter(h)


def dm(buf):
    return ctypes.cast(buf, ctypes.POINTER(DEVMODEW)).contents


def privatni(buf):
    d = dm(buf)
    poc = d.dmSize
    return bytes(buf.raw[poc:poc + d.dmDriverExtra])


def opis(buf, oznaka):
    d = dm(buf)
    p = privatni(buf)
    print("%-26s dmSize=%d extra=%d  papir=%d medij=%d kvalitet=%d yres=%d  priv=%s" % (
        oznaka, d.dmSize, d.dmDriverExtra, d.dmPaperSize, d.dmMediaType,
        d.dmPrintQuality, d.dmYResolution, hashlib.sha1(p).hexdigest()[:12]))
    return p


ime = None
for s in win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 2):
    if "L18050" in s["pPrinterName"].upper():
        ime = s["pPrinterName"]
        break
ime = ime or win32print.GetDefaultPrinter()
print("STAMPAC:", ime, "\n")

osnovni, n = uzmi(ime)
p0 = opis(osnovni, "tekuce u drajveru")

razlike = {}
for sifra, naziv in ((1, "Plain paper"), (326, "Epson Matte"),
                     (325, "Premium Glossy"), (318, "Photo Quality Ink Jet"),
                     (352, "Ultra Glossy")):
    buf, _ = uzmi(ime)
    d = dm(buf)
    d.dmPaperSize = 9
    d.dmMediaType = sifra
    d.dmFields |= (DM_PAPERSIZE | DM_MEDIATYPE)
    izl = spoji(ime, buf, n)
    p = opis(izl, "medij %d %s" % (sifra, naziv))
    razlike[sifra] = p

print("\nPOREDJENJE PRIVATNOG BLOKA (u odnosu na Plain paper):")
osnova = razlike[1]
for sifra, p in razlike.items():
    if sifra == 1:
        continue
    bajt = [i for i in range(min(len(osnova), len(p))) if osnova[i] != p[i]]
    print("  medij %-4d razlicitih bajtova: %d  %s" % (
        sifra, len(bajt), ("na pozicijama " + str(bajt[:16])) if bajt else "(IDENTICAN)"))
