# Občina Hoče-Slivnica – Obveščevalec o novih objavah

Avtomatiziran sistem v Pythonu, ki redno preverja spletno stran Občine Hoče-Slivnica in ob zaznavi novih objav takoj pošlje potisno obvestilo (push notification) na telefon prek storitve **ntfy.sh**.

Projekt teče v oblaku prek **GitHub Actions**, stanje videnih objav pa samodejno shranjuje v repozitorij.

---

## Lastnosti
* **Avtomatsko preverjanje:** Teče dvakrat dnevno (ali ob ročnem zagonu).
* **Takojšnja obvestila:** Uporablja `ntfy.sh`, kar pomeni, da si lahko vsak član družine preprosto namesti uradno aplikacijo na telefon in prejema obvestila.
* **Bogata obvestila:** Obvestilo vsebuje naslov, datum, povezavo do objave in sliko (če jo objava vsebuje).
* **Brez stroškov:** Gostovano povsem brezplačno na GitHubu.

---

## Uporabljene tehnologije
* **Python 3.10+**
* **BeautifulSoup & Playwright** (za zajem dinamične vsebine in paginacijo)
* **GitHub Actions** (za brezplačno izvajanje v oblaku)
* **ntfy.sh** (za potisna obvestila na mobilne naprave)

---

## Nastavitev obvestil na telefonu
1. Prenesi aplikacijo **ntfy** (na voljo za Android in iOS).
2. V aplikaciji se naroči na isti kanal, ki si ga določil v `NTFY_TOPIC`.
3. Sedaj boš vsakič, ko občina objavi nekaj novega, prejel obvestilo neposredno na telefon!