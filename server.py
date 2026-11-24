#!/usr/bin/env python3
"""
Lokalni server za pripremu magneta.

Pregledac samo crta interfejs. Obrada i izvoz rade u ovom procesu,
pa izmedju slike i stampaca nema nikoga ko bi je skalirao.

Pokretanje:   python server.py
Zatim otvori: http://127.0.0.1:8733
"""
from __future__ import annotations

import io
import json
import math
import os
import socket
import sys
import threading
import time
import uuid

from flask import (Flask, jsonify, request, send_file, send_from_directory)
from PIL import Image, ImageDraw

import biblioteka
import dnevnik
import profili
import tabak
import prozor
import version

OVDE_APP = os.path.dirname(os.path.abspath(__file__))
from obrada import (POPUNE, PRESETI, Podesavanja, auto_nivoi, auto_sve, napust,
                    nivoi, obrezi_rub, okreni, primeni_preset, pripremi, smesti,
                    u_png, ucitaj)

OVDE = os.path.dirname(os.path.abspath(__file__))
RADNA = os.path.join(OVDE, "podaci", "slike")
IZLAZ = os.path.join(OVDE, "izlaz")
os.makedirs(RADNA, exist_ok=True)
os.makedirs(IZLAZ, exist_ok=True)

app = Flask(__name__, static_folder=None)
SLIKE: dict[str, dict] = {}          # id -> {ime, putanja, pod, priprema}
REDOSLED: list[str] = []             # najnovije prvo
_KES_IZVOR: dict[str, tuple] = {}    # sid -> (kljuc, jpeg bajtovi)
_KES_PRESETA: dict[str, bytes] = {}
_KES_MALA: dict[str, tuple] = {}


def _pod(d: dict) -> Podesavanja:
    p = Podesavanja()
    for k, v in (d or {}).items():
        if not hasattr(p, k):
            continue
        tip = type(getattr(p, k))
        try:
            setattr(p, k, (v if tip is bool else tip(v)) if tip is not bool
                    else (v if isinstance(v, bool) else str(v).lower() == "true"))
        except (TypeError, ValueError):
            pass
    return p


def _stanje():
    d = profili.ucitaj()
    return d, profili.ram_iz(d)


# ----------------------------------------------------------------- interfejs

@app.get("/")
def pocetna():
    return send_from_directory(os.path.join(OVDE, "static"), "index.html")


@app.get("/static/<path:p>")
def statika(p):
    return send_from_directory(os.path.join(OVDE, "static"), p)


# ----------------------------------------------------------------- podaci

@app.get("/api/podaci")
def podaci():
    d, r = _stanje()
    return jsonify({
        "podesavanja": d,
        "ram": {"naziv": r.naziv, "prozor": [r.prozor_s, r.prozor_v],
                "rez": [r.rez_s, r.rez_v], "puna": [r.puna_s, r.puna_v],
                "napust": r.napust, "ostro": r.ostro,
                "preklop": [r.preklop_s, r.preklop_v], "odnos": r.odnos},
        "preseti": [{"kljuc": k, "ime": v[0]} for k, v in PRESETI.items()],
        "raspored": tabak.raspored(r, d["tabak"], profili.faktor(d)),
        "slike": [{"id": i, "ime": SLIKE[i]["ime"], "pod": SLIKE[i]["pod"],
                   "priprema": SLIKE[i].get("priprema")}
                  for i in REDOSLED if i in SLIKE],
        "popune": [{"kljuc": k, "ime": v} for k, v in POPUNE.items()],
        "app": profili.app_iz(d),
    })


@app.post("/api/podaci")
def sacuvaj_podatke():
    d = request.get_json(force=True, silent=True)
    if not isinstance(d, dict) or "ramovi" not in d:
        return jsonify({"ok": False, "poruka": "Prazna ili nepotpuna podešavanja."}), 400
    profili.sacuvaj(d)
    return jsonify({"ok": True})


@app.post("/api/kalibracija")
def kalibracija():
    izm = float((request.get_json(force=True, silent=True) or {}).get("izmereno", 150.0))
    d, _ = _stanje()
    f = profili.iz_merenja(izm, d["tabak"].get("lenjir_duzina", 150.0))
    profili.stampac_iz(d)["kalibracija"] = f
    profili.sacuvaj(d)
    dnevnik.upisi("kalibracija", "izmereno %.1f mm" % izm, faktor=round(f, 3))
    return jsonify({"ok": True, "faktor": f})


# ----------------------------------------------------------------- slike

MALA_STRANA = 1400          # na toliko se smanji izvor za sve preglede


def _mala(sid: str) -> Image.Image:
    """
    Smanjena kopija izvorne slike, drzi se u memoriji.

    Svi pregledi (editor, prsten, trake preklopa, tabak) rade nad njom, a ne
    nad fajlom od nekoliko hiljada piksela. Bez ovoga svaka promena popune
    znaci ponovo citanje, nivoe i Gaussian blur nad punom slikom - otuda je
    osvezavanje trajalo sekundama.
    """
    s = SLIKE[sid]
    kljuc = (s["putanja"], s["pod"].get("obrezi_rub"))
    pogodak = _KES_MALA.get(sid)
    if pogodak and pogodak[0] == kljuc:
        return pogodak[1]
    im = ucitaj(s["putanja"])
    if s["pod"].get("obrezi_rub"):
        im = obrezi_rub(im)
    if max(im.size) > MALA_STRANA:
        im = im.copy()
        im.thumbnail((MALA_STRANA, MALA_STRANA), Image.LANCZOS)
    if len(_KES_MALA) > 12:
        _KES_MALA.clear()
    _KES_MALA[sid] = (kljuc, im)
    return im


def boja_i_preset(im: Image.Image, p: Podesavanja) -> Image.Image:
    """Nivoi, zasicenje, pa preset - isti lanac kao u obradi."""
    crna, bela = p.crna, p.bela
    if crna < 0 or bela < 0:
        crna, bela = auto_nivoi(im)
    im = nivoi(im, crna, bela, p.zasicenje)
    return primeni_preset(im, p)


def _upisi(ime: str, putanja: str, pod: dict | None = None,
           izvor_biblioteke: str | None = None) -> dict:
    """Ubaci sliku u red, uvek na vrh."""
    sid = uuid.uuid4().hex[:10]
    p = Podesavanja().__dict__.copy()
    try:
        p["obrezi_rub"] = bool(profili.app_iz(profili.ucitaj()).get("obrezi_rub", False))
    except Exception:
        pass
    if pod:
        p.update({k: v for k, v in pod.items() if k in p})
    SLIKE[sid] = {"ime": ime, "putanja": putanja, "pod": p,
                  "priprema": izvor_biblioteke}
    REDOSLED.insert(0, sid)
    return {"id": sid, "ime": ime, "pod": p, "priprema": izvor_biblioteke}


@app.post("/api/uvoz")
def uvoz():
    """
    Prima bilo koji format koji umemo da otvorimo, ukljucujuci PDF sken.
    Novouvezena slika ide na vrh reda i postaje tekuca.
    """
    dodate, odbijene = [], []
    for f in request.files.getlist("fajl"):
        if not f.filename:
            continue
        ime = os.path.basename(f.filename)
        sid = uuid.uuid4().hex[:10]
        put = os.path.join(RADNA, sid + "_" + ime)
        f.save(put)
        try:
            im = ucitaj(put)                 # pravi test: da li se otvara
            if min(im.size) < 8:
                raise ValueError("slika je premala")
        except Exception as e:
            try:
                os.remove(put)
            except OSError:
                pass
            odbijene.append({"ime": ime, "razlog": str(e)})
            continue
        dodate.append(_upisi(ime, put))
        dnevnik.upisi("uvoz", ime, piksela="%dx%d" % im.size)
    for o in odbijene:
        dnevnik.upisi("uvoz", "odbijen " + o["ime"], razlog=o["razlog"])
    return jsonify({"dodate": dodate, "odbijene": odbijene})


@app.get("/api/izvor/<sid>")
def izvor(sid):
    """
    Slika sa sredjenom bojom, ali BEZ kadriranja - podloga za editor.
    Kadriranje se crta u pregledacu, pa je pomeranje trenutno.
    """
    if sid not in SLIKE:
        return jsonify({"greska": "nema te slike"}), 404
    s = SLIKE[sid]
    p = _pod(s["pod"])
    sirina = max(200, min(2000, int(request.args.get("w", 1100))))
    kljuc = (s["putanja"], p.crna, p.bela, p.zasicenje, p.jasnoca, p.preset,
             p.jacina_preseta, p.obrezi_rub, p.rotacija, p.ogledalo, sirina)
    pogodak = _KES_IZVOR.get(sid)
    if pogodak and pogodak[0] == kljuc:
        podaci = pogodak[1]
    else:
        im = _mala(sid)
        im = boja_i_preset(im, p)
        im = okreni(im, p)            # rotacija i ogledalo se vide i u editoru
        if im.size[0] > sirina:
            im = im.resize((sirina, max(1, round(im.size[1] * sirina / im.size[0]))),
                           Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, "JPEG", quality=88)
        podaci = b.getvalue()
        _KES_IZVOR[sid] = (kljuc, podaci)
    odg = send_file(io.BytesIO(podaci), mimetype="image/jpeg")
    odg.headers["Cache-Control"] = "no-store"
    return odg


@app.post("/api/auto/<sid>")
def auto(sid):
    """Jedno dugme koje sredi sliku: nivoi, zasicenje i lokalni kontrast."""
    if sid not in SLIKE:
        return jsonify({"greska": "nema te slike"}), 404
    s = SLIKE[sid]
    im = ucitaj(s["putanja"])
    if s["pod"].get("obrezi_rub"):
        im = obrezi_rub(im)
    if max(im.size) > 1400:                 # dovoljno za procenu, a brzo
        im = im.copy()
        im.thumbnail((1400, 1400))
    pred = auto_sve(im)
    s["pod"].update(pred)
    dnevnik.upisi("auto", s["ime"], **pred)
    _KES_IZVOR.pop(sid, None)
    return jsonify({"ok": True, "pod": s["pod"], "predlog": pred})


@app.post("/api/podesi/<sid>")
def podesi(sid):
    if sid not in SLIKE:
        return jsonify({"greska": "nema te slike"}), 404
    novo = request.get_json(force=True, silent=True) or {}
    staro = dict(SLIKE[sid]["pod"])
    SLIKE[sid]["pod"].update(novo)
    promene = {k: v for k, v in SLIKE[sid]["pod"].items() if staro.get(k) != v}
    if promene:
        dnevnik.upisi("podesi", SLIKE[sid]["ime"],
                      **{k: v for k, v in list(promene.items())[:6]})
    _KES_IZVOR.pop(sid, None)
    return jsonify({"ok": True, "pod": SLIKE[sid]["pod"]})


@app.delete("/api/slika/<sid>")
def obrisi(sid):
    s = SLIKE.pop(sid, None)
    _KES_IZVOR.pop(sid, None)
    if sid in REDOSLED:
        REDOSLED.remove(sid)
    if s:
        dnevnik.upisi("ukloni", s["ime"])
    if s and os.path.exists(s["putanja"]) and RADNA in os.path.abspath(s["putanja"]):
        try:
            os.remove(s["putanja"])
        except OSError:
            pass
    return jsonify({"ok": True})


def otisak(sid, ram, dpi=150, izvor=None):
    """Gotov otisak (jezgro + napust) nad smanjenom kopijom - brzo, za preglede."""
    p = _pod(SLIKE[sid]["pod"])
    p.dpi = dpi
    im = izvor if izvor is not None else _mala(sid)
    im = okreni(boja_i_preset(im, p), p)
    px = lambda mm: int(round(mm * dpi / 25.4))
    jezgro = smesti(im, px(ram.prozor_s), px(ram.prozor_v), p)
    return napust(jezgro, ram, dpi, p.popuna, p.boja_popune)


@app.get("/api/pregled/<sid>")
def pregled(sid):
    if sid not in SLIKE:
        return jsonify({"greska": "nema te slike"}), 404
    d, r = _stanje()
    dpi = max(40, min(400, int(request.args.get("dpi", 150))))
    im = otisak(sid, r, dpi)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=88)
    odg = send_file(io.BytesIO(b.getvalue()), mimetype="image/jpeg")
    odg.headers["Cache-Control"] = "no-store"
    return odg


# ----------------------------------------------------------------- izlaz

@app.post("/api/pdf")
def pdf():
    telo = request.get_json(force=True, silent=True) or {}
    redosled = telo.get("ids") or list(SLIKE.keys())
    kopija = max(1, int(telo.get("kopija", 1)))
    if not redosled:
        return jsonify({"greska": "nema slika"}), 400

    d, r = _stanje()
    f = profili.faktor(d)
    slike = []
    for sid in redosled:
        if sid not in SLIKE:
            continue
        p = _pod(SLIKE[sid]["pod"])
        im, _ = pripremi(SLIKE[sid]["putanja"], r, p)
        slike.extend([im] * kopija)

    ime = "magneti_%s.pdf" % time.strftime("%Y%m%d_%H%M%S")
    put = os.path.join(IZLAZ, ime)
    info = tabak.slozi_pdf(slike, r, d["tabak"], put, faktor=f,
                           lenjir=bool(telo.get("lenjir", d["tabak"].get("lenjir", True))))
    info["ime"] = ime
    return jsonify(info)


@app.post("/api/kontrolni")
def kontrolni():
    d, r = _stanje()
    ime = "kalibracija.pdf"
    put = tabak.kontrolni_list(r, d["tabak"], os.path.join(IZLAZ, ime),
                               faktor=profili.faktor(d))
    return jsonify({"ime": ime, "putanja": put})


@app.get("/api/preuzmi/<ime>")
def preuzmi(ime):
    return send_from_directory(IZLAZ, ime, as_attachment=True)


@app.post("/api/ugasi")
def ugasi():
    """Gasi server iz interfejsa, da korisnik ne mora da trazi prozor.
    {"ostavi_prozor": true}: restart posle azuriranja (V2), prozor ostaje i sam se ponovo ucita."""
    ostavi = bool((request.get_json(force=True, silent=True) or {}).get("ostavi_prozor"))

    def kasnije():
        time.sleep(0.4)
        dnevnik.upisi("gasenje", "restart" if ostavi else "dugme Ugasi")
        if not ostavi:
            prozor.zatvori()
        os._exit(0)
    threading.Thread(target=kasnije, daemon=True).start()
    return jsonify({"ok": True})


def _cilj(d):
    """Koji Windows stampac i sa kojim papirom."""
    import stampa_win
    s = profili.stampac_iz(d)
    ime = s.get("sistemsko_ime")
    if not ime:
        meta = [p["ime"] for p in stampa_win.lista_stampaca()
                if "L18050" in p["ime"].upper()]
        ime = meta[0] if meta else stampa_win.podrazumevani()
    return ime, s.get("medij"), s.get("ulaz")


@app.get("/api/stampaci")
def stampaci():
    """Spisak stampaca i, za izabranog, tipovi papira koje drajver nudi."""
    try:
        import stampa_win
    except ImportError:
        return jsonify({"ok": False, "poruka": "Štampa nije dostupna na ovoj mašini."}), 501
    d, _ = _stanje()
    ime, medij, ulaz = _cilj(d)
    try:
        return jsonify({"ok": True, "izabrani": ime,
                        "stampaci": stampa_win.lista_stampaca(),
                        "papiri": stampa_win.tipovi_papira(ime),
                        "ulazi": stampa_win.izvori_papira(ime),
                        "medij": medij, "ulaz": ulaz})
    except Exception as e:
        return jsonify({"ok": False, "poruka": str(e)}), 500


@app.post("/api/stampac")
def podesi_stampac():
    """Pamti izbor stampaca, tipa papira i ulaza."""
    t = request.get_json(force=True, silent=True) or {}
    d, _ = _stanje()
    s = profili.stampac_iz(d)
    if "sistemsko_ime" in t:
        s["sistemsko_ime"] = t["sistemsko_ime"] or None
    if "medij" in t:
        s["medij"] = int(t["medij"]) if t["medij"] else None
    if "ulaz" in t:
        s["ulaz"] = int(t["ulaz"]) if t["ulaz"] else None
    if "papir" in t:
        s["papir"] = t["papir"]
    profili.sacuvaj(d)
    dnevnik.upisi("stampac", s.get("sistemsko_ime") or "", papir=s.get("papir"),
                  medij=s.get("medij"), ulaz=s.get("ulaz"))
    return jsonify({"ok": True, "stampac": s})


@app.post("/api/kontrolni_stampa")
def kontrolni_stampa():
    try:
        import stampa_win
    except ImportError:
        return jsonify({"ok": False, "poruka": "Štampa nije dostupna na ovoj mašini."}), 501
    d, r = _stanje()
    ime, medij, ulaz = _cilj(d)
    try:
        izv = stampa_win.odstampaj_kontrolni(r, d["tabak"], profili.faktor(d), ime,
                                             medij=medij, ulaz=ulaz)
        izv["ok"] = True
        return jsonify(izv)
    except Exception as e:
        return jsonify({"ok": False, "poruka": str(e)}), 500


def _otisci(ids, kopija, ram):
    """Pripremljene slike za slaganje na tabak, redom kojim su trazene."""
    out = []
    for sid in ids:
        if sid not in SLIKE:
            continue
        im, _ = pripremi(SLIKE[sid]["putanja"], ram, _pod(SLIKE[sid]["pod"]))
        out.extend([im] * max(1, int(kopija)))
    return out


@app.post("/api/pre_stampe")
def pre_stampe():
    """Šta će se odštampati - za prozor potvrde pre slanja na štampač."""
    t = request.get_json(force=True, silent=True) or {}
    d, r = _stanje()
    ids = [s for s in (t.get("ids") or list(REDOSLED)) if s in SLIKE]
    kopija = max(1, int(t.get("kopija", 1)))
    f = profili.faktor(d)
    rasp = tabak.raspored(r, d["tabak"], f, bool(t.get("lenjir", d["tabak"].get("lenjir", True))))
    ukupno = len(ids) * kopija
    po = max(1, rasp["po_tabaku"])
    try:
        import stampa_win
        s = profili.stampac_iz(d)
        ime, medij, ulaz = _cilj(d)
        papiri = {p["sifra"]: p["ime"] for p in stampa_win.tipovi_papira(ime)}
        papir = papiri.get(medij, "kako je podešeno u drajveru")
        dostupna = True
    except Exception:
        ime, papir, dostupna = "—", "—", False
    return jsonify({"ok": True, "slika": len(ids), "kopija": kopija,
                    "otisaka": ukupno, "po_tabaku": po,
                    "tabaka": max(1, math.ceil(ukupno / po)),
                    "stampac": ime, "papir": papir, "stampa_moguca": dostupna})


@app.post("/api/stampaj")
def stampaj():
    try:
        import stampa_win
    except ImportError:
        return jsonify({
            "ok": False,
            "poruka": "Štampa radi samo na Windowsu, na mašini sa štampačem."
        }), 501
    t = request.get_json(force=True, silent=True) or {}
    d, r = _stanje()
    ids = [s for s in (t.get("ids") or list(REDOSLED)) if s in SLIKE]
    if not ids:
        return jsonify({"ok": False, "poruka": "Nijedna slika nije izabrana."}), 400
    kopija = max(1, int(t.get("kopija", 1)))
    lenjir = bool(t.get("lenjir", d["tabak"].get("lenjir", True)))
    f = profili.faktor(d)
    ime, medij, ulaz = _cilj(d)
    try:
        slike = _otisci(ids, kopija, r)
        rasp = tabak.raspored(r, d["tabak"], f, lenjir)
        izv = stampa_win.odstampaj_tabake(slike, r, d["tabak"], rasp, f, stampac=ime,
                                          lenjir=lenjir, probno=bool(t.get("probno")),
                                          medij=medij, ulaz=ulaz)
    except Exception as e:
        dnevnik.greska("stampa", e, "%d slika na %s" % (len(ids), ime))
        return jsonify({"ok": False, "poruka": str(e)}), 500
    izv["ok"] = True
    dnevnik.upisi("stampa", "%d otisaka na %d tabaka, %s" %
                  (len(slike), izv.get("tabaka", 1), ime))
    return jsonify(izv)


# ------------------------------------------------------------- preseti

def _uzorak() -> Image.Image:
    """Slika na kojoj se prikazuju preseti. Prva iz reda, pa ugradjeni uzorak."""
    for sid in REDOSLED:
        if sid in SLIKE and os.path.isfile(SLIKE[sid]["putanja"]):
            try:
                im = ucitaj(SLIKE[sid]["putanja"])
                im.thumbnail((420, 420))
                return im
            except Exception:
                continue
    p = os.path.join(OVDE, "static", "uzorak.jpg")
    if os.path.isfile(p):
        im = ucitaj(p)
        im.thumbnail((420, 420))
        return im
    return Image.new("RGB", (240, 170), (200, 190, 180))


@app.get("/api/popuna_slika/<kljuc>")
def popuna_slika(kljuc):
    """
    Uvecana ivica otiska za dati nacin popune, da se vidi sta ide ispod
    lajsne. Secemo levu ivicu: pola prozora, pa ceo preklop i napust.
    """
    if kljuc not in POPUNE:
        return jsonify({"greska": "nema te popune"}), 404
    d, r = _stanje()
    sid = REDOSLED[0] if REDOSLED else None
    boja = (SLIKE[sid]["pod"].get("boja_popune") if sid else None) or "#FFFFFF"
    oznaka = "%s:%s:%s:%s" % (sid or "uzorak", kljuc, boja, r.naziv)
    if oznaka not in _KES_PRESETA:
        try:
            if sid:
                p = _pod(SLIKE[sid]["pod"])
                mala = _mala(sid)
            else:
                p = Podesavanja()
                mala = ucitaj(os.path.join(OVDE, "static", "uzorak.jpg"))
            p.popuna, p.boja_popune, p.dpi = kljuc, boja, 110
            mala = okreni(boja_i_preset(mala, p), p)
            px = lambda mm: int(round(mm * p.dpi / 25.4))
            jezgro = smesti(mala, px(r.prozor_s), px(r.prozor_v), p)
            puna = napust(jezgro, r, p.dpi, kljuc, boja)
        except Exception as e:
            return jsonify({"greska": str(e)}), 500
        w, h = puna.size
        rub = h * (r.napust + r.preklop_v) / r.puna_v        # napust + preklop, u px
        visina = max(8, int(rub * 2.4))
        isecak = puna.crop((0, 0, w, min(h, visina)))
        s = 360.0 / isecak.size[0]
        isecak = isecak.resize((360, max(6, int(isecak.size[1] * s))), Image.LANCZOS)
        crt = ImageDraw.Draw(isecak)
        y = rub * s                                          # gde pocinje prozor
        crt.line([0, y, 360, y], fill=(255, 253, 248), width=2)
        b = io.BytesIO()
        isecak.save(b, "JPEG", quality=86)
        if len(_KES_PRESETA) > 40:
            _KES_PRESETA.clear()
        _KES_PRESETA[oznaka] = b.getvalue()
    odg = send_file(io.BytesIO(_KES_PRESETA[oznaka]), mimetype="image/jpeg")
    odg.headers["Cache-Control"] = "no-store"
    return odg


@app.get("/api/preset_slika/<kljuc>")
def preset_slika(kljuc):
    """Slicica jednog preseta. Kesira se dok se red ne promeni."""
    if kljuc not in PRESETI:
        return jsonify({"greska": "nema tog preseta"}), 404
    oznaka = (REDOSLED[0] if REDOSLED else "uzorak") + ":" + kljuc
    if oznaka not in _KES_PRESETA:
        im = PRESETI[kljuc][1](_uzorak())
        b = io.BytesIO()
        im.convert("RGB").save(b, "JPEG", quality=84)
        if len(_KES_PRESETA) > 40:
            _KES_PRESETA.clear()
        _KES_PRESETA[oznaka] = b.getvalue()
    odg = send_file(io.BytesIO(_KES_PRESETA[oznaka]), mimetype="image/jpeg")
    odg.headers["Cache-Control"] = "no-store"
    return odg


# ------------------------------------------------------------- ramovi

@app.post("/api/ram")
def sacuvaj_ram():
    """Dodaj nov ram ili prepisi postojeci. `indeks` = -1 znaci nov."""
    t = request.get_json(force=True, silent=True) or {}
    d = profili.ucitaj()
    try:
        nov = {
            "naziv": (t.get("naziv") or "Bez naziva").strip()[:60],
            "prozor_s": float(t["prozor_s"]), "prozor_v": float(t["prozor_v"]),
            "rez_s": float(t["rez_s"]), "rez_v": float(t["rez_v"]),
            "napust": float(t.get("napust", 3.0)),
            "ostro": float(t.get("ostro", 1.5)),
            "beleska": (t.get("beleska") or "").strip()[:400],
        }
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "poruka": "Nedostaje neka mera."}), 400
    for k in ("prozor_s", "prozor_v", "rez_s", "rez_v"):
        if not (5.0 <= nov[k] <= 400.0):
            return jsonify({"ok": False,
                            "poruka": "Mera %s = %.2f mm nije razumna." % (k, nov[k])}), 400
    if nov["rez_s"] <= nov["prozor_s"] or nov["rez_v"] <= nov["prozor_v"]:
        return jsonify({"ok": False,
                        "poruka": "Rez mora biti veći od prozora, inače nema preklopa."}), 400

    i = int(t.get("indeks", -1))
    if 0 <= i < len(d["ramovi"]):
        d["ramovi"][i] = nov
    else:
        d["ramovi"].append(nov)
        i = len(d["ramovi"]) - 1
    if t.get("izaberi", True):
        d["izabrani_ram"] = i
    profili.sacuvaj(d)
    dnevnik.upisi("ram", "sačuvan " + nov["naziv"],
                  prozor="%.2fx%.2f" % (nov["prozor_s"], nov["prozor_v"]),
                  rez="%.2fx%.2f" % (nov["rez_s"], nov["rez_v"]))
    return jsonify({"ok": True, "indeks": i, "ramovi": d["ramovi"],
                    "izabrani_ram": d["izabrani_ram"]})


@app.post("/api/izaberi_ram/<int:i>")
def izaberi_ram(i):
    d = profili.ucitaj()
    if not (0 <= i < len(d["ramovi"])):
        return jsonify({"ok": False, "poruka": "Nema tog rama."}), 404
    d["izabrani_ram"] = i
    profili.sacuvaj(d)
    dnevnik.upisi("ram", "izabran " + d["ramovi"][i].get("naziv", "?"))
    return jsonify({"ok": True, "izabrani_ram": i})


@app.delete("/api/ram/<int:i>")
def obrisi_ram(i):
    d = profili.ucitaj()
    if len(d["ramovi"]) <= 1:
        return jsonify({"ok": False, "poruka": "Mora ostati bar jedan ram."}), 400
    if not (0 <= i < len(d["ramovi"])):
        return jsonify({"ok": False, "poruka": "Nema tog rama."}), 404
    obrisan = d["ramovi"].pop(i)
    d["izabrani_ram"] = min(d["izabrani_ram"], len(d["ramovi"]) - 1)
    profili.sacuvaj(d)
    dnevnik.upisi("ram", "obrisan " + obrisan.get("naziv", "?"))
    return jsonify({"ok": True, "ramovi": d["ramovi"], "izabrani_ram": d["izabrani_ram"]})


@app.post("/api/stl")
def iz_stl():
    """Izmeri otvor iz STL fajla i predloži mere rama."""
    f = request.files.get("fajl")
    if not f or not f.filename:
        return jsonify({"ok": False, "poruka": "Nije poslat fajl."}), 400
    put = os.path.join(IZLAZ, "mera_" + uuid.uuid4().hex[:8] + ".stl")
    f.save(put)
    try:
        import stl_mere
        d = profili.ucitaj()
        a = profili.app_iz(d)
        izv = stl_mere.izmeri(put, skupljanje=float(a.get("skupljanje", 0.7)))
        izv["ok"] = True
        izv["ime"] = os.path.basename(f.filename)
        if not izv.get("predlog", {}).get("prozor"):
            izv["ok"] = False
            izv["poruka"] = ("U modelu nije nađen pravougaoni otvor na sredini. "
                             "Unesi mere ručno.")
        return jsonify(izv)
    except Exception as e:
        return jsonify({"ok": False, "poruka": "Ne mogu da pročitam STL: %s" % e}), 400
    finally:
        try:
            os.remove(put)
        except OSError:
            pass


# ------------------------------------------------------------- podesavanja

@app.post("/api/app")
def podesi_app():
    t = request.get_json(force=True, silent=True) or {}
    d = profili.ucitaj()
    a = profili.app_iz(d)
    for k in ("tema", "biblioteka", "svi_papiri", "obrezi_rub", "skupljanje"):
        if k in t:
            a[k] = t[k]
    for k in ("ivica", "razmak", "lenjir", "lenjir_duzina"):
        if k in t:
            d["tabak"][k] = t[k]
    profili.sacuvaj(d)
    dnevnik.upisi("podesavanja", "", **{k: v for k, v in t.items() if k != "biblioteka"})
    return jsonify({"ok": True, "app": a, "tabak": d["tabak"]})


# ------------------------------------------------------------- dnevnik

@app.get("/api/dnevnik")
def citaj_dnevnik():
    a = request.args
    return jsonify({
        "ok": True,
        "redovi": dnevnik.procitaj(dana=int(a.get("dana", 2)),
                                   samo_greske=a.get("greske") == "1",
                                   trazi=(a.get("trazi") or "").strip() or None,
                                   koliko=int(a.get("koliko", 800))),
        "mb": dnevnik.velicina_mb(),
        "fajlova": dnevnik.broj_fajlova()})


@app.delete("/api/dnevnik")
def obrisi_dnevnik():
    """Brise samo fajlove starije od N dana; dnevnik se ne brise ceo (L1)."""
    n = dnevnik.obrisi_starije(int(request.args.get("stariji_od", 30)))
    return jsonify({"ok": True, "obrisano": n, "mb": dnevnik.velicina_mb(),
                    "fajlova": dnevnik.broj_fajlova()})


@app.get("/health")
def health():
    """P2: potvrda da na ovom portu stoji ova aplikacija (pid i version za version.js, V3)."""
    return jsonify({"app": version.APP_NAME, "verzija": version.VERSION, "version": version.VERSION,
                    "pid": os.getpid(), "oznaka": version.label()})


# ------------------------------------------------------------- azuriranje (V2, V3)

def _git_spreman():
    import update
    return os.path.isdir(os.path.join(OVDE_APP, ".git")) and bool(update.git_exe())


@app.get("/api/update")
def azuriranje_stanje():
    if not _git_spreman():
        return jsonify({"ok": False, "error": "Ažuriranje nije podešeno na ovom računaru."})
    import update
    return jsonify(update.status(version.VERSION))


@app.post("/api/update")
def azuriranje():
    if not _git_spreman():
        return jsonify({"ok": False, "error": "Ažuriranje nije podešeno na ovom računaru."})
    import update
    r = update.apply(version.VERSION)
    return jsonify({"ok": r.get("ok"), "changed": r.get("changed"),
                    "error": None if r.get("ok") else "Ažuriranje nije uspelo (detalji u dnevniku)."})


# ------------------------------------------------------------- izbor fascikle

@app.post("/api/izaberi_fasciklu")
def izaberi_fasciklu():
    """
    Otvori sistemski prozor za izbor fascikle. Radi zato sto server zivi
    na istoj masini kao i korisnik; da je na mrezi, ovo ne bi imalo smisla.
    """
    rezultat = {}

    def dijalog():
        try:
            import tkinter
            from tkinter import filedialog
            k = tkinter.Tk()
            k.withdraw()
            k.attributes("-topmost", True)
            p = filedialog.askdirectory(title="Izaberi fasciklu za biblioteku",
                                        initialdir=_koren() or os.path.expanduser("~"))
            k.destroy()
            rezultat["put"] = p or None
        except Exception as e:
            rezultat["greska"] = str(e)

    n = threading.Thread(target=dijalog)
    n.start()
    n.join(timeout=180)
    if "greska" in rezultat:
        dnevnik.upisi("biblioteka", "izbor fascikle nije uspeo", razlog=rezultat["greska"])
        return jsonify({"ok": False, "poruka":
                        "Sistemski izbor fascikle nije dostupan, upiši putanju ručno."}), 501
    put = rezultat.get("put")
    if not put:
        return jsonify({"ok": False, "otkazano": True})
    return jsonify({"ok": True, "putanja": os.path.normpath(put)})


# ------------------------------------------------------------- biblioteka

SLIKOVNI = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic", ".pdf"}


def _unutar(koren: str, rel: str) -> str:
    """Sprečava izlazak iz fascikle biblioteke preko ../ ."""
    pun = os.path.abspath(os.path.join(koren, rel or ""))
    if not pun.startswith(os.path.abspath(koren)):
        raise ValueError("izlazak iz biblioteke")
    return pun


@app.get("/api/pregledaj")
def pregledaj():
    """Sadržaj fascikle u biblioteci: podfascikle i slike."""
    koren = _koren()
    rel = request.args.get("put", "")
    try:
        pun = _unutar(koren, rel)
    except ValueError:
        return jsonify({"ok": False, "poruka": "Nedozvoljena putanja."}), 400
    if not os.path.isdir(pun):
        return jsonify({"ok": True, "koren": koren, "put": "", "fascikle": [],
                        "slike": [], "poruka": "Fascikla ne postoji."})
    fascikle, slike = [], []
    try:
        for ime in sorted(os.listdir(pun)):
            p = os.path.join(pun, ime)
            if os.path.isdir(p):
                fascikle.append({"ime": ime,
                                 "put": os.path.join(rel, ime).replace("\\", "/"),
                                 "priprema": os.path.isfile(os.path.join(p, "priprema.json"))})
            elif os.path.splitext(ime)[1].lower() in SLIKOVNI:
                slike.append({"ime": ime,
                              "put": os.path.join(rel, ime).replace("\\", "/"),
                              "bajtova": os.path.getsize(p)})
    except OSError as e:
        return jsonify({"ok": False, "poruka": str(e)}), 500
    return jsonify({"ok": True, "koren": koren, "put": rel.replace("\\", "/"),
                    "gore": os.path.dirname(rel.rstrip("/")).replace("\\", "/") if rel else None,
                    "fascikle": fascikle, "slike": slike})


@app.get("/api/slicica")
def slicica():
    """Mala sličica bilo koje slike iz biblioteke."""
    try:
        pun = _unutar(_koren(), request.args.get("put", ""))
    except ValueError:
        return jsonify({"greska": "nedozvoljeno"}), 400
    if not os.path.isfile(pun):
        return jsonify({"greska": "nema fajla"}), 404
    try:
        im = ucitaj(pun)
        im.thumbnail((160, 160))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=80)
    except Exception:
        return jsonify({"greska": "ne mogu da otvorim"}), 415
    odg = send_file(io.BytesIO(b.getvalue()), mimetype="image/jpeg")
    odg.headers["Cache-Control"] = "no-store"
    return odg


@app.post("/api/otvori_iz_biblioteke")
def otvori_iz_biblioteke():
    """Ubaci sliku iz biblioteke u editor, sa podešavanjima ako ih ima."""
    t = request.get_json(force=True, silent=True) or {}
    try:
        pun = _unutar(_koren(), t.get("put", ""))
    except ValueError:
        return jsonify({"ok": False, "poruka": "Nedozvoljena putanja."}), 400
    if not os.path.isfile(pun):
        return jsonify({"ok": False, "poruka": "Fajl ne postoji."}), 404
    pod = None
    fas = os.path.dirname(pun)
    zapis = os.path.join(fas, "priprema.json")
    oznaka = None
    if os.path.isfile(zapis):
        try:
            with open(zapis, "r", encoding="utf-8") as f:
                z = json.load(f)
            pod = z.get("podesavanja")
            oznaka = os.path.basename(fas)
        except Exception:
            pass
    nova = _upisi(os.path.basename(pun), pun, pod, oznaka)
    dnevnik.upisi("biblioteka", "otvoreno " + os.path.basename(pun))
    return jsonify({"ok": True, "slika": nova})


def _koren():
    d = profili.ucitaj()
    return profili.app_iz(d).get("biblioteka")


@app.get("/api/biblioteka")
def biblioteka_spisak():
    k = _koren()
    return jsonify({"ok": True, "koren": k, "stavke": biblioteka.spisak(k)})


@app.get("/api/biblioteka/pregled/<fascikla>")
def biblioteka_pregled(fascikla):
    p = biblioteka.putanja_pregleda(_koren(), fascikla)
    if not p:
        return jsonify({"greska": "nema pregleda"}), 404
    return send_file(p, mimetype="image/jpeg")


@app.post("/api/biblioteka/sacuvaj")
def biblioteka_sacuvaj():
    t = request.get_json(force=True, silent=True) or {}
    sid = t.get("id")
    if sid not in SLIKE:
        return jsonify({"ok": False, "poruka": "Nema te slike."}), 404
    s = SLIKE[sid]
    d, r = _stanje()
    p = _pod(s["pod"])
    p.dpi = 110
    try:
        im, _ = pripremi(s["putanja"], r, p)
    except Exception:
        im = None
    naziv = (t.get("naziv") or os.path.splitext(s["ime"])[0]).strip()
    try:
        z = biblioteka.sacuvaj(_koren(), naziv, s["putanja"], s["pod"],
                               {"naziv": r.naziv, "prozor": [r.prozor_s, r.prozor_v],
                                "rez": [r.rez_s, r.rez_v], "napust": r.napust,
                                "ostro": r.ostro},
                               pregled=im, prepisi=t.get("prepisi") or None)
    except Exception as e:
        dnevnik.greska("priprema", e, naziv)
        return jsonify({"ok": False, "poruka": "Ne mogu da snimim: %s" % e}), 500
    s["priprema"] = z["fascikla"]
    dnevnik.upisi("priprema", "sačuvana " + z["fascikla"])
    return jsonify({"ok": True, "zapis": z})


@app.post("/api/biblioteka/otvori/<fascikla>")
def biblioteka_otvori(fascikla):
    z = biblioteka.ucitaj(_koren(), fascikla)
    if not z or not os.path.isfile(z.get("putanja_izvora", "")):
        return jsonify({"ok": False, "poruka": "Priprema nije potpuna."}), 404
    for sid in list(REDOSLED):
        if SLIKE.get(sid, {}).get("priprema") == fascikla:
            REDOSLED.remove(sid)
            REDOSLED.insert(0, sid)
            return jsonify({"ok": True, "slika": {"id": sid, "ime": SLIKE[sid]["ime"],
                                                  "pod": SLIKE[sid]["pod"],
                                                  "priprema": fascikla}})
    nova = _upisi(z.get("naziv") or fascikla, z["putanja_izvora"],
                  z.get("podesavanja"), fascikla)
    return jsonify({"ok": True, "slika": nova, "ram": z.get("ram")})


@app.delete("/api/biblioteka/<fascikla>")
def biblioteka_obrisi(fascikla):
    ok = biblioteka.obrisi(_koren(), fascikla)
    for s in SLIKE.values():
        if s.get("priprema") == fascikla:
            s["priprema"] = None
    return jsonify({"ok": ok})


# ------------------------------------------------------------- tabak

@app.post("/api/tabak_maks")
def tabak_maks():
    """
    Nadji razmak i ivicu pri kojima na list stane najvise komada.

    Donja granica razmaka je 5 mm: marke za rez idu 5 mm preko linije reza,
    a oko svake slike vec stoji napust, pa ispod toga marke susednih slika
    pocinju da se dodiruju.
    """
    d, r = _stanje()
    t = dict(d["tabak"])
    f = profili.faktor(d)
    lenjir = bool(t.get("lenjir", True))
    najbolji, izbor = None, None
    for ivica in (10.0, 8.0, 6.0, 5.0):
        for razmak in (12.0, 10.0, 8.0, 6.0, 5.0):
            proba = dict(t, ivica=ivica, razmak=razmak)
            rasp = tabak.raspored(r, proba, f, lenjir)
            kljuc = (rasp["po_tabaku"], razmak, ivica)   # vise komada, pa siri razmak
            if najbolji is None or kljuc > najbolji:
                najbolji, izbor = kljuc, (ivica, razmak, rasp)
    sada = tabak.raspored(r, t, f, lenjir)
    ivica, razmak, rasp = izbor
    if request.args.get("probno") == "1":
        return jsonify({"ok": True, "sada": sada["po_tabaku"], "moze": rasp["po_tabaku"],
                        "ivica": ivica, "razmak": razmak})
    d["tabak"]["ivica"] = ivica
    d["tabak"]["razmak"] = razmak
    profili.sacuvaj(d)
    dnevnik.upisi("tabak", "najgušći raspored", ivica=ivica, razmak=razmak,
                  po_tabaku=rasp["po_tabaku"])
    return jsonify({"ok": True, "pre": sada["po_tabaku"], "po_tabaku": rasp["po_tabaku"],
                    "ivica": ivica, "razmak": razmak, "raspored": rasp})


@app.get("/api/tabak_pregled")
def tabak_pregled():
    """Slika celog A4 lista sa rasporedom, za tab Tabak."""
    d, r = _stanje()
    t, f = d["tabak"], profili.faktor(d)
    lenjir = bool(request.args.get("lenjir", "1") != "0")
    rasp = tabak.raspored(r, t, f, lenjir)
    razmera = 3.2                                  # px po mm
    W = int(t["sirina"] * razmera)
    H = int(t["visina"] * razmera)
    im = Image.new("RGB", (W, H), "white")
    crt = ImageDraw.Draw(im)
    mm = lambda v: v * razmera

    k, red = rasp["kolona"], rasp["redova"]
    pw, ph = rasp["pw"], rasp["ph"]
    rez_w, rez_h = r.rez_s * f, r.rez_v * f
    if rasp["uspravno"]:
        rez_w, rez_h = rez_h, rez_w
    uk = k * pw + (k - 1) * t["razmak"]
    x0 = (t["sirina"] - uk) / 2.0

    # koji otisci stvarno idu na prvi list
    ids = [x for x in (request.args.get("ids", "").split(",") if request.args.get("ids")
                       else list(REDOSLED)) if x in SLIKE]
    kopija = max(1, int(request.args.get("kopija", 1)))
    niz = []
    for sid in ids:
        niz.extend([sid] * kopija)
    po_tabaku = max(1, k * red)
    prvi = niz[:po_tabaku]

    kes = {}
    for i in range(po_tabaku):
        rr, kk = divmod(i, k)
        bx = x0 + kk * (pw + t["razmak"])
        by = t["ivica"] + rr * (ph + t["razmak"])
        tx = bx + (pw - rez_w) / 2.0
        ty = by + (ph - rez_h) / 2.0
        kutija = (int(mm(tx)), int(mm(ty)), int(mm(tx + rez_w)), int(mm(ty + rez_h)))
        if i < len(prvi):
            sid = prvi[i]
            if sid not in kes:
                try:
                    o = otisak(sid, r, dpi=90)
                    if rasp["uspravno"]:
                        o = o.rotate(90, expand=True)
                    kes[sid] = o
                except Exception:
                    kes[sid] = None
            o = kes[sid]
            if o is not None:
                sir, vis = kutija[2] - kutija[0], kutija[3] - kutija[1]
                crt.rectangle([mm(bx), mm(by), mm(bx + pw), mm(by + ph)], fill="#F2EDE4")
                im.paste(o.resize((max(1, sir), max(1, vis)), Image.LANCZOS),
                         (kutija[0], kutija[1]))
            else:
                crt.rectangle([mm(bx), mm(by), mm(bx + pw), mm(by + ph)], fill="#E8E2D8")
            crt.rectangle(list(kutija), outline="#4A443A", width=2)
        else:
            crt.rectangle(list(kutija), outline="#D4CCBD", width=2)
    if lenjir:
        L = t.get("lenjir_duzina", 150.0) * f
        lx = (t["sirina"] - L) / 2.0
        ly = t["visina"] - t["ivica"] - 6.0
        crt.line([mm(lx), mm(ly), mm(lx + L), mm(ly)], fill="#8A7F6B", width=2)
        n = int(round(t.get("lenjir_duzina", 150.0) / 10.0))
        for i in range(n + 1):
            x = lx + i * L / n
            crt.line([mm(x), mm(ly), mm(x), mm(ly - (4 if i % 5 == 0 else 2.5))],
                     fill="#8A7F6B", width=2)
    crt.rectangle([0, 0, W - 1, H - 1], outline="#B8AE9C")
    b = io.BytesIO()
    im.save(b, "PNG")
    odg = send_file(io.BytesIO(b.getvalue()), mimetype="image/png")
    odg.headers["X-Po-Tabaku"] = str(rasp["po_tabaku"])
    odg.headers["X-Na-Listu"] = str(len(prvi))
    odg.headers["Cache-Control"] = "no-store"
    return odg


def vec_radi(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8733))
    url = "http://127.0.0.1:%d" % port
    import update
    update.init(OVDE_APP, version_file="version.py", launcher="server.py")

    if "--restart" in sys.argv:
        # posle azuriranja: stari server se gasi (prozor ostaje i sam se ucita), pa se dize novi
        import urllib.request
        try:
            z = urllib.request.Request(url + "/api/ugasi", data=b'{"ostavi_prozor": true}',
                                       headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(z, timeout=3).read()
        except Exception:
            pass
        for _ in range(60):
            if not vec_radi(port):
                break
            time.sleep(0.5)
        sys.argv.append("--bez-pregledaca")
    # Dvoklik dok vec radi: ne rusi se na "port zauzet", samo otvori prozor.
    elif vec_radi(port):
        prozor.otvori(url)
        sys.exit(0)

    d, r = _stanje()
    print("Priprema magneta")
    print("  ram        %s  (prozor %.2f x %.2f, rez %.2f x %.2f)"
          % (r.naziv, r.prozor_s, r.prozor_v, r.rez_s, r.rez_v))
    print("  kalibracija %.2f %%" % profili.stampac_iz(d)["kalibracija"])
    print("  otvori      http://127.0.0.1:%d" % port)
    if "--bez-pregledaca" not in sys.argv:
        threading.Timer(1.0, prozor.otvori, args=(url,)).start()

    def ugasi_iz_ikonice():
        dnevnik.upisi("gasenje", "ikonica pored sata")
        prozor.zatvori()
        os._exit(0)
    prozor.ikonica(url, ugasi_iz_ikonice)
    dnevnik.upisi("start", version.label(), port=port)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
