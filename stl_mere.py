#!/usr/bin/env python3
"""
Merenje otvora u ramu iz STL fajla.

Zasto ovako: otvor rama je unutrasnja kontura preseka. Presecemo model
vodoravnom ravni, sastavimo zatvorene petlje od duzi koje ravan preseca,
i od njih uzmemo one unutrasnje. Bez ray castinga i bez trimesh-a - samo
numpy, da aplikacija ostane laka za instalaciju.

VAZNA NAPOMENA koja ide i u korisnicki deo: STL daje PROJEKTOVANU meru.
Odstampan PLA se skupi oko 0.6-0.8 %, pa se broj odavde uzima kao predlog,
a konacna mera se izmeri sublerom na odstampanom ramu.
"""
from __future__ import annotations

import struct

import numpy as np

TOL = 1e-4


# ------------------------------------------------------------------ citanje

def ucitaj_stl(putanja: str) -> np.ndarray:
    """Vrati niz trouglova oblika (n, 3, 3)."""
    with open(putanja, "rb") as f:
        glava = f.read(84)
        if len(glava) < 84:
            raise ValueError("Fajl je prekratak da bi bio STL.")
        broj = struct.unpack("<I", glava[80:84])[0]
        ostatak = f.read()

    if len(ostatak) == broj * 50 and broj > 0:
        a = np.frombuffer(ostatak, dtype=np.uint8).reshape(broj, 50)
        t = a[:, 12:48].copy().view(np.float32).reshape(broj, 3, 3)
        return t.astype(np.float64)

    # ASCII
    with open(putanja, "r", errors="ignore") as f:
        tacke = []
        for red in f:
            red = red.strip()
            if red.startswith("vertex"):
                d = red.split()
                tacke.append((float(d[1]), float(d[2]), float(d[3])))
    if len(tacke) < 3 or len(tacke) % 3:
        raise ValueError("Ne mogu da pročitam STL (ni binarni ni ASCII).")
    return np.asarray(tacke, dtype=np.float64).reshape(-1, 3, 3)


# ------------------------------------------------------------------ presek

def _duzi_na_z(tr: np.ndarray, z: float) -> list:
    """Duzi koje ravan z pravi kroz trouglove."""
    Z = tr[:, :, 2]
    iznad = Z > z
    broj = iznad.sum(axis=1)
    sel = (broj == 1) | (broj == 2)
    if not sel.any():
        return []
    t = tr[sel]
    out = []
    for v in t:
        tacke = []
        for i in range(3):
            a, b = v[i], v[(i + 1) % 3]
            za, zb = a[2], b[2]
            if (za > z) == (zb > z):
                continue
            if abs(zb - za) < 1e-12:
                continue
            f = (z - za) / (zb - za)
            tacke.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
        if len(tacke) == 2:
            p, q = tacke
            if abs(p[0] - q[0]) > TOL or abs(p[1] - q[1]) > TOL:
                out.append((p, q))
    return out


def _petlje(duzi: list) -> list:
    """Sastavi zatvorene petlje od neuredjenih duzi."""
    kljuc = lambda p: (round(p[0] / TOL), round(p[1] / TOL))
    veze: dict = {}
    for p, q in duzi:
        veze.setdefault(kljuc(p), []).append((kljuc(q), q))
        veze.setdefault(kljuc(q), []).append((kljuc(p), p))

    poseceno = set()
    petlje = []
    for start in list(veze):
        if start in poseceno:
            continue
        put, tek, pret = [], start, None
        while tek is not None and tek not in poseceno:
            poseceno.add(tek)
            sledeci = None
            for k, tacka in veze.get(tek, []):
                if k == pret:
                    continue
                if k in poseceno:
                    sledeci = None
                    if k == start:
                        put.append(tacka)
                    break
                sledeci = (k, tacka)
                break
            if sledeci is None:
                break
            put.append(sledeci[1])
            pret, tek = tek, sledeci[0]
        if len(put) >= 3:
            petlje.append(np.asarray(put, dtype=np.float64))
    return petlje


def _povrsina(p: np.ndarray) -> float:
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def otvori_na_z(tr: np.ndarray, z: float) -> list[dict]:
    """
    Unutrasnji otvori na visini z, sortirani od veceg ka manjem.
    Svaki je {'sirina','visina','povrsina','centar'}.
    """
    p = _petlje(_duzi_na_z(tr, z))
    if len(p) < 2:
        return []
    povrs = [abs(_povrsina(x)) for x in p]
    spolja = int(np.argmax(povrs))
    out = []
    for i, petlja in enumerate(p):
        if i == spolja or povrs[i] < 1.0:
            continue
        x0, y0 = petlja[:, 0].min(), petlja[:, 1].min()
        x1, y1 = petlja[:, 0].max(), petlja[:, 1].max()
        w, h = float(x1 - x0), float(y1 - y0)
        okvir = max(w * h, 1e-9)
        out.append({"sirina": round(w, 2), "visina": round(h, 2),
                    "povrsina": round(povrs[i], 1),
                    "pravougaonost": round(povrs[i] / okvir, 3),
                    "centar": [round(float((x0 + x1) / 2), 2),
                               round(float((y0 + y1) / 2), 2)]})
    out.sort(key=lambda d: -d["povrsina"])
    return out


# ------------------------------------------------------------------ pregled

def izmeri(putanja: str, koraka: int = 40,
           skupljanje: float = 0.7, preklop: float = 2.0) -> dict:
    """
    Prodji kroz model po visini i prijavi sve razlicite otvore koje nadjes.
    Vraca predlog za prozor (najmanji stabilan otvor) i za prorez.
    """
    tr = ucitaj_stl(putanja)
    zmin = float(tr[:, :, 2].min())
    zmax = float(tr[:, :, 2].max())
    vis = zmax - zmin
    if vis <= 0:
        raise ValueError("Model nema visinu.")

    gx = float(tr[:, :, 0].max() - tr[:, :, 0].min())
    gy = float(tr[:, :, 1].max() - tr[:, :, 1].min())
    cx = float(tr[:, :, 0].max() + tr[:, :, 0].min()) / 2.0
    cy = float(tr[:, :, 1].max() + tr[:, :, 1].min()) / 2.0

    def vredi(o):
        """Prozor je velik, pravougaon i otprilike na sredini rama.
        Sitne petlje u ornamentu ispadaju ovim pragom."""
        if o["sirina"] < 0.25 * gx or o["visina"] < 0.25 * gy:
            return False
        if o["pravougaonost"] < 0.88:
            return False
        if o["sirina"] > 0.90 * gx and o["visina"] > 0.90 * gy:
            return False            # to je spoljna kontura ornamenta, ne otvor
        return (abs(o["centar"][0] - cx) < 0.12 * gx
                and abs(o["centar"][1] - cy) < 0.12 * gy)

    nalazi = []
    for i in range(koraka):
        z = zmin + vis * (i + 0.5) / koraka
        for o in otvori_na_z(tr, z):
            if not vredi(o):
                continue
            o = dict(o)
            o["z"] = round(z - zmin, 2)
            nalazi.append(o)

    # grupisi po meri, zaokruzeno na 0.1 mm
    grupe: dict = {}
    for o in nalazi:
        k = (round(o["sirina"], 1), round(o["visina"], 1))
        g = grupe.setdefault(k, {"sirina": k[0], "visina": k[1],
                                 "od_z": o["z"], "do_z": o["z"], "pojava": 0})
        g["od_z"] = min(g["od_z"], o["z"])
        g["do_z"] = max(g["do_z"], o["z"])
        g["pojava"] += 1

    stabilni = [g for g in grupe.values() if g["pojava"] >= max(2, koraka // 15)]
    po_meri = sorted(stabilni or list(grupe.values()),
                     key=lambda g: g["sirina"] * g["visina"])

    # Prozor je najmanji od ozbiljnih otvora - sve iznad njega je prorez ili
    # usta levka, a ta mera nije pouzdana jer se levak siri.
    predlog = {}
    s = 1.0 - max(0.0, min(3.0, skupljanje)) / 100.0
    if po_meri:
        pw, ph = po_meri[0]["sirina"] * s, po_meri[0]["visina"] * s
        predlog["prozor_projektovan"] = [po_meri[0]["sirina"], po_meri[0]["visina"]]
        predlog["prozor"] = [round(pw, 2), round(ph, 2)]
        predlog["rez"] = [round(pw + 2 * preklop, 2), round(ph + 2 * preklop, 2)]
        predlog["skupljanje"] = skupljanje
        predlog["preklop"] = preklop
    if len(po_meri) > 1:
        predlog["sledeci_otvor"] = [po_meri[1]["sirina"], po_meri[1]["visina"]]

    return {
        "gabarit": [round(float(tr[:, :, 0].max() - tr[:, :, 0].min()), 2),
                    round(float(tr[:, :, 1].max() - tr[:, :, 1].min()), 2),
                    round(vis, 2)],
        "trouglova": int(tr.shape[0]),
        "otvori": po_meri,
        "predlog": predlog,
        "upozorenje": "STL daje projektovanu meru. Odštampan PLA se skupi "
                      "oko 0.7 %, pa posle prve štampe izmeri prozor "
                      "šublerom i ispravi broj.",
    }


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(izmeri(sys.argv[1]), ensure_ascii=False, indent=2))
