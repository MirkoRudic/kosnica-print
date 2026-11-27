# Košnica Print — stanje (26.11.2026)

Verzija **1.2.0**. Računar u radionici `desktop-fk7e7jt`, `C:\Users\zzroz\Desktop\VAJB\kosnica-print`, port 8733, git klon ovog repoa, ažuriranje iz Podešavanja → Verzija.
Nastavak u novom četu: pročitaj `AGENTS.md`, `SPECIFICATION.md`, ovaj fajl; pravila `vajb-osnova/RULES.md`. Ramovi (3D model) ne pripadaju ovde — `vajb-osnova/RULES_3D_PRINTING.md`.

## Poslednje urađeno
- 24.11: repo i ažuriranje iz app (V2/V3), Edge `--app` + ikonica pored sata (P3/P4), folder premešten u `Desktop\VAJB`.
- 19.11: Tabler ikonice, dnevnik `applog` po danu, oblačići `data-savet`, verzija i `/health`, ime Košnica Print, `sastavi.py`.

## Odluke
- Odvojena od Košnice 3D: svoj folder, port, dnevnik.
- Zaglavlje: tabovi Ramić / Magneti / Šolja; DTF, UV i nalepnice ne idu ovde.
- Spolja samo preko Cloudflare Tunnel-a sa Access-om; Workers/Pages ne dolaze u obzir (PIL, pymupdf, win32print).

## Otvoreno
- Zaglavlje sa vrstama štampe: simulacija https://claude.ai/artifact/RkGhZyXcBS8hQoQKwLVXQv čeka potvrdu (pitanje: zupčanik dole levo ili u zaglavlju).
- Sadržaj tabova Magneti i Šolja nije definisan.
- Tunnel: pre otvaranja spolja — Ugasi samo sa 127.0.0.1, sakriti „Izaberi fasciklu…“.
- Stari `podaci/dnevnik.log` može da se obriše.

## Nije provereno
- Ništa novo od 1.2.0.
