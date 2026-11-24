#!/usr/bin/env python3
"""
Slaganje na tabak i izvoz PDF-a.

Kalibracioni faktor se primenjuje OVDE, pri renderovanju, a ne u dijalogu
za stampu. Ako stampac stampa 0.7% preveliko, mi crtamo 0.7% manje i izlaz
je tacan, bez obzira kroz sta je prosao.
"""
from __future__ import annotations

import io
import math
import os

from PIL import Image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from obrada import Ram


def koliko_stane(ram: Ram, t: dict, faktor: float = 1.0) -> tuple[int, int, bool]:
    """Vrati (kolona, redova, uspravno) za najbolji raspored na tabaku."""
    uw = t["sirina"] - 2 * t["ivica"]
    uh = t["visina"] - 2 * t["ivica"]
    best = (0, 0, False)
    for uspravno in (False, True):
        w = (ram.puna_v if uspravno else ram.puna_s) * faktor
        h = (ram.puna_s if uspravno else ram.puna_v) * faktor
        k = int((uw + t["razmak"]) // (w + t["razmak"]))
        r = int((uh + t["razmak"]) // (h + t["razmak"]))
        if k * r > best[0] * best[1]:
            best = (k, r, uspravno)
    return best


def raspored(ram: Ram, t: dict, faktor: float = 1.0, lenjir: bool | None = None) -> dict:
    """Stvaran raspored na tabaku, sa oduzetim prostorom za lenjir."""
    if lenjir is None:
        lenjir = t.get("lenjir", True)
    k, r, uspravno = koliko_stane(ram, t, faktor)
    pw = (ram.puna_v if uspravno else ram.puna_s) * faktor
    ph = (ram.puna_s if uspravno else ram.puna_v) * faktor
    prostor_v = t["visina"] - 2 * t["ivica"] - (22.0 if lenjir else 0.0)
    r = max(0, min(r, int((prostor_v + t["razmak"]) // (ph + t["razmak"]))))
    return {"kolona": k, "redova": r, "uspravno": uspravno, "po_tabaku": k * r,
            "pw": pw, "ph": ph}


def _marke(c, tx0, ty0, tx1, ty1, duz=4.0, zazor=1.0):
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.25)
    for x in (tx0, tx1):
        c.line(x * mm, (ty0 - zazor) * mm, x * mm, (ty0 - zazor - duz) * mm)
        c.line(x * mm, (ty1 + zazor) * mm, x * mm, (ty1 + zazor + duz) * mm)
    for y in (ty0, ty1):
        c.line((tx0 - zazor) * mm, y * mm, (tx0 - zazor - duz) * mm, y * mm)
        c.line((tx1 + zazor) * mm, y * mm, (tx1 + zazor + duz) * mm, y * mm)


def _lenjir(c, t, y_mm, faktor):
    L = t.get("lenjir_duzina", 150.0) * faktor
    x0 = (t["sirina"] - L) / 2.0
    c.setLineWidth(0.4)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(x0 * mm, y_mm * mm, (x0 + L) * mm, y_mm * mm)
    korak = L / (t.get("lenjir_duzina", 150.0) / 10.0)   # na svakih 10 nominalnih mm
    n = int(round(t.get("lenjir_duzina", 150.0) / 10.0))
    c.setFont("Helvetica", 6)
    for i in range(n + 1):
        x = x0 + i * korak
        h = 4.0 if i % 5 == 0 else 2.5
        c.line(x * mm, y_mm * mm, x * mm, (y_mm + h) * mm)
        if i % 5 == 0:
            c.drawCentredString(x * mm, (y_mm + 5.2) * mm, str(i * 10))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString((t["sirina"] / 2) * mm, (y_mm - 6) * mm,
                        "IZMERI SUBLEROM: mora biti %.1f mm" % t.get("lenjir_duzina", 150.0))


def slozi_pdf(slike, ram: Ram, t: dict, putanja: str, faktor: float = 1.0,
              lenjir: bool | None = None) -> dict:
    """
    `slike` je lista PIL slika vec pripremljenih sa napustom (puna_s x puna_v).
    Vraca podatke o rasporedu.
    """
    if lenjir is None:
        lenjir = t.get("lenjir", True)

    R = raspored(ram, t, faktor, lenjir)
    k, r, uspravno = R["kolona"], R["redova"], R["uspravno"]
    if k < 1 or r < 1:
        raise ValueError("Slika je veca od tabaka.")

    pw, ph = R["pw"], R["ph"]
    rez_w = ram.rez_s * faktor
    rez_h = ram.rez_v * faktor
    if uspravno:
        rez_w, rez_h = rez_h, rez_w

    po_tabaku = R["po_tabaku"]
    tabaka = max(1, math.ceil(len(slike) / po_tabaku))

    c = canvas.Canvas(putanja, pagesize=(t["sirina"] * mm, t["visina"] * mm))
    uk_w = k * pw + (k - 1) * t["razmak"]
    uk_h = r * ph + (r - 1) * t["razmak"]
    x0 = (t["sirina"] - uk_w) / 2.0
    y_vrh = t["visina"] - t["ivica"]

    for n in range(tabaka):
        deo = slike[n * po_tabaku:(n + 1) * po_tabaku]
        for idx, sl in enumerate(deo):
            red, kol = divmod(idx, k)
            s = sl.rotate(90, expand=True) if uspravno else sl
            bx = x0 + kol * (pw + t["razmak"])
            by = y_vrh - (red + 1) * ph - red * t["razmak"]
            c.drawImage(ImageReader(s), bx * mm, by * mm, pw * mm, ph * mm)
            tx0 = bx + (pw - rez_w) / 2.0
            ty0 = by + (ph - rez_h) / 2.0
            _marke(c, tx0, ty0, tx0 + rez_w, ty0 + rez_h)
        if lenjir:
            _lenjir(c, t, t["ivica"] + 10.0, faktor)
        c.showPage()
    c.save()

    return {"po_tabaku": po_tabaku, "kolona": k, "redova": r, "uspravno": uspravno,
            "tabaka": tabaka, "faktor": faktor,
            "rez_mm": (round(rez_w, 2), round(rez_h, 2)),
            "puna_mm": (round(pw, 2), round(ph, 2)),
            "putanja": os.path.abspath(putanja)}


def kontrolni_list(ram: Ram, t: dict, putanja: str, faktor: float = 1.0) -> str:
    """Samo lenjir i prazan okvir reza - za prvu kalibraciju, bez trosenja mastila."""
    c = canvas.Canvas(putanja, pagesize=(t["sirina"] * mm, t["visina"] * mm))
    _lenjir(c, t, t["visina"] / 2.0, faktor)
    rez_w, rez_h = ram.rez_s * faktor, ram.rez_v * faktor
    tx0 = (t["sirina"] - rez_w) / 2.0
    ty0 = t["visina"] / 2.0 + 40.0
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.25)
    c.rect(tx0 * mm, ty0 * mm, rez_w * mm, rez_h * mm)
    _marke(c, tx0, ty0, tx0 + rez_w, ty0 + rez_h)
    c.setFont("Helvetica", 8)
    c.drawCentredString((t["sirina"] / 2) * mm, (ty0 - 8) * mm,
                        "okvir reza: %.2f x %.2f mm" % (ram.rez_s, ram.rez_v))
    c.save()
    return os.path.abspath(putanja)
