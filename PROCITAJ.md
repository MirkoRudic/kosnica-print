# Košnica Print

Lokalna aplikacija za pripremu i štampu fotografija za 3D štampane magnetne ramove.

Interfejs se otvara u pregledaču, ali pregledač **samo crta**. Obrada slike i
izvoz rade u Python procesu na tvom računaru, pa između slike i štampača nema
nikoga ko bi je skalirao. To je bio ceo razlog za ovu aplikaciju.

---

## Pokretanje

Dupli klik na prečicu **Košnica Print** na Desktopu (prečica se ranije zvala „Priprema magneta“).

Ne otvara se nikakav crni prozor — server radi u pozadini, a aplikacija se
otvara u tvom podrazumevanom pregledaču na `http://127.0.0.1:8733`.

**Za gašenje** klikni dugme **Ugasi** dole desno u aplikaciji. Zatvaranje
samog prozora pregledača ne gasi server, samo sklanja prikaz.

Ako dvaput pokreneš, neće se buniti — samo otvori prozor na već pokrenutom.

### Kad nešto ne radi

Pokreni **`pokreni.bat`** u folderu aplikacije. To je ista stvar, ali sa
vidljivim prozorom u kom se čitaju poruke o greškama. Taj prozor je server,
pa se zatvaranjem gasi i aplikacija.

---

## Kako se radi

1. **Uvezi slike** — skenirani crteži ili fotografije, može više odjednom.
2. Slika se odmah uklapa u prozor rama: **centrirano, od ivice do ivice**.
   Aplikacija ne traži subjekat i ne kadrira umesto tebe.
3. Klizačima **Vodoravno / Uspravno / Zum** pomeri kadar gde hoćeš.
4. Izaberi **preset** ako treba, podesi **boju**.
5. **Napravi PDF** — slaže koliko komada stane na A4, sa linijama reza.

Režeš po zamišljenoj liniji koja spaja dve naspramne crtice. Ta linija prolazi
kroz obojeni deo — boja ide 3 mm preko reza namerno, da promašaj skalpela ne
ostavi belu prugu.

---

## Kalibracija

Radi se jednom po štampaču i papiru.

1. **Kalibracioni list** pravi A4 sa linijom od tačno 150 mm.
2. Odštampaj ga, pa je **izmeri šublerom**, ne lenjirom. Razlika od jednog
   milimetra na 150 je 0.7 %, a toliko je dovoljno da slika ne uđe u prorez.
3. Upiši izmereno u podešavanja. Faktor se od tada primenjuje **pri
   renderovanju**, ne u dijalogu za štampu, pa radi kroz bilo koji put do papira.

---

## Profili ramova

Mere se čuvaju u `podaci/profili.json` i mogu se menjati rukom.

Ključno: mere su **izmerene na odštampanom ramu**, ne projektovane. PLA se
skuplja oko 0.7 %, pa je prozor projektovan na 69.60 × 48.00 izašao
69.10 × 47.70. Kad odštampaš novi ram, izmeri prozor šublerom i upiši.

Rez slike se izvodi iz toga: prorez u ramu minus 0.4 mm zazora, jer sečeš ručno.

---

## Šta još nije povezano

**Direktna štampa na Epson.** Taj sloj (`win32print`, hvatanje `DEVMODE` bloka
sa podešavanjima drajvera) ne može da se napiše naslepo — greške u njemu se ne
vide iz koda nego tek kad papir izađe pogrešan. Piše se na mašini sa štampačem.

Do tada: izvezi PDF i odštampaj ga kao i do sada, sa zaključanim procentom.
Geometrija u PDF-u je tačna, to je provereno — marke su na 73.100 × 51.700 mm.

---

## Fajlovi

```
server.py        lokalni server i API
obrada.py        nivoi, lokalni kontrast, kadar, napust, preseti
tabak.py         raspored na A4, linije reza, lenjir, PDF
profili.py       profili ramova i kalibracija
static/          interfejs
podaci/          profili.json i uvezene slike
izlaz/           napravljeni PDF-ovi
```
