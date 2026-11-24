#!/usr/bin/env python3
"""
Direktna stampa na Windows stampac, bez pregledaca i bez dijaloga.

Zasto ovako: svaki pregledac i svaki PDF citac ima svoje skaliranje, i dovoljno
je da se jedan od njih ne slozi sa drajverom pa da mera pobegne. Ovde se crta
pravo na stampacki DC u fizickim milimetrima, pa izmedju slike i papira nema
nikoga ko bi je promenio.

Tip papira i ulaz se postavljaju iz aplikacije: sifre se citaju iz drajvera
(DeviceCapabilities), upisu u javni deo DEVMODE-a i proteraju kroz
DocumentProperties, koji ih prevede u Epsonov privatni blok. Provereno na
L18050: privatni blok se stvarno menja, pa sa papirom dolazi i kvalitet koji
Epson za taj papir vezuje. Kvalitet se posebno ne moze nametnuti - drajver
javno polje uvek vrati na 720.
Sistemska podesavanja se ne diraju; izmene zive samo u tekucem poslu.
"""
from __future__ import annotations

import json
import os
import struct

import win32con
import win32gui
import win32print
import win32ui
from PIL import Image, ImageWin

OVDE = os.path.dirname(os.path.abspath(__file__))
MAPA = os.path.join(OVDE, "podaci")
DEVMODE_FAJL = os.path.join(MAPA, "devmode.bin")

DMPAPER_A4 = 9


# ----------------------------------------------------------------- stampaci

def lista_stampaca() -> list[dict]:
    z = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    out = []
    for p in win32print.EnumPrinters(z, None, 2):
        out.append({"ime": p["pPrinterName"], "drajver": p.get("pDriverName"),
                    "port": p.get("pPortName")})
    return out


def podrazumevani() -> str:
    return win32print.GetDefaultPrinter()


# ------------------------------------------------- sta drajver nudi

DC_BINS = 6
DC_BINNAMES = 12
DC_MEDIATYPENAMES = 34
DC_MEDIATYPES = 35


def _port(ime: str) -> str:
    h = _otvori(ime)
    try:
        return win32print.GetPrinter(h, 2)["pPortName"]
    finally:
        win32print.ClosePrinter(h)


def _spisak(ime, port, sta_imena, sta_sifre) -> list[dict]:
    try:
        imena = win32print.DeviceCapabilities(ime, port, sta_imena)
        sifre = win32print.DeviceCapabilities(ime, port, sta_sifre)
    except Exception:
        return []
    if not isinstance(imena, (list, tuple)) or not isinstance(sifre, (list, tuple)):
        return []
    return [{"sifra": int(s), "ime": str(n)} for n, s in zip(imena, sifre)]


def tipovi_papira(ime: str) -> list[dict]:
    """Tipovi papira koje drajver nudi, sa Epsonovim siframa."""
    return _spisak(ime, _port(ime), DC_MEDIATYPENAMES, DC_MEDIATYPES)


def izvori_papira(ime: str) -> list[dict]:
    """Ulazi za papir (zadnji ulaz, bez ivica, ladica za diskove...)."""
    return _spisak(ime, _port(ime), DC_BINNAMES, DC_BINS)


def mogucnosti(ime: str | None = None) -> dict:
    ime = ime or podrazumevani()
    return {"stampac": ime, "papiri": tipovi_papira(ime), "izvori": izvori_papira(ime)}


# ----------------------------------------------------------------- devmode

def _otvori(ime: str):
    try:
        return win32print.OpenPrinter(ime, {"DesiredAccess": win32print.PRINTER_ACCESS_USE})
    except Exception:
        return win32print.OpenPrinter(ime)


_POLJA = ("PaperSize", "PaperWidth", "PaperLength", "Orientation",
          "PrintQuality", "YResolution", "MediaType", "Color", "Copies", "Scale")


DM_MEDIATYPE = 0x08000000
DM_DEFAULTSOURCE = 0x00000200


def _devmode_za(ime: str, medij=None, ulaz=None):
    """
    Uzmi TEKUCA podesavanja drajvera i nametni ono sto mora: A4, uspravno,
    bez skaliranja, jedna kopija - pa jos tip papira i ulaz ako su trazeni.

    Blok koji drajver vrati nosi i Epsonov privatni deo. Kad mu se preko
    DocumentProperties preda nova sifra papira, drajver taj privatni deo sam
    prepravi, pa uz papir ide i kvalitet koji Epson za njega vezuje.
    Sistemska podesavanja se NE menjaju; izmena zivi samo u ovom poslu.
    """
    h = _otvori(ime)
    try:
        dm = win32print.GetPrinter(h, 2)["pDevMode"]
        pre = {k: getattr(dm, k, None) for k in _POLJA}
        dm.PaperSize = DMPAPER_A4
        dm.Orientation = win32con.DMORIENT_PORTRAIT
        dm.Scale = 100
        dm.Copies = 1
        polja = (win32con.DM_PAPERSIZE | win32con.DM_ORIENTATION
                 | win32con.DM_SCALE | win32con.DM_COPIES)
        if medij:
            dm.MediaType = int(medij)
            polja |= DM_MEDIATYPE
        if ulaz:
            dm.DefaultSource = int(ulaz)
            polja |= DM_DEFAULTSOURCE
        dm.Fields |= polja
        win32print.DocumentProperties(0, h, ime, dm, dm,
                                      win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER)
        posle = {k: getattr(dm, k, None) for k in _POLJA}
        opis = {"izvor": "tekuca podesavanja drajvera, A4 nametnut",
                "trazeno": {"medij": medij, "ulaz": ulaz},
                "pre": pre, "posle": posle}
        if medij and posle.get("MediaType") != int(medij):
            opis["upozorenje"] = ("drajver nije prihvatio tip papira %s, ostao je %s"
                                  % (medij, posle.get("MediaType")))
        return dm, opis
    finally:
        win32print.ClosePrinter(h)


def procitaj_podesavanja(ime: str, medij=None, ulaz=None) -> dict:
    """Sta drajver trenutno nudi - za prikaz u aplikaciji."""
    os.makedirs(MAPA, exist_ok=True)
    _, opis = _devmode_za(ime, medij, ulaz)
    opis["stampac"] = ime
    opis["papiri"] = tipovi_papira(ime)
    opis["ulazi"] = izvori_papira(ime)
    with open(os.path.join(MAPA, "stampac.json"), "w", encoding="utf-8") as f:
        json.dump(opis, f, ensure_ascii=False, indent=2)
    return opis


# ----------------------------------------------------------------- crtanje

class List:
    """Stampacki DC na kom se crta u milimetrima od ivice papira."""

    def __init__(self, ime: str, medij=None, ulaz=None):
        self.ime = ime
        dm, self.izvor_dm = _devmode_za(ime, medij, ulaz)
        hdc = win32gui.CreateDC("WINSPOOL", ime, dm)
        self.dc = win32ui.CreateDCFromHandle(hdc)
        g = self.dc.GetDeviceCaps
        self.dpi_x, self.dpi_y = g(win32con.LOGPIXELSX), g(win32con.LOGPIXELSY)
        self.odmak_x, self.odmak_y = g(win32con.PHYSICALOFFSETX), g(win32con.PHYSICALOFFSETY)
        self.fiz_w, self.fiz_h = g(win32con.PHYSICALWIDTH), g(win32con.PHYSICALHEIGHT)
        self.pisi_w, self.pisi_h = g(win32con.HORZRES), g(win32con.VERTRES)

    def mere(self) -> dict:
        return {"stampac": self.ime, "devmode": self.izvor_dm,
                "dpi": [self.dpi_x, self.dpi_y],
                "papir_mm": [round(self.fiz_w / self.dpi_x * 25.4, 2),
                             round(self.fiz_h / self.dpi_y * 25.4, 2)],
                "stampajuce_mm": [round(self.pisi_w / self.dpi_x * 25.4, 2),
                                  round(self.pisi_h / self.dpi_y * 25.4, 2)],
                "neispisiva_ivica_mm": [round(self.odmak_x / self.dpi_x * 25.4, 2),
                                        round(self.odmak_y / self.dpi_y * 25.4, 2)]}

    # mm od ivice papira -> piksel na DC-u (DC pocinje od stampajuce povrsine)
    def px(self, x_mm, y_mm):
        return (int(round(x_mm / 25.4 * self.dpi_x)) - self.odmak_x,
                int(round(y_mm / 25.4 * self.dpi_y)) - self.odmak_y)

    def pocni(self, naslov="Priprema magneta"):
        self.dc.StartDoc(naslov)

    def nova_strana(self):
        self.dc.StartPage()

    def kraj_strane(self):
        self.dc.EndPage()

    def zavrsi(self):
        self.dc.EndDoc()
        self.dc.DeleteDC()

    def slika(self, im: Image.Image, x_mm, y_mm, w_mm, h_mm):
        x0, y0 = self.px(x_mm, y_mm)
        x1, y1 = self.px(x_mm + w_mm, y_mm + h_mm)
        ImageWin.Dib(im.convert("RGB")).draw(self.dc.GetHandleOutput(), (x0, y0, x1, y1))

    def linija(self, x0_mm, y0_mm, x1_mm, y1_mm, debljina_mm=0.09):
        d = max(1, int(round(debljina_mm / 25.4 * self.dpi_x)))
        pero = win32ui.CreatePen(win32con.PS_SOLID, d, 0)
        staro = self.dc.SelectObject(pero)
        self.dc.MoveTo(self.px(x0_mm, y0_mm))
        self.dc.LineTo(self.px(x1_mm, y1_mm))
        self.dc.SelectObject(staro)


# ----------------------------------------------------------------- tabak

def _marke(l: List, tx0, ty0, tx1, ty1, duz=4.0, zazor=1.0):
    for x in (tx0, tx1):
        l.linija(x, ty0 - zazor, x, ty0 - zazor - duz)
        l.linija(x, ty1 + zazor, x, ty1 + zazor + duz)
    for y in (ty0, ty1):
        l.linija(tx0 - zazor, y, tx0 - zazor - duz, y)
        l.linija(tx1 + zazor, y, tx1 + zazor + duz, y)


def _lenjir(l: List, t, y_mm, faktor):
    L = t.get("lenjir_duzina", 150.0) * faktor
    x0 = (t["sirina"] - L) / 2.0
    l.linija(x0, y_mm, x0 + L, y_mm, 0.15)
    n = int(round(t.get("lenjir_duzina", 150.0) / 10.0))
    korak = L / n
    for i in range(n + 1):
        x = x0 + i * korak
        l.linija(x, y_mm, x, y_mm - (4.0 if i % 5 == 0 else 2.5), 0.12)


def odstampaj_tabake(slike, ram, t, raspored, faktor, stampac=None,
                     lenjir=True, probno=False, medij=None, ulaz=None) -> dict:
    """
    `slike` - PIL slike sa napustom, vec pripremljene.
    `raspored` - rezultat tabak.raspored().
    `medij`/`ulaz` - Epsonove sifre tipa papira i ulaza, ili None za ono sto
    je vec podeseno u drajveru.
    `probno=True` racuna i vraca geometriju, ali ne salje nista na stampac.
    """
    import math
    ime = stampac or podrazumevani()
    l = List(ime, medij, ulaz)
    izvestaj = l.mere()

    k, r, uspravno = raspored["kolona"], raspored["redova"], raspored["uspravno"]
    pw, ph = raspored["pw"], raspored["ph"]
    rez_w, rez_h = ram.rez_s * faktor, ram.rez_v * faktor
    if uspravno:
        rez_w, rez_h = rez_h, rez_w

    po_tabaku = max(1, k * r)
    tabaka = max(1, math.ceil(len(slike) / po_tabaku))
    uk_w = k * pw + (k - 1) * t["razmak"]
    x0 = (t["sirina"] - uk_w) / 2.0
    y_vrh = t["ivica"]

    izvestaj.update({"tabaka": tabaka, "po_tabaku": po_tabaku,
                     "rez_mm": [round(rez_w, 2), round(rez_h, 2)],
                     "prvi_isecak_mm": None, "probno": probno})

    # provera da li sve staje u stampajucu povrsinu
    pw_lim = l.pisi_w / l.dpi_x * 25.4
    ph_lim = l.pisi_h / l.dpi_y * 25.4
    lev = l.odmak_x / l.dpi_x * 25.4
    gor = l.odmak_y / l.dpi_y * 25.4
    izvestaj["upozorenja"] = []
    if x0 < lev:
        izvestaj["upozorenja"].append(
            "leva ivica %.2f mm je unutar neispisivog ruba %.2f mm" % (x0, lev))
    dno = y_vrh + r * ph + (r - 1) * t["razmak"] + (22.0 if lenjir else 0.0)
    if dno > gor + ph_lim:
        izvestaj["upozorenja"].append(
            "sadrzaj ide do %.1f mm, a stampajuce je do %.1f mm" % (dno, gor + ph_lim))

    if probno:
        for idx in range(min(1, len(slike))):
            red, kol = divmod(idx, k)
            bx = x0 + kol * (pw + t["razmak"])
            by = y_vrh + red * (ph + t["razmak"])
            izvestaj["prvi_isecak_mm"] = [round(bx, 2), round(by, 2),
                                          round(pw, 2), round(ph, 2)]
        l.dc.DeleteDC()
        return izvestaj

    l.pocni()
    for n in range(tabaka):
        deo = slike[n * po_tabaku:(n + 1) * po_tabaku]
        l.nova_strana()
        for idx, sl in enumerate(deo):
            red, kol = divmod(idx, k)
            s = sl.rotate(90, expand=True) if uspravno else sl
            bx = x0 + kol * (pw + t["razmak"])
            by = y_vrh + red * (ph + t["razmak"])
            l.slika(s, bx, by, pw, ph)
            tx0 = bx + (pw - rez_w) / 2.0
            ty0 = by + (ph - rez_h) / 2.0
            _marke(l, tx0, ty0, tx0 + rez_w, ty0 + rez_h)
        if lenjir:
            _lenjir(l, t, t["visina"] - t["ivica"] - 6.0, faktor)
        l.kraj_strane()
    l.zavrsi()
    return izvestaj


# ----------------------------------------------------------------- za server

def odstampaj_kontrolni(ram, t, faktor=1.0, stampac=None, probno=False,
                        medij=None, ulaz=None) -> dict:
    """
    Jedan list: lenjir od 150 mm i prazan okvir reza sa markama.
    Trosi gotovo nimalo mastila, a daje sve sto treba za kalibraciju.
    """
    ime = stampac or podrazumevani()
    l = List(ime, medij, ulaz)
    izv = l.mere()
    rez_w, rez_h = ram.rez_s * faktor, ram.rez_v * faktor
    tx0 = (t["sirina"] - rez_w) / 2.0
    ty0 = 60.0
    y_lenjir = 150.0
    izv.update({"okvir_mm": [round(tx0, 2), round(ty0, 2),
                             round(rez_w, 2), round(rez_h, 2)],
                "lenjir_mm": round(t.get("lenjir_duzina", 150.0) * faktor, 2),
                "probno": probno})
    if probno:
        l.dc.DeleteDC()
        return izv

    l.pocni("Kalibracija - priprema magneta")
    l.nova_strana()
    # okvir reza
    l.linija(tx0, ty0, tx0 + rez_w, ty0)
    l.linija(tx0, ty0 + rez_h, tx0 + rez_w, ty0 + rez_h)
    l.linija(tx0, ty0, tx0, ty0 + rez_h)
    l.linija(tx0 + rez_w, ty0, tx0 + rez_w, ty0 + rez_h)
    _marke(l, tx0, ty0, tx0 + rez_w, ty0 + rez_h)
    # lenjir
    _lenjir(l, t, y_lenjir, faktor)
    try:
        import win32ui as _w
        visina = int(round(3.2 / 25.4 * l.dpi_y))
        font = _w.CreateFont({"name": "Arial", "height": -visina, "weight": 700})
        staro = l.dc.SelectObject(font)
        l.dc.SetTextColor(0)
        l.dc.TextOut(*l.px(t["sirina"] / 2 - 42.0, y_lenjir + 6.0),
                     "IZMERI SUBLEROM: mora biti %.1f mm"
                     % t.get("lenjir_duzina", 150.0))
        l.dc.TextOut(*l.px(tx0, ty0 - 10.0),
                     "okvir reza: %.2f x %.2f mm" % (ram.rez_s, ram.rez_v))
        l.dc.SelectObject(staro)
    except Exception as e:
        izv["tekst"] = "nije ispisan: %s" % e
    l.kraj_strane()
    l.zavrsi()
    return izv
