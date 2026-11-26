# Košnica Print — specifikacija

Šta app radi iz ugla korisnika. Svaka izmena ponašanja prvo se upiše ovde, pa u kod.
Oblik: **kad uradim X → desi se Y**. Tehnika i zamke su u `CLAUDE.md`, gde smo stali u `STANJE.md`.

## Svrha
Priprema fotografija za ramiće i magnete i štampa na Epson L18050 u radionici Ožiljak. Obrada i izvoz rade u Python procesu, pa se između slike i štampača ništa ne skalira — mere na papiru su tačne.
Ranije „Foto Ramići“. Radi potpuno odvojeno od Košnice 3D.

## 1. Pokretanje
- Prečica „Košnica Print“ na Desktopu → app u sopstvenom prozoru (Edge bez adresne trake), ikonica pored sata. Bez crnog prozora.
- Drugi klik → otvori se postojeći prozor, ne druga app.
- Ugasi (dole levo/u zaglavlju) → gasi server; zatvaranje prozora ga ne gasi.

## 2. Slike
- Uvezi ili prevuci sliku (JPEG, PNG, HEIC, PDF — prva strana 400 dpi) → slika postaje tekuća i ide na vrh liste. Beli rub skenera se skida.
- App **nikad ne kadrira umesto mene**: slika se postavi od ivice do ivice; kadriranje mišem kao u Canvi.
- Rotacija i ogledalo vide se odmah i u pregledu i u izvozu.
- Kartice: **Boja** (auto nivoi, preseti sa klizačem jačine 0–100; sličice preseta na mojoj slici), **Preklop** (puna boja ili zamućena kopija, paleta + pipeta), **Tabak**.
- Zatamnjenje pokazuje deo slike koji ispada iz prozora rama (bez natpisa „odsečeno“).

## 3. Tabak i štampa
- Tabak: raspored na A4 po profilu rama, crtice za rez, broj kopija; Margina i Razmak vidljivi.
- Štampaj (uvek dole desno) → dijalog pre štampe: obim (podrazumevano **tekuća slika**), štampač, papir (tri imena; ceo spisak drajvera samo uz `svi_papiri`), kopije, pregled sa pravom slikom.
- Posle štampe → zasebna poruka o uspehu (nije isti prozor kao potvrda).
- Kalibracija se primenjuje pri izradi tabaka, nikad u dijalogu štampe. Podešavanje štampača važi samo za ovu app, nikad za sistem.
- PDF tabaka ide u `izlaz/` (`magneti_YYYYMMDD_HHMMSS.pdf`).

## 4. Biblioteka i podešavanja
- Sačuvana priprema = obična fascikla (`priprema.json` + izvor + pregled), vidljiva i bez app; drvo fascikli levo.
- Podešavanja (zupčanik): profili ramova, štampač i kalibracija (kontrolni list → šubler → upis mere), tema (svetla/tamna/sepija), Dnevnik, Verzija i ažuriranje.

## Namerno ne radi
- Nema `alert/confirm/prompt` ni sistemskih oblačića; sve u dizajnu app.
- Ne menja Mirkova podešavanja radi probe (probe sa `probno=1`).
- Štampa samo na Windows-u.

## Nije urađeno / nije provereno
- Zaglavlje sa vrstama štampe (Ramić / Magneti / Šolja) — simulacija čeka potvrdu.
- Pristup spolja preko Cloudflare Tunnel-a + Access — dogovoren pravac, nije počet.
