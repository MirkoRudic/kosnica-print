#!/usr/bin/env python3
"""
Obrada slike za magnetni ram.

Lanac je uvek isti:
    ucitaj -> ispravi nivoe -> iseci na prozor -> primeni preset -> dodaj napust

Nista u ovom modulu ne zna za stampac ni za Windows. Ulaz je slika,
izlaz je slika spremna za rez, zajedno sa merama u milimetrima.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageOps

Image.MAX_IMAGE_PIXELS = 300_000_000


# ----------------------------------------------------------------------
# mere
# ----------------------------------------------------------------------

@dataclass
class Ram:
    """Sve mere u milimetrima, izmerene na ODSTAMPANOM ramu."""
    naziv: str
    prozor_s: float          # otvor kroz koji se vidi slika
    prozor_v: float
    rez_s: float             # na ovo se isece odstampana slika
    rez_v: float
    napust: float = 3.0      # koliko boje ide preko linije reza
    ostro: float = 1.5       # koliko ogledala uz ivicu ostaje ostro

    @property
    def odnos(self) -> float:
        return self.prozor_s / self.prozor_v

    @property
    def puna_s(self) -> float:
        return self.rez_s + 2 * self.napust

    @property
    def puna_v(self) -> float:
        return self.rez_v + 2 * self.napust

    @property
    def preklop_s(self) -> float:
        return (self.rez_s - self.prozor_s) / 2.0

    @property
    def preklop_v(self) -> float:
        return (self.rez_v - self.prozor_v) / 2.0


@dataclass
class Podesavanja:
    """Sve sto korisnik moze da pomeri."""
    preset: str = "original"
    pomak_x: float = 0.5     # 0 = skroz levo, 1 = skroz desno
    pomak_y: float = 0.5
    zum: float = 1.0         # 1.0 = popunjava prozor tacno; manje = okvir oko slike
    boja_pozadine: str = "#FFFFFF"   # vidi se kad je zum < 1
    rotacija: int = 0        # 0, 90, 180, 270 (u levo)
    ogledalo: bool = False
    crna: float = -1.0       # -1 = automatski iz histograma
    bela: float = -1.0
    zasicenje: float = 1.12
    jasnoca: int = 30        # lokalni kontrast, 0..100
    jacina_preseta: int = 100   # 0 = original, 100 = pun preset
    obrezi_rub: bool = False  # skini beli rub skenera (po potrebi, iz Podesavanja)
    popuna: str = "ogledalo"  # cime se popunjava deo ispod lajsne
    boja_popune: str = "#FFFFFF"
    dpi: int = 350


# ----------------------------------------------------------------------
# osnovne radnje
# ----------------------------------------------------------------------

PDF_DPI = 400


def _iz_pdf(putanja: str, dpi: int = PDF_DPI) -> Image.Image:
    """Prva strana PDF-a kao slika. Trazi PyMuPDF, pa pdf2image."""
    try:
        import pymupdf as fitz                        # PyMuPDF
    except ImportError:
        try:
            import fitz                               # starije izdanje
        except ImportError:
            fitz = None
    if fitz is not None:
        d = fitz.open(putanja)
        try:
            if d.page_count < 1:
                raise ValueError("PDF nema nijednu stranu.")
            s = d.load_page(0)
            m = fitz.Matrix(dpi / 72.0, dpi / 72.0)
            p = s.get_pixmap(matrix=m, alpha=False)
            return Image.frombytes("RGB", (p.width, p.height), p.samples)
        finally:
            d.close()
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError(
            "Za uvoz PDF-a nedostaje PyMuPDF. Instaliraj ga sa: pip install pymupdf")
    sl = convert_from_path(putanja, dpi=dpi, first_page=1, last_page=1)
    if not sl:
        raise ValueError("PDF nema nijednu stranu.")
    return sl[0].convert("RGB")


def _skini_praznu_ivicu(im: Image.Image, prag: int = 247) -> Image.Image:
    """
    Skini potpuno praznu ivicu strane. Namenjeno PDF-u, gde je crtez skoro
    uvek u sredini A4 lista, pa bi inace pola kadra bio prazan papir.
    Dira samo redove i kolone koji su gotovo u celosti beli.
    """
    a = np.asarray(im.convert("L"))
    red = (a < prag).mean(axis=1) > 0.004
    kol = (a < prag).mean(axis=0) > 0.004
    if not red.any() or not kol.any():
        return im
    y0, y1 = int(np.argmax(red)), len(red) - int(np.argmax(red[::-1]))
    x0, x1 = int(np.argmax(kol)), len(kol) - int(np.argmax(kol[::-1]))
    d = max(2, min(im.size) // 200)                  # vrati malo vazduha
    x0, y0 = max(0, x0 - d), max(0, y0 - d)
    x1, y1 = min(im.size[0], x1 + d), min(im.size[1], y1 + d)
    if (x1 - x0) < 32 or (y1 - y0) < 32:
        return im
    return im.crop((x0, y0, x1, y1))


def _pozadina(im: Image.Image) -> Image.Image:
    """Providne delove (PNG, PDF) spusti na belo, da ne postanu crni."""
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        p = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(p, im)
    return im.convert("RGB")


def ucitaj(izvor) -> Image.Image:
    """
    Ucitaj bilo sta sto je slika: jpg, png, tif, bmp, webp, gif, heic, pdf.
    PDF se renderuje sa prve strane; HEIC radi ako je instaliran pillow-heif.
    """
    if isinstance(izvor, Image.Image):
        return _pozadina(izvor)
    if isinstance(izvor, str) and izvor.lower().endswith(".pdf"):
        return _skini_praznu_ivicu(_pozadina(_iz_pdf(izvor)))
    try:
        import pillow_heif                            # noqa: F401
        pillow_heif.register_heif_opener()
    except Exception:
        pass
    try:
        im = Image.open(izvor)
    except Exception:
        # neki skeneri daju PDF bez nastavka; probaj i to pre nego sto odustanes
        if isinstance(izvor, str):
            try:
                return _pozadina(_iz_pdf(izvor))
            except Exception:
                pass
        raise
    im = ImageOps.exif_transpose(im)
    return _pozadina(im)


def citljiv(ime: str) -> bool:
    """Da li ime fajla lici na nesto sto umemo da otvorimo."""
    d = ime.lower().rsplit(".", 1)
    if len(d) < 2:
        return False
    return d[1] in {"jpg", "jpeg", "png", "tif", "tiff", "bmp", "webp", "gif",
                    "heic", "heif", "pdf", "jfif", "ppm", "pgm", "tga", "ico"}


def obrezi_rub(im: Image.Image, prag: float = 0.5) -> Image.Image:
    """
    Skini beli rub skenera. Trazi gde pocinje obojeni ili tamni sadrzaj,
    po redovima i kolonama. Ako nista ne nadje, vraca sliku neizmenjenu.
    """
    a = np.asarray(im).astype(np.float32)
    L = a.mean(axis=2)
    S = a.max(axis=2) - a.min(axis=2)
    m = (S > 18) | (L < 215)

    def opseg(v):
        iznad = v > prag
        if not iznad.any():
            return None
        i = int(np.argmax(iznad))
        j = len(v) - int(np.argmax(iznad[::-1]))
        return i, j

    ox = opseg(m.mean(axis=0))
    oy = opseg(m.mean(axis=1))
    if not ox or not oy:
        return im
    W, H = im.size
    if (ox[1] - ox[0]) < 0.3 * W or (oy[1] - oy[0]) < 0.3 * H:
        return im                      # sumnjiv rezultat, ne diraj
    return im.crop((ox[0], oy[0], ox[1], oy[1]))


def auto_nivoi(im: Image.Image, crn: float = 0.1, beo: float = 99.8):
    """
    Vrati (crna, bela) tacku iz histograma, u 0..255.
    Percentili su namerno blagi: sken crteza ima ogromnu belu povrsinu,
    pa stroziji prag (0.4) podigne crnu tacku na 128 i spali sliku.
    """
    a = np.asarray(im.convert("L"))
    c = float(np.percentile(a, crn))
    b = float(np.percentile(a, beo))
    return min(c, 170.0), max(b, c + 30.0)


def nivoi(im: Image.Image, crna: float, bela: float, zasicenje: float = 1.0):
    if bela - crna < 1:
        bela = crna + 1
    a = np.asarray(im).astype(np.float32)
    a = (a - crna) * (255.0 / (bela - crna))
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if abs(zasicenje - 1.0) > 1e-3:
        out = ImageEnhance.Color(out).enhance(zasicenje)
    return out


def auto_sve(im: Image.Image) -> dict:
    """
    Predlozi sva cetiri broja odjednom, po tome kakva je slika.

    Ideja: crna i bela iz histograma, zasicenje nanize ako je slika vec
    zivih boja a navise ako je bleda, jasnoca vise ako je slika mekana.
    Vraca recnik koji se moze prosuti pravo u Podesavanja.
    """
    c, b = auto_nivoi(im)
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    mx, mn = a.max(axis=2), a.min(axis=2)
    sivo = mx.mean() < 1e-6
    hroma = float((mx - mn).mean())              # 0 = sivo, ~60 = vrlo zivo
    L = np.asarray(im.convert("L")).astype(np.float32)
    raspon = float(b - c)

    if sivo or hroma < 4:
        zas = 1.0
    else:
        zas = 1.30 - (hroma / 110.0)             # blede slike dobiju vise
        zas = round(min(1.35, max(0.95, zas)), 2)

    # mekoca: koliko se slika promeni kad se malo zamuti
    mala = Image.fromarray(L.astype(np.uint8))
    if max(mala.size) > 900:
        mala = mala.resize((mala.size[0] // 2, mala.size[1] // 2))
    m = np.asarray(mala).astype(np.float32)
    ostrina = float(np.abs(m[1:, :] - m[:-1, :]).mean())
    jas = int(min(70, max(12, round(62 - ostrina * 3.2))))

    if raspon > 200:                              # vec rastegnuta slika
        jas = max(10, jas - 10)

    return {"crna": round(c, 1), "bela": round(b, 1),
            "zasicenje": zas, "jasnoca": jas}


def jasnoca(im: Image.Image, kolicina: int):
    """Lokalni kontrast velikog poluprecnika. Razdvaja slojeve na ravnom svetlu."""
    if kolicina <= 0:
        return im
    r = max(6, im.size[0] // 45)
    return im.filter(ImageFilter.UnsharpMask(radius=r, percent=int(kolicina), threshold=3))


def _rastegni_sivu(g: np.ndarray, crn=0.8, beo=99.3) -> np.ndarray:
    lo, hi = np.percentile(g, crn), np.percentile(g, beo)
    return np.clip((g - lo) * (255.0 / max(hi - lo, 1.0)), 0, 255)


# ----------------------------------------------------------------------
# preseti
# ----------------------------------------------------------------------

def _siva(im: Image.Image) -> Image.Image:
    g = np.asarray(jasnoca(im, 70).convert("L")).astype(np.float32)
    return Image.fromarray(_rastegni_sivu(g).astype(np.uint8))


def _toniraj(im: Image.Image, tamna, svetla) -> Image.Image:
    g = np.asarray(_siva(im)).astype(np.float32) / 255.0
    t = np.array(tamna, dtype=np.float32)
    s = np.array(svetla, dtype=np.float32)
    o = t[None, None, :] + (s - t)[None, None, :] * g[:, :, None]
    return Image.fromarray(np.clip(o, 0, 255).astype(np.uint8))


def _plakat(im: Image.Image) -> Image.Image:
    m = jasnoca(im, 40).filter(ImageFilter.GaussianBlur(1.8))
    m = ImageEnhance.Color(m).enhance(1.7)
    return ImageOps.posterize(m, 3)


def _raster(im: Image.Image, cel: int = 6) -> Image.Image:
    """Klasican raster pod 45 stepeni."""
    g = np.asarray(_siva(im)).astype(np.float32) / 255.0
    H, W = g.shape
    S = 3
    out = Image.new("L", (W * S, H * S), 255)
    d = ImageDraw.Draw(out)
    ug = math.radians(45.0)
    ca, sa = math.cos(ug), math.sin(ug)
    dij = int((W + H) / cel) + 2
    for i in range(-dij, dij):
        for j in range(-dij, dij):
            x = (i * cel) * ca - (j * cel) * sa + W / 2
            y = (i * cel) * sa + (j * cel) * ca + H / 2
            if not (0 <= x < W and 0 <= y < H):
                continue
            x0, x1 = int(max(0, x - cel / 2)), int(min(W, x + cel / 2))
            y0, y1 = int(max(0, y - cel / 2)), int(min(H, y + cel / 2))
            if x1 <= x0 or y1 <= y0:
                continue
            tam = 1.0 - float(g[y0:y1, x0:x1].mean())
            r = (cel * 0.92) * (max(tam, 0.0) ** 0.60) / 2.0
            if r < 0.2:
                continue
            d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=0)
    return out.resize((W, H), Image.LANCZOS).convert("RGB")


PRESETI = {
    "original":  ("Original",        lambda im: jasnoca(im, 30)),
    "cb":        ("Crno-belo",       lambda im: _siva(im).convert("RGB")),
    "sepija":    ("Sepija",          lambda im: _toniraj(im, (42, 28, 16), (250, 239, 214))),
    "duotone":   ("Duotone šumski",  lambda im: _toniraj(im, (24, 52, 45), (242, 227, 192))),
    "plakat":    ("Plakat",          _plakat),
    "raster":    ("Raster",          _raster),
}


# ----------------------------------------------------------------------
# kadriranje
# ----------------------------------------------------------------------

def primeni_preset(im: Image.Image, p: Podesavanja) -> Image.Image:
    """
    Preset sa jacinom: 0 vraca original, 100 pun efekat, izmedju se mesa.
    Mesanje je linearno po pikselu - tako "pola sepije" izgleda kao pola
    puta izmedju, a ne kao neki treci efekat.
    """
    if p.preset == "original":
        return jasnoca(im, p.jasnoca) if p.jasnoca != 30 else im
    fn = PRESETI.get(p.preset, PRESETI["original"])[1]
    obradjena = fn(im)
    j = max(0, min(100, int(p.jacina_preseta)))
    if j >= 100:
        return obradjena
    if j <= 0:
        return im
    if obradjena.size != im.size:
        obradjena = obradjena.resize(im.size, Image.LANCZOS)
    return Image.blend(im.convert("RGB"), obradjena.convert("RGB"), j / 100.0)


def okreni(im: Image.Image, p: Podesavanja) -> Image.Image:
    if p.rotacija:
        im = im.rotate(-p.rotacija, expand=True)
    if p.ogledalo:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


def smesti(im: Image.Image, w: int, h: int, p: Podesavanja) -> Image.Image:
    """
    Smesti sliku u prozor od w x h piksela.

    zum = 1.00 znaci da slika tacno pokriva prozor (visak se isece).
    zum < 1 znaci da je slika manja od prozora, pa se oko nje vidi pozadina
    - tu je mesto za beo ili obojen okvir oko fotografije.
    pomak_x/pomak_y (0..1) sece kad je slika veca, a pomera kad je manja.

    Isto racuna i pregledac u editoru, pa se ono sto vidis i ono sto izadje
    iz stampaca ne razilaze.
    """
    W, H = im.size
    pokrij = max(w / W, h / H)
    s = pokrij * max(0.05, float(p.zum))
    nw, nh = max(1, int(round(W * s))), max(1, int(round(H * s)))
    mala = im.resize((nw, nh), Image.LANCZOS)

    try:
        poz = ImageColor.getrgb(p.boja_pozadine)
    except Exception:
        poz = (255, 255, 255)
    out = Image.new("RGB", (w, h), poz)
    x = int(round((w - nw) * min(max(p.pomak_x, 0.0), 1.0)))
    y = int(round((h - nh) * min(max(p.pomak_y, 0.0), 1.0)))
    out.paste(mala, (x, y))
    return out


POPUNE = {
    "ogledalo":  "Ogledalo ivice",
    "razvucena": "Razvučena ivica",
    "zamucena":  "Zamućeno ogledalo",
    "boja":      "Boja",
}


def _ogledalo(jezgro, pad, pad_y):
    W, H = jezgro.size
    out = Image.new("RGB", (W + 2 * pad, H + 2 * pad_y))
    out.paste(jezgro, (pad, pad_y))
    out.paste(jezgro.crop((0, 0, pad, H)).transpose(Image.FLIP_LEFT_RIGHT), (0, pad_y))
    out.paste(jezgro.crop((W - pad, 0, W, H)).transpose(Image.FLIP_LEFT_RIGHT), (W + pad, pad_y))
    gore = out.crop((0, pad_y, W + 2 * pad, 2 * pad_y)).transpose(Image.FLIP_TOP_BOTTOM)
    dole = out.crop((0, H, W + 2 * pad, H + pad_y)).transpose(Image.FLIP_TOP_BOTTOM)
    out.paste(gore, (0, 0))
    out.paste(dole, (0, H + pad_y))
    return out


def _razvuci(jezgro, pad, pad_y):
    """Ivicni piksel se produzi napolje. Boja se nastavlja, motiv se ne ponavlja."""
    a = np.asarray(jezgro)
    a = np.pad(a, ((pad_y, pad_y), (pad, pad), (0, 0)), mode="edge")
    return Image.fromarray(a)


def _prosek_ivice(jezgro, debljina_px):
    a = np.asarray(jezgro).astype(np.float32)
    d = max(1, min(debljina_px, min(a.shape[0], a.shape[1]) // 2))
    rub = np.concatenate([a[:d].reshape(-1, 3), a[-d:].reshape(-1, 3),
                          a[:, :d].reshape(-1, 3), a[:, -d:].reshape(-1, 3)])
    return tuple(int(round(v)) for v in rub.mean(axis=0))


def napust(jezgro: Image.Image, ram: Ram, dpi: int,
           popuna: str = "ogledalo", boja: str = "#FFFFFF") -> Image.Image:
    """
    Prosiri sliku preko linije reza, da se pod lajsnom i oko nje ne vidi
    beo papir ako se papiric pomeri u prorezu ili se isece malo ukoso.

    `popuna`:
      ogledalo  - preslikana ivica; prvih `ram.ostro` mm ostaje ostro da se
                  nastavak ne primeti, dalje se zamucuje
      razvucena - ivicni piksel se produzi napolje, pa blago zamuti
      zamucena  - preslikana ivica, zamucena sve do same ivice slike
      boja      - jedna boja, iz palete
    """
    px = lambda mm: int(round(mm * dpi / 25.4))
    pad = max(1, px(ram.preklop_s + ram.napust))
    pad_y = max(1, px(ram.preklop_v + ram.napust))
    W, H = jezgro.size
    ostro = max(1, px(ram.ostro))

    if popuna == "boja":
        try:
            c = ImageColor.getrgb(boja)
        except Exception:
            c = _prosek_ivice(jezgro, ostro)
        out = Image.new("RGB", (W + 2 * pad, H + 2 * pad_y), c)
        out.paste(jezgro, (pad, pad_y))
        return out

    if popuna == "razvucena":
        out = _razvuci(jezgro, pad, pad_y)
        mut = out.filter(ImageFilter.GaussianBlur(max(pad, pad_y) * 0.22))
    elif popuna == "zamucena":
        out = _ogledalo(jezgro, pad, pad_y)
        mut = out.filter(ImageFilter.GaussianBlur(max(pad, pad_y) * 0.45))
        ostro = max(1, ostro // 3)          # skoro nimalo ostrog pojasa
    else:                                    # ogledalo
        out = _ogledalo(jezgro, pad, pad_y)
        mut = out.filter(ImageFilter.GaussianBlur(max(pad, pad_y) * 0.30))

    maska = Image.new("L", out.size, 255)
    ImageDraw.Draw(maska).rectangle(
        [pad - ostro, pad_y - ostro, pad + W - 1 + ostro, pad_y + H - 1 + ostro], fill=0)
    maska = maska.filter(ImageFilter.GaussianBlur(ostro * 0.9))
    out = Image.composite(mut, out, maska)
    out.paste(jezgro, (pad, pad_y))
    return out


# ----------------------------------------------------------------------
# ceo lanac
# ----------------------------------------------------------------------

def pripremi(izvor, ram: Ram, p: Podesavanja):
    """
    Vrati (slika_sa_napustom, podaci). Slika je u punoj meri `ram.puna_s` x `ram.puna_v`
    na `p.dpi`, i spremna je za slaganje na tabak.
    """
    im = ucitaj(izvor) if not isinstance(izvor, Image.Image) else izvor
    if p.obrezi_rub:
        im = obrezi_rub(im)
    izvorne = im.size

    crna, bela = (p.crna, p.bela)
    if crna < 0 or bela < 0:
        crna, bela = auto_nivoi(im)
    im = nivoi(im, crna, bela, p.zasicenje)

    im = primeni_preset(im, p)
    im = okreni(im, p)
    ime = PRESETI.get(p.preset, PRESETI["original"])[0]

    px = lambda mm: int(round(mm * p.dpi / 25.4))
    jezgro = smesti(im, px(ram.prozor_s), px(ram.prozor_v), p)
    odseceno = max(0.0, 1.0 - 1.0 / max(1e-6, float(p.zum)) ** 2)
    puna = napust(jezgro, ram, p.dpi, p.popuna, p.boja_popune)

    return puna, {
        "preset": ime,
        "popuna": POPUNE.get(p.popuna, p.popuna),
        "izvor_px": izvorne,
        "kadar_px": jezgro.size,
        "zum": round(float(p.zum), 3),
        "odseceno_udeo": round(odseceno, 4),
        "crna": round(crna, 1),
        "bela": round(bela, 1),
        "puna_mm": (ram.puna_s, ram.puna_v),
        "rez_mm": (ram.rez_s, ram.rez_v),
        "prozor_mm": (ram.prozor_s, ram.prozor_v),
        "dpi_stvarni": round(puna.size[0] / (ram.puna_s / 25.4), 1),
    }


def pregled(izvor, ram: Ram, p: Podesavanja, sirina_px: int = 900):
    """Brzi pregled za interfejs: ista obrada, manja rezolucija."""
    mali = Podesavanja(**{**p.__dict__})
    mali.dpi = max(80, int(sirina_px / (ram.puna_s / 25.4)))
    return pripremi(izvor, ram, mali)


def u_png(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, format="PNG")
    return b.getvalue()
