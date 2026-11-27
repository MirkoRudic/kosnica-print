Važe pravila iz `RULES.md` u repou MirkoRudic/vajb-osnova (za modele i štampu i `RULES_3D_PRINTING.md`). Ovde su arhitektura, zamke i izuzeci. Šta app radi iz ugla korisnika je u `SPECIFICATION.md` — svaka izmena ponašanja prvo tamo. Dokle smo stigli: `STATUS.md`. Šta je već probano i nije radilo: `ATTEMPTS.md` — pročitati pre predloga rešenja.

# Košnica Print

Lokalna aplikacija za pripremu fotografija i štampu u radionici Ožiljak.
Folder: `C:\Users\zzroz\Desktop\VAJB\kosnica-print` (do 20.11.2026 `Documents\PripremaMagneta`).
Pregledač samo crta interfejs; obrada slike i izvoz rade u Python procesu,
pa između slike i štampača nema ničega što bi je skaliralo. To je ceo razlog
za aplikaciju i zato se ništa od obrade ne sme preseliti u pregledač.

Radi nezavisno od **Košnice 3D** — zaseban folder, zaseban port, zaseban
dnevnik. Ništa se ne deli između te dve aplikacije.

## Arhitektura

| Fajl | Šta radi |
|---|---|
| `server.py` | Flask na 127.0.0.1:8733, sve API rute, orkestracija štampe |
| `obrada.py` | obrada slike bez zavisnosti od platforme (`smesti`, `napust`, `auto_nivoi`, preseti); PDF kroz pymupdf 400 dpi, HEIC kroz pillow-heif |
| `tabak.py` | raspored na A4, crtice za rez, PDF kroz reportlab |
| `stampa_win.py` | Windows štampa: win32print, DEVMODE, crtanje u milimetrima |
| `profili.py` | ramovi, štampači, kalibracija — `podaci/profili.json` |
| `biblioteka.py` | drvo fascikli i pripreme |
| `dnevnik.py` | tanak sloj nad `applog.py` (kopija iz `moduli/`) |
| `version.py` | kopija iz `moduli/`; `APP_NAME` i `VERSION` se podižu pri slanju na git |
| `stl_mere.py` | merenje prozora rama iz STL fajla |
| `sastavi.py` | sastavlja `static/index.html` iz delova |
| `prozor.py` | P3/P4: Edge `--app` (profil `podaci/edge`), ikonica pored sata (pystray), gašenje zatvara prozor |
| `PripremaMagneta.vbs` | pokretanje bez konzole; prečicu „Košnica Print“ na Desktopu pravi/osvežava pri svakom pokretanju |

### Interfejs

`static/index.html` se **ne menja ručno** — sastavlja se iz
`deo_glava.html` (CSS) + `deo_telo.html` (markup, `__SPRAJT__`) +
`deo_skripta.html` (JS), sa `ikone.svg` ulepljenim umesto `__SPRAJT__`.
Posle svake izmene dela: `python sastavi.py`.

Ikonice su **Tabler Icons 3.31.0** (MIT), kao inline sprajt. `i-znak` nije
ikonica nego znak aplikacije, pa je svoj.

## Poznate zamke

- **Štampa radi samo na Windows-u.** Na drugim sistemima `stampa_win.py`
  prijavljuje da štampa nije dostupna; ostatak aplikacije radi.
- **Kalibracija po štampaču**, ne globalno — Epson L18050 ne štampa 1:1.
- **Kvalitet štampe se ne može nametnuti** iz koda: `PrintQuality` uvek
  vraća 720. Tip papira se menja kroz `DocumentProperties` merge.
- **Pauza za magnet** u 3D štampi nije stvar ove aplikacije — to je ram.
- Stari dnevnik `podaci/dnevnik.log` je ostao od pre prelaska na `applog`;
  može da se obriše ručno.

## Ažuriranje (V2/V3)

Folder na računaru je git klon MirkoRudic/kosnica-print (od 24.11.2026). `update.py` (kopija iz Nadzora), `/api/update`, `server.py --restart`. Verzija u `version.py`.

## Izuzeci od RULES.md

| Šifra | Izuzetak i zašto |
|---|---|
| **F1** | folderi se zovu `podaci/` i `izlaz/`, ne `data/`. Suština je ispoštovana — ništa ne izlazi iz foldera aplikacije. Preimenovanje bi tražilo migraciju profila i biblioteke, pa se ne dira. Dnevnik je u `podaci/logs/`. |
| **P2** | port **8733**, van opsega 8800–8899. Upisan takav u `APPLICATIONS.md`; menjanje bi tražilo i prečicu, `.vbs` i bukmarke. |
| **UI1** | ne koristi `moduli/static/base.css` — aplikacija ima svoju paletu sa tri teme (svetla/tamna/sepija). Pravila UI1 i UI8 su rešena u `deo_glava.html`. |
| **UI4** | ne koristi `moduli/static/dialog.js` — dijalozi su sopstveni `<dialog>` elementi u stilu aplikacije (`poruka`, `potvrdi`, `pitajNaziv`). Nema `alert/confirm/prompt` ni `title=`; oblačići idu kroz `data-savet`. |
| **UI11** | nema otiska u adresi jer CSS i JS nisu zasebni fajlovi — ulepljeni su u `index.html`. |
| **F2** | `profili.py` nije `moduli/settings.py` jer nosi i profile ramova i štampača sa kalibracijom, ne samo podešavanja. |
| — | `tempdir.py` i `runlock.py` se ne koriste: aplikacija ne pravi privremene fajlove (izlaz ide u `izlaz/`), a drugi klik se rešava proverom porta pre pokretanja. |

## Još nije urađeno

- **Zaglavlje sa vrstama štampe** (Ramić / Magneti / Šolja) — simulacija je
  napravljena, čeka se potvrda pre produkcije.
